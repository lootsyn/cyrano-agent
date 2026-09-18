"""WP17 contract scenarios: CON-SKL-01..12."""

from __future__ import annotations

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.evaluation.gates import judge_candidate
from deepagents_code.cyrano.improvement.skill_lane import (
    SkillRegistry,
    SkillRelease,
    check_skill_impact,
    extract_lesson,
    prepare_memory_skill_bundle,
    propose_skill_candidate,
)


def _registry():
    return SkillRegistry(SkillRelease("s1", "r1", None, "sha256:c1", "active"))


def _lesson(**kw):
    base = {
        "repeats": 3,
        "scope_id": "ws-1",
        "counterexamples": ["ce1"],
        "body": "check imports before editing",
    }
    base.update(kw)
    return base


def _evidence(candidate):
    return {
        "kind": "actual_paired",
        "body_digest": candidate.content_digest,
    }


# -- CON-SKL -----------------------------------------------------------


def test_con_skl_01_repeated_lesson_stored_as_candidate_only():
    candidate = propose_skill_candidate(
        _lesson(), skill_id="s1", parent_release_id="r1", author="a"
    )
    assert candidate.state == "candidate"
    assert candidate.counterexamples == ("ce1",)
    with pytest.raises(CyranoError, match="EVIDENCE_REQUIRED"):
        propose_skill_candidate(
            _lesson(repeats=1),
            skill_id="s1",
            parent_release_id="r1",
            author="a",
        )


def test_con_skl_02_expected_red_classified_expected_failure():
    lesson = extract_lesson(
        {"expected_red": True, "outcome": "failed", "summary": "x"}
    )
    assert lesson["kind"] == "expected_failure"
    assert lesson["lesson"] is None


def test_con_skl_03_hidden_acceptance_delete_is_protected():
    impact = check_skill_impact(
        ["evaluation/sealed/hidden_acceptance.py"],
        claimed_kind="code",
        input_semantics_unchanged=False,
        policy_ir_validated=False,
    )
    assert impact["effect_class"] == "protected_change"
    assert impact["blocked"] is True


def test_con_skl_04_body_change_with_replay_only_blocked():
    registry = _registry()
    candidate = propose_skill_candidate(
        _lesson(), skill_id="s1", parent_release_id="r1", author="a"
    )
    with pytest.raises(CyranoError, match="BLOCKED"):
        registry.promote(
            candidate,
            evidence={"kind": "replay", "score": 0.9},
        )


def test_con_skl_05_py_change_claimed_as_wording_is_code():
    impact = check_skill_impact(
        ["skills/s1/resources/run.py", "skills/s1/README.md"],
        claimed_kind="wording",
        input_semantics_unchanged=False,
        policy_ir_validated=False,
    )
    assert impact["actual_kind"] == "code"
    assert impact["route"] == "high_risk_review"


def test_con_skl_06_merge_dropping_counterexample_invalid():
    with pytest.raises(CyranoError, match="INPUT_INVALID"):
        prepare_memory_skill_bundle(
            [],
            [
                {
                    "id": "s-merge",
                    "counterexamples": [],
                    "dropped_counterexamples": ["ce1"],
                }
            ],
        )
    ok = prepare_memory_skill_bundle(
        [{"id": "m1", "counterexamples": ["ce1"]}],
        [{"id": "s1", "counterexamples": ["ce2"]}],
    )
    assert set(ok["counterexamples"]) == {"ce1", "ce2"}


def test_con_skl_07_one_char_edit_is_stale_evidence():
    registry = _registry()
    candidate = propose_skill_candidate(
        _lesson(), skill_id="s1", parent_release_id="r1", author="a"
    )
    evidence = _evidence(candidate)
    evidence["body_digest"] = "sha256:older-body"
    with pytest.raises(CyranoError, match="STALE_EVIDENCE"):
        registry.promote(candidate, evidence=evidence)


def test_con_skl_08_cas_same_parent_one_winner():
    registry = _registry()
    first = propose_skill_candidate(
        _lesson(), skill_id="s1", parent_release_id="r1", author="a"
    )
    second = propose_skill_candidate(
        _lesson(body="prefer the smallest diff"),
        skill_id="s1",
        parent_release_id="r1",
        author="b",
    )
    winner = registry.promote(first, evidence=_evidence(first))
    assert winner.parent_release_id == "r1"
    with pytest.raises(CyranoError, match="REBASE_REQUIRED"):
        registry.promote(second, evidence=_evidence(second))


def test_con_skl_09_new_task_binds_new_release():
    registry = _registry()
    candidate = propose_skill_candidate(
        _lesson(), skill_id="s1", parent_release_id="r1", author="a"
    )
    promoted = registry.promote(candidate, evidence=_evidence(candidate))
    bound = registry.bind_run(
        {
            "release_id": promoted.release_id,
            "started_after_promotion": True,
        }
    )
    assert bound["ok"] is True


def test_con_skl_10_running_r1_stays_new_run_gets_r2():
    registry = _registry()
    candidate = propose_skill_candidate(
        _lesson(), skill_id="s1", parent_release_id="r1", author="a"
    )
    promoted = registry.promote(candidate, evidence=_evidence(candidate))
    old_run = registry.bind_run(
        {"release_id": "r1", "pinned_release_id": "r1"}
    )
    assert old_run["ok"] is True
    assert registry.live.release_id == promoted.release_id


def test_con_skl_11_revoke_pauses_and_rebinds():
    registry = _registry()
    result = registry.revoke("r1")
    assert result["running_tasks"] == "paused"
    assert result["requires_new_binding"] is True
    bound = registry.bind_run({"release_id": "r1"})
    assert bound["reason"] == "REVOKED_RELEASE"


def test_con_skl_12_small_sample_wide_interval_inconclusive():
    verdict = judge_candidate(
        verdict="inconclusive",
        safety_failures=0,
        actual_pairs=2,
        planned_pairs=5,
    )
    assert verdict.verdict == "inconclusive"
    assert verdict.eligible_for_review is False


def test_review_unknown_pinned_release_paused():
    registry = _registry()
    bound = registry.bind_run(
        {"release_id": "bogus", "pinned_release_id": "bogus"}
    )
    assert bound["ok"] is False
    assert bound["reason"] == "UNKNOWN_PINNED_RELEASE"
