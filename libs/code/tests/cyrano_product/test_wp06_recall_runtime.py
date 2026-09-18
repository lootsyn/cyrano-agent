"""WP06 recall-to-obligation runtime through the real agent graph.

The governed path no longer needs a harness to stage memory records:
``MemoryGate.recall`` resolves eligible records, rule bodies and a
freshly pinned ``MemoryView`` from the live store per task, before the
plan is sealed. These tests run the real ``create_cli_agent`` graph
with a scripted local model — no provider calls — and prove:

    task context → recall → eligible records → pinned view →
    scope_rule projection → plan binding → approval/permit → mediated
    execution → deterministic verification → bounded correction →
    evidence.

Cache/staleness, scope-switch, revocation races, store errors and
delegation all fail closed. This is offline regression evidence, not
live effectiveness evidence.
"""

import dataclasses
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)
from langchain.agents.middleware.types import ToolCallRequest
from langchain.tools import ToolRuntime
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from deepagents_code._fake_models import _ToolBindingFakeModel
from deepagents_code.cyrano.context.binding import MemoryView
from deepagents_code.cyrano.context.compiler import CompiledContext
from deepagents_code.cyrano.context.epochs import epoch_for
from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.dcode.governed_middleware import (
    GovernedObligationMiddleware,
    GovernedSession,
)
from deepagents_code.cyrano.dcode.governed_runtime import (
    FEEDBACK_MARKER,
    ApprovalGate,
    GovernedRunConfig,
    MemoryGate,
    run_governed_work,
)
from deepagents_code.cyrano.dcode.recall import (
    RecallContext,
    RecallEvidence,
    RecallOutcome,
    task_recall,
)
from deepagents_code.cyrano.kernel.actions import ActionBroker, Grant
from deepagents_code.cyrano.kernel.approvals import (
    ApprovalDesk,
    issue_permit,
)
from deepagents_code.cyrano.memory import MemoryRepository, MemoryService
from deepagents_code.cyrano.memory.checkers import TrustedCheckerRegistry
from deepagents_code.cyrano.memory.obligations import project_obligations
from deepagents_code.cyrano.planning.subject import (
    GovernedWorkPlan,
    WorkUnitSpec,
)
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

KEY = Ed25519PrivateKey.generate()
PUB = KEY.public_key()
SRC = frozenset({"src:1"})

RULE_BODY = json.dumps(
    {
        "rule_id": "widgetbox-sidecar-v2",
        "checker_id": "sidecar-check",
        "applicability": {
            "write_globs": ["meta/*.json", "widgetbox/*.py"],
            "operations": ["create", "modify"],
        },
        "exceptions": [
            {
                "exception_id": "grandfather-alpha",
                "path_globs": ["meta/alpha.json"],
            }
        ],
        "summary": "sidecars use widgetbox.sidecar/2",
    }
).encode()

CHECKER_BODY = json.dumps(
    {
        "kind": "paired_files",
        "params": {
            "trigger": "widgetbox/*.py",
            "derive": "meta/{stem}.json",
            "required": True,
            "json_fields": {
                "schema": {"equals": "widgetbox.sidecar/2"},
                "compat": {"equals": "widgetbox/2"},
                "lifecycle": {
                    "one_of": ["stable", "beta", "deprecated", "retired"]
                },
                "name": {"matches_stem": True},
                "owners": {"required": True},
            },
        },
    }
).encode()

V1_SIDECAR = json.dumps(
    {
        "name": "alpha",
        "schema": "widgetbox.sidecar/1",
        "lifecycle": "stable",
        "owners": ["w"],
    }
)


def _v2(name: str) -> str:
    return json.dumps(
        {
            "name": name,
            "schema": "widgetbox.sidecar/2",
            "lifecycle": "stable",
            "compat": "widgetbox/2",
            "owners": ["w"],
        }
    )


_PY = "def widget():\n    return 1\n"

ALL_PROBES = {
    "extension_loading": "verified",
    "async_middleware": "verified",
    "child_observation": "verified",
    "tool_mediation": "verified",
    "sandbox_isolation": "verified",
    "trusted_approval": "verified",
    "context_manifest": "verified",
    "cancel_recovery": "verified",
}


class _ScriptedModel(_ToolBindingFakeModel):
    """Prompt-driven fake model emitting scripted tool calls."""

    script: Any = None

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,  # noqa: ARG002
        run_manager: Any = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> ChatResult:
        """Delegate to the test-supplied script over the messages."""
        assert self.script is not None
        return ChatResult(
            generations=[ChatGeneration(message=self.script(messages))]
        )

    @property
    def _llm_type(self) -> str:
        """Model type label for wire evidence."""
        return "scripted-fake"


def _abs(workspace: Path, path: str) -> str:
    """Real host path for a workspace-relative path.

    The governed backend runs ``virtual_mode=False``, so (like a real
    model told its cwd) calls carry absolute paths.
    """
    return str(workspace / path)


def _write_calls(
    workspace: Path,
    writes: dict[str, str],
    prefix: str = "w",
) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "write_file",
                "args": {
                    "file_path": _abs(workspace, path),
                    "content": content,
                },
                "id": f"{prefix}-{i}",
            }
            for i, (path, content) in enumerate(writes.items())
        ],
    )


ROOT = Path(__file__).resolve().parents[2]
TARGET_DDL = (ROOT / "cyrano/contracts/sql/target-schema.sql").read_text()


@pytest.fixture
def env(tmp_path):
    """Store, workspace, plan — no caller-staged records."""
    repo = ScopedRepository.create(tmp_path / "db.sqlite3", TARGET_DDL)
    scope = repo.register_scope("t1", "u1", "w1")
    service = MemoryService(MemoryRepository(repo))
    service.propose_memory(
        scope,
        "rule-sidecar",
        kind="scope_rule",
        content=RULE_BODY,
        source_digest="src:1",
        evidence_refs=("e:1",),
        at=1,
    )
    service.activate_memory(scope, "rule-sidecar", expected_revision=1, at=2)

    workspace = tmp_path / "ws"
    (workspace / "meta").mkdir(parents=True)
    (workspace / "widgetbox").mkdir()
    (workspace / "meta" / "alpha.json").write_text(V1_SIDECAR)

    plan = GovernedWorkPlan(
        plan_id="plan-1",
        revision=1,
        requirements=("REQ:sidecar",),
        units=(
            WorkUnitSpec(
                unit_id="u1",
                requirement_ids=("REQ:sidecar",),
                acceptance_ids=("ACC:sidecar",),
                write_paths=("widgetbox/x.py", "meta/x.json"),
                test_recipe="sidecar-check",
                test_oracle="verify_obligations",
                cost_cap=4,
            ),
        ),
        budget_cap=8,
    )
    state = {
        "clock": [10],
        "audit": [],
        "service": service,
        "db_path": tmp_path / "db.sqlite3",
        "scope": scope,
        "workspace": workspace,
        "plan": plan,
    }
    yield state
    repo.close()


def _fresh_repo(env) -> ScopedRepository:
    """A fresh connection — callbacks may run on executor threads."""
    return ScopedRepository.open(env["db_path"])


def _fresh_service(env) -> MemoryService:
    return MemoryService(MemoryRepository(_fresh_repo(env)))


def _recall(env) -> Callable[[RecallContext], RecallOutcome]:
    """The live recall provider — a fresh store read per call."""

    def provider(ctx):
        repo = _fresh_repo(env)
        try:
            return task_recall(
                service=MemoryService(MemoryRepository(repo)),
                repository=MemoryRepository(repo),
                context=ctx,
            )
        finally:
            repo.close()

    return provider


def _is_current(env) -> Callable[[str, int], bool]:
    def check(mid: str, rev: int) -> bool:
        service = _fresh_service(env)
        try:
            record = service.get(env["scope"], mid)
        finally:
            service._repo._repo.close()
        return (
            record is not None
            and record.revision == rev
            and record.status == "active"
        )

    return check


def _live_view(env) -> Callable[[], MemoryView]:
    """The store-derived view — re-reads revocation state per call."""

    def view() -> MemoryView:
        repo = _fresh_repo(env)
        try:
            records = MemoryRepository(repo).list_scope(env["scope"])
        finally:
            repo.close()
        revoked = frozenset(
            r.memory_id for r in records if r.status != "active"
        )
        return MemoryView(digest(sorted(revoked)), "live", revoked)

    return view


def _registry() -> TrustedCheckerRegistry:
    registry = TrustedCheckerRegistry()
    registry.register("sidecar-check", CHECKER_BODY)
    return registry


def _gates(env, **overrides):
    """Recall-backed gates — no caller-staged records or bodies."""
    config = GovernedRunConfig(
        plan=env["plan"],
        task_text="Implement the widget and its v2 sidecar.",
        scope_id=env["scope"],
        workspace=env["workspace"],
        grants=overrides.pop(
            "grants",
            (
                Grant(
                    path="widgetbox/x.py",
                    allow=frozenset({"create", "write_existing"}),
                ),
                Grant(
                    path="meta/x.json",
                    allow=frozenset({"create", "write_existing"}),
                ),
                Grant(
                    path="meta/alpha.json",
                    allow=frozenset({"read"}),
                ),
            ),
        ),
        tools=frozenset({"write_file", "read_file", "edit_file"}),
        requirements_doc={"spec": {"REQ:sidecar": "v2 sidecar required"}},
        source_snapshot={"tree": "snap-1"},
        scope={"scope_id": env["scope"]},
        now=lambda: env["clock"][0],
        cost_cap=overrides.pop("cost_cap", 4),
        run_id=overrides.pop("run_id", "run-1"),
        **{
            k: v
            for k, v in overrides.items()
            if k
            not in {
                "decide",
                "epoch",
                "compiled",
                "admitted_kinds",
                "recall",
            }
        },
        epoch=overrides.get("epoch"),
        compiled=overrides.get("compiled"),
    )
    memory = MemoryGate(
        records=(),
        rule_bodies={},
        available_source_digests=SRC,
        registry=_registry(),
        is_current=_is_current(env),
        view_provider=_live_view(env),
        recall=overrides.get("recall", _recall(env)),
        admitted_kinds=overrides.get("admitted_kinds", frozenset()),
    )
    approval = ApprovalGate(
        desk=ApprovalDesk(),
        signing_key=KEY,
        trust_root=PUB,
        audience="operator",
        is_revoked=lambda pid: pid in env.get("revoked_permits", ()),
        audit=env["audit"].append,
        decide=overrides.get("decide"),
    )
    return config, memory, approval


def _agent_factory(script, workspace: Path):
    def build(registry):
        import os

        from deepagents_code.agent import create_cli_agent

        agent, _backend = create_cli_agent(
            model=_ScriptedModel(script=script),
            assistant_id="governed-recall-test",
            interactive=False,
            auto_approve=True,
            enable_ask_user=False,
            enable_memory=False,
            enable_skills=False,
            enable_shell=False,
            system_prompt="You write files as instructed.",
            cwd=workspace,
            checkpointer=InMemorySaver(),
            extension_registry=registry,
            enforce_model_policy=False,
            environ={
                **os.environ,
                "DEEPAGENTS_CODE_EXPERIMENTAL": "1",
            },
        )
        return agent

    return build


def _good_script(workspace: Path):
    def script(messages):
        if _has_tool_results(messages):
            return AIMessage(content="done")
        return _write_calls(
            workspace, {"widgetbox/x.py": _PY, "meta/x.json": _v2("x")}
        )

    return script


def _has_tool_results(messages: list[BaseMessage]) -> bool:
    return any(isinstance(m, ToolMessage) for m in messages)


def _correction_turn(messages: list[BaseMessage]) -> bool:
    return any(
        isinstance(m, HumanMessage)
        and isinstance(m.content, str)
        and m.content.startswith(FEEDBACK_MARKER)
        for m in messages
    )


async def _run(env, script, **overrides):
    config, memory, approval = _gates(env, **overrides)
    return await run_governed_work(
        config=config,
        memory=memory,
        approval=approval,
        probe_report=ALL_PROBES,
        agent_factory=_agent_factory(script, env["workspace"]),
    )


# ------------------------------------------------------------- path --


async def test_recall_projects_active_rule(env):
    """The store's active scope_rule reaches the plan unstaged."""
    evidence = await _run(env, _good_script(env["workspace"]))
    assert evidence.status == "satisfied"
    assert evidence.recall is not None
    returned = dict(_recall_of(evidence).returned)
    assert "rule-sidecar" in returned
    assert evidence.obligations
    obligation = evidence.obligations[0]
    assert obligation.memory_id == "rule-sidecar"
    assert obligation.revision == returned["rule-sidecar"]
    assert all(v.state == "applied" for v in evidence.verdicts)
    assert (env["workspace"] / "meta" / "x.json").exists()


async def test_unrelated_memory_recalled_not_projected(env):
    """A non-rule record is recalled yet never gains authority."""
    env["service"].propose_memory(
        env["scope"],
        "note-1",
        kind="fact",
        content=b"an ordinary note",
        source_digest="src:1",
        evidence_refs=("e:2",),
        at=3,
    )
    env["service"].activate_memory(
        env["scope"], "note-1", expected_revision=1, at=4
    )
    evidence = await _run(env, _good_script(env["workspace"]))
    assert evidence.status == "satisfied"
    returned_ids = {mid for mid, _ in _recall_of(evidence).returned}
    assert "note-1" in returned_ids  # recalled
    assert all(
        o.memory_id != "note-1" for o in evidence.obligations
    )  # never projected
    assert evidence.readonly is not None
    assert "note-1" in evidence.readonly.reference_ids


async def test_stale_rule_excluded(env):
    """An invalidated rule is recall-excluded, never projected."""
    env["service"].invalidate(env["scope"], "rule-sidecar", at=3)
    evidence = await _run(env, _good_script(env["workspace"]))
    assert evidence.status == "satisfied"
    assert evidence.obligations == ()
    reasons = dict(_recall_of(evidence).excluded)
    assert reasons["rule-sidecar"] == "inactive:stale"


async def test_revoked_rule_excluded(env):
    """A quarantined rule is excluded and the view marks it revoked."""
    env["service"].quarantine(env["scope"], "rule-sidecar", at=3)
    evidence = await _run(env, _good_script(env["workspace"]))
    assert evidence.status == "satisfied"
    assert evidence.obligations == ()
    reasons = dict(_recall_of(evidence).excluded)
    assert reasons["rule-sidecar"] == "inactive:quarantined"


async def test_expired_rule_excluded(env):
    """A rule past expires_at never reaches projection."""
    env["service"].invalidate(env["scope"], "rule-sidecar", at=3)
    env["service"].propose_memory(
        env["scope"],
        "rule-exp",
        kind="scope_rule",
        content=RULE_BODY,
        source_digest="src:1",
        evidence_refs=("e:3",),
        at=4,
        expires_at=5,  # now == 10 — already expired
    )
    env["service"].activate_memory(
        env["scope"], "rule-exp", expected_revision=1, at=5
    )
    evidence = await _run(env, _good_script(env["workspace"]))
    assert evidence.status == "satisfied"
    assert evidence.obligations == ()
    reasons = dict(_recall_of(evidence).excluded)
    assert reasons.get("rule-exp") == "expired"


async def test_superseded_rule_excluded(env):
    """Supersession projects only the live revision."""
    env["service"].invalidate(env["scope"], "rule-sidecar", at=3)
    env["service"].propose_memory(
        env["scope"],
        "rule-v2",
        kind="scope_rule",
        content=RULE_BODY,
        source_digest="src:1",
        evidence_refs=("e:4",),
        at=4,
    )
    env["service"].activate_memory(
        env["scope"], "rule-v2", expected_revision=1, at=5
    )
    evidence = await _run(env, _good_script(env["workspace"]))
    assert evidence.status == "satisfied"
    assert [o.memory_id for o in evidence.obligations] == ["rule-v2"]
    reasons = dict(_recall_of(evidence).excluded)
    assert reasons["rule-sidecar"] == "inactive:stale"


async def test_inapplicable_selector_refuses(env):
    """A recalled rule matching no unit refuses as UNBOUND — no skip."""
    env["service"].propose_memory(
        env["scope"],
        "rule-other",
        kind="scope_rule.other",
        content=json.dumps(
            {
                "rule_id": "other",
                "checker_id": "sidecar-check",
                "applicability": {
                    "write_globs": ["other/*.py"],
                    "operations": ["create"],
                },
                "exceptions": [],
                "summary": "other tree only",
            }
        ).encode(),
        source_digest="src:1",
        evidence_refs=("e:5",),
        at=3,
    )
    env["service"].activate_memory(
        env["scope"], "rule-other", expected_revision=1, at=4
    )
    evidence = await _run(
        env,
        _good_script(env["workspace"]),
        admitted_kinds=frozenset({"scope_rule.other"}),
    )
    assert evidence.status == "refused"
    assert evidence.refusal_code == "UNBOUND_OBLIGATION"
    assert "rule-other" in {o.memory_id for o in evidence.obligations}


async def test_revision_change_between_recall_and_approval(env):
    """A rule moved inside the approval boundary refuses dispatch."""

    def decide(_record):
        service = _fresh_service(env)
        try:
            # Bump the stored revision while the record stays active.
            service._repo.transition(
                env["scope"],
                "rule-sidecar",
                "active",
                expected_revision=2,
                new_revision=5,
                at=9,
            )
        finally:
            service._repo._repo.close()
        return "approve"

    config, memory, approval = _gates(env, decide=decide)
    evidence = await run_governed_work(
        config=config,
        memory=memory,
        approval=approval,
        probe_report=ALL_PROBES,
        agent_factory=_agent_factory(
            _good_script(env["workspace"]), env["workspace"]
        ),
    )
    assert evidence.status == "refused"
    assert evidence.refusal_code == "STALE_REVISION"


async def test_new_rule_after_approval_forces_replan(env):
    """A rule activated mid-run is drift — the sealed plan aborts."""

    def script(messages):
        if _has_tool_results(messages):
            return AIMessage(content="done")
        service = _fresh_service(env)
        try:
            service.propose_memory(
                env["scope"],
                "rule-late",
                kind="scope_rule",
                content=RULE_BODY,
                source_digest="src:1",
                evidence_refs=("e:6",),
                at=8,
            )
            service.activate_memory(
                env["scope"],
                "rule-late",
                expected_revision=1,
                supersedes="rule-sidecar",
                at=9,
            )
        finally:
            service._repo._repo.close()
        return _write_calls(
            env["workspace"],
            {"widgetbox/x.py": _PY, "meta/x.json": _v2("x")},
        )

    evidence = await _run(env, script)
    assert evidence.status == "aborted"
    assert evidence.refusal_code in {
        "OBLIGATION_DRIFT",
        "STALE_REVISION",
        "MEMORY_REVOKED",
    }


async def test_epoch_change_after_cached_recall(env):
    """An epoch pinned to an older view refuses the fresh binding."""
    config, memory, approval = _gates(env)
    # Caller compiled its epoch against a stale empty-revocation view.
    # The stale epoch claims a revocation the live store does not have.
    stale_view = MemoryView(digest(["ghost"]), "old-rel", frozenset({"ghost"}))
    config = dataclasses.replace(
        config,
        epoch=epoch_for(
            tool_inventory_digest="t",
            model_identity="m",
            route=None,
            release_digest="r",
            profile_digest="p",
            memory_view_digest=stale_view.view_digest,
        ),
        compiled=CompiledContext(
            stable_text="s",
            dynamic_text="d",
            stable_digest="sd",
            request_digest="rd",
            stable_bytes=0,
            block_digests=(),
        ),
    )
    evidence = await run_governed_work(
        config=config,
        memory=memory,
        approval=approval,
        probe_report=ALL_PROBES,
        agent_factory=_agent_factory(
            _good_script(env["workspace"]), env["workspace"]
        ),
    )
    assert evidence.status == "refused"
    assert evidence.refusal_code == "STALE_EPOCH"


async def test_second_task_recalls_fresh(env):
    """A second task in the same process re-recalls — no stale reuse."""
    first = await _run(env, _good_script(env["workspace"]), run_id="run-a")
    assert first.status == "satisfied"
    # Store moved on: the rule was superseded between tasks.
    env["service"].invalidate(env["scope"], "rule-sidecar", at=6)
    env["service"].propose_memory(
        env["scope"],
        "rule-v3",
        kind="scope_rule",
        content=RULE_BODY,
        source_digest="src:1",
        evidence_refs=("e:7",),
        at=7,
    )
    env["service"].activate_memory(
        env["scope"], "rule-v3", expected_revision=1, at=8
    )
    second = await _run(env, _good_script(env["workspace"]), run_id="run-b")
    assert second.status == "satisfied"
    assert [o.memory_id for o in second.obligations] == ["rule-v3"]
    returned = dict(_recall_of(second).returned)
    assert "rule-v3" in returned and "rule-sidecar" not in {
        o.memory_id for o in second.obligations
    }


async def test_scope_switch_no_leak(env):
    """A second scope's records never surface in this run's recall."""
    repo = ScopedRepository.open(env["db_path"])
    try:
        other = repo.register_scope("t1", "u1", "w-other")
        svc = MemoryService(MemoryRepository(repo))
        svc.propose_memory(
            other,
            "rule-other-scope",
            kind="scope_rule",
            content=RULE_BODY,
            source_digest="src:1",
            evidence_refs=("e:8",),
            at=3,
        )
        svc.activate_memory(
            other, "rule-other-scope", expected_revision=1, at=4
        )
    finally:
        repo.close()
    evidence = await _run(env, _good_script(env["workspace"]))
    assert evidence.status == "satisfied"
    returned_ids = {mid for mid, _ in _recall_of(evidence).returned}
    assert "rule-other-scope" not in returned_ids
    assert all(o.memory_id == "rule-sidecar" for o in evidence.obligations)


async def test_delegated_tool_call_uses_same_session(env):
    """A delegated call mediates on the canonical session binding.

    Obligations live on ``GovernedSession`` — a delegated call gets the
    identical permit/broker decision, never a prompt-inherited copy.
    """
    config, _memory, _approval = _gates(env)
    outcome = _recall(env)(
        RecallContext(
            task_id="t",
            scope_id=env["scope"],
            path_hints=(),
            query_terms=None,
            limit=10,
            now=env["clock"][0],
            epoch=None,
            source_digests=SRC,
        )
    )
    obligations = project_obligations(
        list(outcome.records),
        scope_id=env["scope"],
        now=env["clock"][0],
        available_source_digests=SRC,
        rule_bodies=outcome.rule_bodies,
        memory_view=outcome.memory_view,
        checker_digests=_registry().digests(),
    ).obligations
    permit = issue_permit(
        KEY,
        permit_id="p-del",
        subject_digest="sd",
        shown_digest="sh",
        user_event_id="u",
        scope_id=env["scope"],
        purpose="execute",
        audience="operator",
        nonce="n",
        issued_at=1,
        expires_at=env["clock"][0] + 3600,
    )
    session = GovernedSession(
        broker=ActionBroker(
            tools=frozenset({"write_file"}),
            grants=config.grants,
            audit=env["audit"].append,
        ),
        permit=permit,
        trust_root=PUB,
        subject_digest="sd",
        root=env["workspace"],
        currency_check=lambda: None,
        is_revoked=lambda _pid: False,
        now=lambda: env["clock"][0],
        audit=env["audit"].append,
        obligations=obligations,
    )
    middleware = GovernedObligationMiddleware(session)
    # A delegated write on a granted path mediates through the same
    # permit; an out-of-grant path is denied — identical decisions.
    granted = _fake_tool_request(
        "write_file",
        {"file_path": str(env["workspace"] / "widgetbox" / "x.py")},
    )
    result = middleware.wrap_tool_call(
        granted,
        lambda _r: ToolMessage(
            content="ok", tool_call_id="d1", name="write_file"
        ),
    )
    assert getattr(result, "status", "success") != "error"
    denied = _fake_tool_request(
        "write_file",
        {"file_path": str(env["workspace"] / "outside" / "no.py")},
    )
    result = middleware.wrap_tool_call(
        denied,
        lambda _r: ToolMessage(
            content="ok", tool_call_id="d2", name="write_file"
        ),
    )
    assert getattr(result, "status", "success") == "error"
    # And a `task` delegation call itself is not silently allowed.
    task_call = _fake_tool_request(
        "task", {"subagent_type": "general-purpose", "description": "x"}
    )
    result = middleware.wrap_tool_call(
        task_call,
        lambda _r: ToolMessage(content="ok", tool_call_id="d3", name="task"),
    )
    assert getattr(result, "status", "success") == "error"
    assert any("UNSUPPORTED_TOOL" in d for d in middleware.denials)


def _recall_of(evidence) -> RecallEvidence:
    """Narrow the run's recall evidence — present on every live run."""
    assert evidence.recall is not None
    return evidence.recall


def _fake_tool_request(name: str, args: dict[str, object]):
    return ToolCallRequest(
        tool_call={
            "name": name,
            "args": args,
            "id": "d1",
            "type": "tool_call",
        },
        tool=None,
        state={},
        runtime=ToolRuntime(
            state={},
            context=None,
            config=RunnableConfig(),
            stream_writer=lambda _chunk: None,
            tool_call_id="d1",
            store=None,
        ),
    )


async def test_recall_returns_no_memory(env):
    """An empty store yields an honest empty recall, not fabrication."""
    env["service"].invalidate(env["scope"], "rule-sidecar", at=3)
    evidence = await _run(env, _good_script(env["workspace"]))
    assert evidence.status == "satisfied"
    assert _recall_of(evidence).returned == ()
    assert _recall_of(evidence).reason == "no_recall"
    assert evidence.obligations == ()


async def test_recall_store_error_refuses(env):
    """A store failure is refused — no obligations are fabricated."""

    def broken(_ctx):
        raise CyranoError("MEMORY_STORE_UNAVAILABLE", "db locked")

    config, memory, approval = _gates(env)
    memory = dataclasses.replace(memory, recall=broken)
    evidence = await run_governed_work(
        config=config,
        memory=memory,
        approval=approval,
        probe_report=ALL_PROBES,
        agent_factory=_agent_factory(
            _good_script(env["workspace"]), env["workspace"]
        ),
    )
    assert evidence.status == "refused"
    assert evidence.refusal_code == "MEMORY_STORE_UNAVAILABLE"
    assert evidence.obligations == ()
    assert not (env["workspace"] / "meta" / "x.json").exists()


async def test_study3_recall_reaches_v2(env):
    """The v1-exemplar scenario through recall — offline regression.

    The v2 rule arrives via the store recall, not manual injection;
    the first pass imitates the visible v1 exemplar, the checker
    rejects it, and the bounded correction produces the v2 postimage.
    """

    def script(messages):
        if _correction_turn(messages):
            return _write_calls(
                env["workspace"], {"meta/x.json": _v2("x")}, prefix="f"
            )
        if _has_tool_results(messages):
            return AIMessage(content="done")
        return _write_calls(
            env["workspace"],
            {
                "widgetbox/x.py": _PY,
                "meta/x.json": json.dumps(
                    {
                        "name": "x",
                        "schema": "widgetbox.sidecar/1",
                        "lifecycle": "stable",
                        "owners": ["w"],
                    }
                ),
            },
        )

    evidence = await _run(env, script)
    assert evidence.status == "corrected"
    assert evidence.recall is not None
    assert evidence.obligations
    ledger = evidence.ledgers[0]
    assert ledger.first_failure is not None
    assert ledger.first_failure.verdict.state == "violated"
    final = json.loads((env["workspace"] / "meta" / "x.json").read_text())
    assert final["schema"] == "widgetbox.sidecar/2"


async def test_exception_releases_on_touched_path(env):
    """Touching the grandfathered path forfeits the exception.

    ``meta/alpha.json`` is exception-covered while untouched — the
    satisfied runs above prove the skip. Writing v1 there releases
    the clause, the checker evaluates it, and correction must repair.
    """
    grants = (
        Grant(
            path="widgetbox/x.py",
            allow=frozenset({"create", "write_existing"}),
        ),
        Grant(
            path="widgetbox/alpha.py",
            allow=frozenset({"create", "write_existing"}),
        ),
        Grant(
            path="meta/x.json",
            allow=frozenset({"create", "write_existing"}),
        ),
        Grant(
            path="meta/alpha.json",
            allow=frozenset({"write_existing"}),
        ),
    )

    def script(messages):
        if _correction_turn(messages):
            return _write_calls(
                env["workspace"],
                {"meta/alpha.json": _v2("alpha")},
                prefix="f",
            )
        if _has_tool_results(messages):
            return AIMessage(content="done")
        return _write_calls(
            env["workspace"],
            {
                "widgetbox/x.py": _PY,
                "widgetbox/alpha.py": _PY,
                "meta/x.json": _v2("x"),
                "meta/alpha.json": V1_SIDECAR,
            },
        )

    evidence = await _run(env, script, grants=grants)
    assert evidence.status == "corrected"
    ledger = evidence.ledgers[0]
    assert ledger.first_failure is not None
    assert ledger.first_failure.verdict.state == "violated"
    final = json.loads((env["workspace"] / "meta" / "alpha.json").read_text())
    assert final["schema"] == "widgetbox.sidecar/2"


async def test_caller_staged_view_bypassed_by_recall(env):
    """A stale caller-pinned view cannot bypass the fresh pin."""
    config, memory, approval = _gates(env)
    # A deliberately wrong pinned view that revokes the live rule.
    bad_view = MemoryView(
        digest(["rule-sidecar"]), "stale", frozenset({"rule-sidecar"})
    )
    memory = dataclasses.replace(memory, memory_view=bad_view)
    evidence = await run_governed_work(
        config=config,
        memory=memory,
        approval=approval,
        probe_report=ALL_PROBES,
        agent_factory=_agent_factory(
            _good_script(env["workspace"]), env["workspace"]
        ),
    )
    # Recall's fresh pin wins — the staged view never authorizes.
    assert evidence.status == "satisfied"
    assert evidence.recall is not None
    assert _recall_of(evidence).view_digest != bad_view.view_digest
    assert evidence.obligations
