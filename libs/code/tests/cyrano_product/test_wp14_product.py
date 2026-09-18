"""WP14 product tests: episode/world/replay plus trace navigation."""

import json
from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.events.domain_sink import DomainSink
from deepagents_code.cyrano.improvement.episodes import (
    build_episode,
    failure_attribution,
    trace_run,
)
from deepagents_code.cyrano.improvement.replay import (
    DEPENDENCY_NOT_OBSERVED,
    INCOMPLETE,
    INPUT_MISMATCH,
    OUT_OF_SUPPORT,
    SIGNATURE_MISMATCH,
    SUPPORTED,
    TIMEOUT,
    WorldReplay,
    compare_report,
    settle_stop,
)
from deepagents_code.cyrano.improvement.worlds import (
    ExecutionSignature,
    build_world,
    public_observation,
)
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

ROOT = Path(__file__).resolve().parents[2]
TARGET_DDL = (ROOT / "cyrano/contracts/sql/target-schema.sql").read_text()

SIG = ExecutionSignature(
    model_id="m1",
    endpoint="https://api.example",
    runtime_digest="sha256:rt",
    tool_inventory_digest="sha256:tools",
    skill_digest="sha256:skill-a",
)

EVENTS = [
    {"node_id": "a1", "kind": "step", "input_digest": "sha256:i1"},
    {"node_id": "a2", "kind": "step", "input_digest": "sha256:i2"},
    {"node_id": "t", "kind": "run.finished", "input_digest": "sha256:it"},
]

LEGAL = frozenset({"a1", "a2", "b", "ghost"})


def _world(events=None, *, scores=None, signature=SIG, refs=None):
    episode = build_episode("ep1", events if events is not None else EVENTS)
    return build_world(episode, signature, scores=scores, external_refs=refs)


def _replay(world, signature=SIG):
    replay = WorldReplay(world, signature, legal_actions=LEGAL)
    replay.commit_slots(sorted(LEGAL))
    return replay


def _observation(world):
    return public_observation(
        world,
        attempts_used=1,
        error_kinds=["timeout"],
        budget_remaining=5,
        legal_actions=sorted(LEGAL),
    )


def _policy(obs):
    return ("stop" if obs["budget_remaining"] < 1 else "a1", obs)


# -- DREAM-RPL ---------------------------------------------------------


def test_dream_rpl_01_same_decision_hidden_scores_not_referenced():
    world_low = _world(scores={"a1": 0.1, "a2": 0.2})
    world_high = _world(scores={"a1": 0.9, "a2": 0.9})
    assert _observation(world_low) == _observation(world_high)
    assert _policy(_observation(world_low)) == _policy(
        _observation(world_high)
    )
    assert "hidden_score" not in json.dumps(_observation(world_high))


def test_dream_rpl_02_legal_action_without_transition_is_out_of_support():
    replay = _replay(_world())
    replay.open_batch({"ghost": "sha256:i1"})
    closed = replay.close_batch()
    assert closed.status == OUT_OF_SUPPORT
    assert closed.data_collection_required is True
    assert replay.world_score() is None
    assert all(s.result is None for s in closed.steps)


def test_dream_rpl_03_unobserved_dependency_blocks_replay():
    events = [
        {"node_id": "a", "kind": "step", "input_digest": "sha256:ia"},
        {
            "node_id": "b",
            "kind": "step",
            "input_digest": "sha256:ib",
            "observed_deps": ["a"],
        },
        {"node_id": "t", "kind": "run.finished", "input_digest": "x"},
    ]
    legal = frozenset({"a", "b"})
    replay = WorldReplay(_world(events), SIG, legal_actions=legal)
    replay.commit_slots(["a", "b"])
    outcome = replay.open_batch({"b": "sha256:ib"})
    step = next(s for s in outcome.steps if s.action_id == "b")
    assert step.status == DEPENDENCY_NOT_OBSERVED
    replay.close_batch()
    replay2 = WorldReplay(_world(events), SIG, legal_actions=legal)
    replay2.commit_slots(["a", "b"])
    replay2.open_batch({"a": "sha256:ia"})
    replay2.settle_step("a")
    assert replay2.close_batch().status == SUPPORTED
    replay2.open_batch({"b": "sha256:ib"})
    replay2.settle_step("b")
    assert replay2.close_batch().status == SUPPORTED


def test_dream_rpl_04_skill_drift_is_input_mismatch():
    drifted = ExecutionSignature(
        model_id=SIG.model_id,
        endpoint=SIG.endpoint,
        runtime_digest=SIG.runtime_digest,
        tool_inventory_digest=SIG.tool_inventory_digest,
        skill_digest="sha256:skill-b",
    )
    replay = _replay(_world(), signature=drifted)
    outcome = replay.open_batch({"a1": "sha256:i1"})
    assert all(s.status == INPUT_MISMATCH for s in outcome.steps)


def test_dream_rpl_05_model_drift_is_signature_mismatch_not_new_result():
    drifted = ExecutionSignature(
        model_id="m2",
        endpoint=SIG.endpoint,
        runtime_digest=SIG.runtime_digest,
        tool_inventory_digest=SIG.tool_inventory_digest,
        skill_digest=SIG.skill_digest,
    )
    world = _world()
    replay = _replay(world, signature=drifted)
    outcome = replay.open_batch({"a1": "sha256:i1"})
    assert all(s.status == SIGNATURE_MISMATCH for s in outcome.steps)
    assert outcome.recorded_signature == world.signature.signature_digest
    assert outcome.recorded_signature != drifted.signature_digest


def test_dream_rpl_06_slots_precede_results_no_best_leak():
    replay = _replay(_world(scores={"a1": 0.9, "a2": 0.1}))
    slots = replay.commit_slots(["a1", "a2"])
    assert len(slots) == 2
    obs = _observation(_world(scores={"a1": 0.9}))
    leaked = {"hidden_score", "best", "score", "result"} & set(obs)
    assert leaked == set()
    replay.open_batch({"a1": "sha256:i1"})
    replay.settle_step("a1")
    replay.close_batch()


def test_dream_rpl_07_tape_order_fixed_no_best_sample_selection():
    world = _world(scores={"a1": 0.1, "a2": 0.9})
    assert [t.action_id for t in world.transitions] == ["a1", "a2", "t"]
    obs = _observation(world)
    assert not any("score" in k or "best" in k for k in obs)
    replay = _replay(world)
    replay.open_batch({"a1": "sha256:i1", "a2": "sha256:i2"})
    replay.settle_step("a1")
    replay.settle_step("a2")
    assert replay.close_batch().status == SUPPORTED
    assert replay.world_score() == pytest.approx(0.5)


def test_dream_rpl_08_full_denominator_and_support_count():
    report = compare_report(
        {"w1": SUPPORTED, "w2": OUT_OF_SUPPORT, "w3": INCOMPLETE}
    )
    assert report["planned"] == 3
    assert report["supported"] == 1
    assert report["statuses"] == {
        "w1": SUPPORTED,
        "w2": OUT_OF_SUPPORT,
        "w3": INCOMPLETE,
    }


def test_dream_rpl_09_each_policy_starts_at_root():
    world = _world()
    first = _replay(world)
    first.open_batch({"a1": "sha256:i1"})
    first.settle_step("a1")
    first.close_batch()
    assert "a1" in first.select_next()
    second = _replay(world)
    assert second.select_next() == {}


def test_dream_rpl_10_external_id_substitution_same_result():
    w1 = _world(refs={"a1": "peer-run-1"})
    w2 = _world(refs={"a1": "peer-run-999"})
    assert w1.tape_digest == w2.tape_digest
    r1, r2 = _replay(w1), _replay(w2)
    for r in (r1, r2):
        r.open_batch({"a1": "sha256:i1"})
        r.settle_step("a1")
    assert r1.close_batch() == r2.close_batch()


def test_dream_rpl_11_missing_terminal_is_incomplete_not_scored():
    events = [e for e in EVENTS if e["kind"] != "run.finished"]
    world = _world(events)
    assert world.complete is False
    replay = _replay(world)
    outcome = replay.open_batch({"a1": "sha256:i1"})
    assert all(s.status == INCOMPLETE for s in outcome.steps)
    replay.close_batch()
    assert replay.world_score() is None


def test_dream_rpl_12_barrier_blocks_select_timeout_explicit():
    world = _world()
    replay = _replay(world)
    replay.open_batch({"a1": "sha256:i1", "a2": "sha256:i2"})
    replay.settle_step("a1")
    with pytest.raises(CyranoError, match="BATCH_INCOMPLETE"):
        replay.select_next()
    with pytest.raises(CyranoError, match="BATCH_INCOMPLETE"):
        replay.close_batch()
    replay.settle_step("a2", timed_out=True)
    outcome = replay.close_batch()
    assert outcome.status == TIMEOUT
    timed = next(s for s in outcome.steps if s.action_id == "a2")
    assert timed.status == TIMEOUT


# -- A-* exploration actions -------------------------------------------


def test_a_future_hidden_permutation_same_action():
    base = _world(scores={"a1": 0.1, "a2": 0.9})
    permuted = _world(scores={"a1": 0.9, "a2": 0.1})
    assert _observation(base) == _observation(permuted)
    assert _policy(_observation(base)) == _policy(_observation(permuted))


def test_a_batch_partial_support_reveals_nothing():
    replay = _replay(_world())
    replay.open_batch({"a1": "sha256:i1", "ghost": "sha256:i9"})
    replay.settle_step("a1")
    outcome = replay.close_batch()
    assert outcome.status == OUT_OF_SUPPORT
    assert all(s.result is None for s in outcome.steps)


def test_a_dependency_unexecuted_parent_never_guessed():
    events = [
        {
            "node_id": "b",
            "kind": "step",
            "input_digest": "sha256:ib",
            "observed_deps": ["a"],
        },
        {"node_id": "t", "kind": "run.finished", "input_digest": "x"},
    ]
    replay = _replay(_world(events))
    outcome = replay.open_batch({"b": "sha256:ib"})
    assert outcome.steps[0].status == DEPENDENCY_NOT_OBSERVED
    closed = replay.close_batch()
    assert closed.steps[0].result is None


def test_uncommitted_action_refused():
    replay = WorldReplay(_world(), SIG, legal_actions=LEGAL)
    with pytest.raises(CyranoError, match="SLOTS_NOT_COMMITTED"):
        replay.open_batch({"a1": "sha256:i1"})


def test_a_stop_exploration_never_skips_gates():
    with pytest.raises(CyranoError, match="COMPLETION_GATES_REQUIRED"):
        settle_stop(
            acceptance_granted=False, review_granted=True, reason="done"
        )
    record = settle_stop(
        acceptance_granted=True, review_granted=True, reason="done"
    )
    assert record["task_complete"] is False


# -- R3-44 trace navigation --------------------------------------------


@pytest.fixture()
def ctx(tmp_path):
    repo = ScopedRepository.create(tmp_path / "db.sqlite3", TARGET_DDL)
    scope = repo.register_scope("t1", "u1", "w1")
    repo.create_stream(scope, "run-1", "request")
    sink = DomainSink(repo)
    yield repo, scope, sink
    repo.close()


def _record(sink, scope, stream, seq, kind, payload):
    producers = {
        "model.attempt_started": "native_observer",
        "model.finished": "native_observer",
        "model.failed": "native_observer",
        "tool.denied": "tool_observer",
        "test.finished": "runner",
    }
    sink.record_event(scope, stream, producers[kind], seq, kind, payload)


def test_r3_44_01_trace_navigates_timeline_to_receipt(ctx):
    repo, scope, sink = ctx
    _record(
        sink,
        scope,
        "run-1",
        1,
        "model.attempt_started",
        {"attempt_id": "a1", "logical_request_id": "l1", "is_retry": 0},
    )
    _record(
        sink,
        scope,
        "run-1",
        2,
        "model.failed",
        {
            "attempt_id": "a1",
            "logical_request_id": "l1",
            "error_class": "timeout",
        },
    )
    page = trace_run(repo, scope, "run-1")
    assert [s.kind for s in page.spans] == [
        "model.attempt_started",
        "model.failed",
    ]
    span = page.spans[1]
    body = repo.read_artifact(scope, span.payload_digest)
    assert json.loads(body)["error_class"] == "timeout"
    trace = failure_attribution(repo, scope, "run-1")
    assert trace.root_cause == "provider_timeout"


def test_r3_44_02_foreign_scope_denied_without_leak(ctx):
    repo, scope, sink = ctx
    other = repo.register_scope("t1", "u2", "w2")
    _record(
        sink,
        scope,
        "run-1",
        1,
        "model.attempt_started",
        {"attempt_id": "a1", "logical_request_id": "l1", "is_retry": 0},
    )
    with pytest.raises(CyranoError, match="SCOPE_DENIED"):
        trace_run(repo, other, "run-1")
    with pytest.raises(CyranoError, match="SCOPE_DENIED"):
        trace_run(repo, other, "nonexistent-run")


def test_r3_44_03_event_seq_stable_pagination(ctx):
    repo, scope, sink = ctx
    for seq in range(1, 6):
        _record(
            sink,
            scope,
            "run-1",
            seq,
            "model.attempt_started",
            {
                "attempt_id": f"a{seq}",
                "logical_request_id": "l1",
                "is_retry": 0,
            },
        )
    seen: list[str] = []
    cursor = 0
    while True:
        page = trace_run(repo, scope, "run-1", cursor=cursor, limit=2)
        seen.extend(s.event_id for s in page.spans)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    assert len(seen) == 5
    assert len(set(seen)) == 5
    with pytest.raises(CyranoError, match="INPUT_INVALID"):
        trace_run(repo, scope, "run-1", cursor=-1)


def test_r3_44_04_deleted_payload_marked_unavailable(ctx):
    repo, scope, sink = ctx
    _record(
        sink,
        scope,
        "run-1",
        1,
        "model.failed",
        {
            "attempt_id": "a1",
            "logical_request_id": "l1",
            "error_class": "timeout",
        },
    )
    page = trace_run(repo, scope, "run-1")
    digest = page.spans[0].payload_digest
    repo.connection.execute(
        "DELETE FROM event_blobs WHERE raw_digest=?", (digest,)
    )
    repo.connection.commit()
    page = trace_run(repo, scope, "run-1")
    assert page.spans[0].evidence == "unavailable"
    assert repo.read_artifact(scope, digest) is None


def test_r3_44_05_lost_worker_root_cause_unknown(ctx):
    repo, scope, sink = ctx
    _record(
        sink,
        scope,
        "run-1",
        1,
        "model.attempt_started",
        {"attempt_id": "a1", "logical_request_id": "l1", "is_retry": 0},
    )
    trace = failure_attribution(repo, scope, "run-1")
    assert trace.root_cause == "unknown"
    assert trace.hypotheses
    assert trace.observed


def test_r3_44_06_distinct_failures_identified(ctx):
    repo, scope, sink = ctx
    repo.create_stream(scope, "run-deny", "request")
    repo.create_stream(scope, "run-test", "request")
    _record(
        sink,
        scope,
        "run-deny",
        1,
        "tool.denied",
        {"tool_call_id": "c1", "decision_id": "d1"},
    )
    _record(
        sink,
        scope,
        "run-test",
        1,
        "test.finished",
        {"run_id": "run-test", "outcome": "failed"},
    )
    _record(
        sink,
        scope,
        "run-1",
        1,
        "model.failed",
        {
            "attempt_id": "a1",
            "logical_request_id": "l1",
            "error_class": "timeout",
        },
    )
    deny = failure_attribution(repo, scope, "run-deny")
    test = failure_attribution(repo, scope, "run-test")
    provider = failure_attribution(repo, scope, "run-1")
    assert deny.root_cause == "approval_missing"
    assert deny.remediation_owner == "requester"
    assert test.root_cause == "test_failure"
    assert test.remediation_owner == "implementer"
    assert provider.root_cause == "provider_timeout"
    assert provider.remediation_owner == "platform"
