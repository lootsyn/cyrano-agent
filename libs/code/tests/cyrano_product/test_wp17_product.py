"""WP17 product cases: knowledge lane and skill lane obligations."""

from __future__ import annotations

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.improvement.knowledge_lane import (
    apply_recipe,
    evaluate_memory_pairs,
    promote_scope,
    validate_knowledge_candidate,
)
from deepagents_code.cyrano.improvement.skill_lane import (
    SkillRegistry,
    SkillRelease,
    check_skill_impact,
    propose_skill_candidate,
)


def _fact(**kw):
    p = {
        "kind": "fact",
        "scope_id": "ws-1",
        "subject": "u1",
        "evidence_refs": ["ev1"],
        "freshness_epoch": 3,
        "source_snapshot": "snap-1",
    }
    p.update(kw)
    return p


# -- B-FACT / B-PREF ---------------------------------------------------


def test_b_fact_snapshot_scope_authority_no_global():
    candidate = validate_knowledge_candidate(_fact())
    assert candidate.scope_id == "ws-1"
    with pytest.raises(CyranoError, match="SCOPE_DENIED"):
        validate_knowledge_candidate(_fact(generalize=True))
    with pytest.raises(CyranoError, match="EVIDENCE_REQUIRED"):
        validate_knowledge_candidate(_fact(source_snapshot=None))


def test_b_pref_trusted_subject_supersedes_own_only():
    prior = {"subject": "u1", "kind": "preference"}
    ok = validate_knowledge_candidate(
        _fact(
            kind="preference",
            supersedes="mem-1",
            trusted=True,
        ),
        superseded=prior,
    )
    assert ok.supersedes == "mem-1"
    with pytest.raises(CyranoError, match="SCOPE_DENIED"):
        validate_knowledge_candidate(
            _fact(
                kind="preference",
                supersedes="mem-1",
                trusted=True,
            ),
            superseded={"subject": "u2", "kind": "preference"},
        )
    with pytest.raises(CyranoError, match="PERMISSION_DENIED"):
        validate_knowledge_candidate(
            _fact(kind="preference", supersedes="mem-1"),
            superseded=prior,
        )


def test_b_skill_reads_up_accuracy_down_not_offset():
    evidence = evaluate_memory_pairs(
        exposures=[{"memory_id": "m1"}, {"memory_id": "m1"}],
        outcomes=[{"status": "success", "applied_memories": []}],
    )
    assert evidence["exposed"] == 1
    assert evidence["causal"] == 0
    assert evidence["correlated_only"] == 1
    assert evidence["promotable"] is False


def test_b_negative_done_migration_applies_conditionally():
    recipe = {"precondition": "db-migrated"}
    done = apply_recipe(recipe, environment={"completed": ["db-migrated"]})
    assert done.applied is False
    assert done.reason == "already_satisfied"
    fresh = apply_recipe(recipe, environment={"completed": []})
    assert fresh.applied is True


def test_uh_mem_12_workspace_lesson_global_needs_eval():
    candidate = validate_knowledge_candidate(_fact())
    with pytest.raises(CyranoError, match="SCOPE_DENIED"):
        promote_scope(
            candidate, to_scope="global", evaluation=None, approval="a1"
        )
    promoted = promote_scope(
        candidate,
        to_scope="global",
        evaluation={"scope_evaluated": True, "scope_id": "global"},
        approval="ap-9",
    )
    assert promoted.scope_id == "global"


# -- skill lane integration --------------------------------------------


def _release(rev="r1"):
    return SkillRelease("skill-1", rev, None, "sha256:c1", "active")


def _candidate(registry):
    return propose_skill_candidate(
        {
            "repeats": 3,
            "scope_id": "ws-1",
            "counterexamples": ["ce1"],
            "body": "when tests fail, read the error first",
        },
        skill_id="skill-1",
        parent_release_id=registry.live.release_id,
        author="agent",
    )


def test_wp17_i02_code_vs_wording_classification():
    impact = check_skill_impact(
        ["skills/x/resources/helper.py"],
        claimed_kind="wording",
        input_semantics_unchanged=False,
        policy_ir_validated=False,
    )
    assert impact["actual_kind"] == "code"
    assert impact["route"] == "high_risk_review"


def test_wp17_i03_revoked_release_pauses_running():
    registry = SkillRegistry(_release())
    candidate = _candidate(registry)
    promoted = registry.promote(
        candidate,
        evidence={
            "kind": "actual_paired",
            "body_digest": candidate.content_digest,
        },
    )
    registry.revoke(promoted.release_id)
    bound = registry.bind_run({"release_id": promoted.release_id})
    assert bound["ok"] is False
    assert bound["state"] == "paused"
    assert bound["reason"] == "REVOKED_RELEASE"
