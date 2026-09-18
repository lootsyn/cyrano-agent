"""WP22 product tests: feature stages, compatibility, readiness."""

import pytest

from deepagents_code.cyrano.cli.launch import (
    check_enable_combination,
    check_promotion_evidence,
    check_reader_compatibility,
    check_writer_compatibility,
    collect_release_readiness,
    evaluate_release_eligibility,
    launch_preflight,
    license_inventory,
    plan_release_package,
    plan_shadow_execution,
    record_upstream_observation,
    resolve_feature_state,
    restore_with_deletions,
    staged_migration,
    verify_wheel_assets,
)
from deepagents_code.cyrano.contracts.types import CyranoError


def test_con_mig_01_unconfigured_feature_is_off():
    """CON-MIG-01: a missing feature config resolves to disabled."""
    state = resolve_feature_state("new_memory_selection", {})
    assert state.stage == "off"
    assert state.configured is False
    assert "not_configured" in state.blocked_reasons


def test_con_mig_01_unknown_stage_rejected():
    """CON-MIG-01: a stage outside the ladder is never coerced."""
    with pytest.raises(CyranoError) as exc:
        resolve_feature_state("f", {"f": {"stage": "mostly_on"}})
    assert exc.value.code == "FEATURE_STAGE_UNKNOWN"


def test_con_mig_02_shadow_real_effects_refused():
    """CON-MIG-02: shadow runs may not duplicate real side effects."""
    feature = resolve_feature_state(
        "push_agent", {"push_agent": {"stage": "isolated_shadow"}}
    )
    plan = plan_shadow_execution(feature, ["write", "push"])
    assert plan["allowed"] is False
    assert set(plan["effects"]) == {"write", "push"}


def test_con_mig_02_shadow_no_effect_allowed():
    """CON-MIG-02: an isolated, no-effect shadow plan is allowed."""
    feature = resolve_feature_state(
        "dry_compare", {"dry_compare": {"stage": "isolated_shadow"}}
    )
    plan = plan_shadow_execution(feature, [])
    assert plan["allowed"] is True
    assert plan["mode"] == "isolated_no_effect"


def test_con_mig_03_combination_needs_interaction_eval():
    """CON-MIG-03: two solo-verified features need interaction eval."""
    result = check_enable_combination(
        ["mem_sel", "provider_tx"],
        ["mem_sel", "provider_tx"],
        [],
    )
    assert result["allowed"] is False
    assert result["requires_interaction_eval"]
    covered = check_enable_combination(
        ["mem_sel", "provider_tx"],
        ["mem_sel", "provider_tx"],
        [("mem_sel", "provider_tx")],
    )
    assert covered["allowed"] is True


def test_con_mig_04_old_reader_new_record_version_conflict():
    """CON-MIG-04: an old reader on a new record is VERSION_CONFLICT."""
    with pytest.raises(CyranoError) as exc:
        check_reader_compatibility(2, 3)
    assert exc.value.code == "VERSION_CONFLICT"
    check_reader_compatibility(3, 3)


def test_con_mig_05_failed_migration_never_commits_partial():
    """CON-MIG-05: a mid-migration failure preserves the original."""
    records = [{"v": 1}, {"v": 2}, {"v": 3}]

    def transform(record):
        if record["v"] == 2:
            raise ValueError("corrupt record")
        return {"v": record["v"], "migrated": True}

    result = staged_migration(records, transform)
    assert result.committed is False
    assert result.failed_at == 1
    assert result.original_preserved is True

    ok = staged_migration(records, lambda r: {"v": r["v"]})
    assert ok.committed and ok.converted == 3


def test_con_mig_06_old_writer_new_db_migration_required():
    """CON-MIG-06: an old binary on a new DB needs MIGRATION_REQUIRED."""
    with pytest.raises(CyranoError) as exc:
        check_writer_compatibility(4, 5)
    assert exc.value.code == "MIGRATION_REQUIRED"
    check_writer_compatibility(5, 5)


def test_con_mig_08_upstream_release_is_record_only():
    """CON-MIG-08: a newer upstream is logged, never auto-adopted."""
    note = record_upstream_observation("0.1.70", "0.1.69")
    assert note["action"] == "record_only"
    assert note["requires_separate_review"] is True
    same = record_upstream_observation("0.1.69", "0.1.69")
    assert same["requires_separate_review"] is False


def test_con_mig_09_unconfirmed_license_defers_inclusion():
    """CON-MIG-09: a package without license data is deferred."""
    result = license_inventory(
        [
            {"name": "serena-agent", "license": None},
            {"name": "solid", "license": "MIT"},
        ]
    )
    assert result["complete"] is False
    assert result["deferred"] == ("serena-agent",)
    assert result["decision"] == "blocked"


def test_con_mig_10_generated_state_excluded_from_package():
    """CON-MIG-10: state dirs and caches never ship in a release."""
    plan = plan_release_package(
        [
            "deepagents_code/cyrano/cli/launch.py",
            "tools/.state/corpus/wp22/blob",
            "node_modules/pkg/index.js",
            "cyrano/contracts/v1/cyrano.schema.json",
        ]
    )
    assert "deepagents_code/cyrano/cli/launch.py" in plan["included"]
    assert "tools/.state/corpus/wp22/blob" in plan["excluded"]
    assert "node_modules/pkg/index.js" in plan["excluded"]


def test_con_mig_11_hash_mismatch_is_stale_evidence():
    """CON-MIG-11: candidate vs evidence hash drift blocks CAS."""
    with pytest.raises(CyranoError) as exc:
        check_promotion_evidence("sha256:aaa", "sha256:bbb")
    assert exc.value.code == "STALE_EVIDENCE"
    check_promotion_evidence("sha256:aaa", "sha256:aaa")


def test_con_mig_12_security_regression_is_hard_fail():
    """CON-MIG-12: a success-rate gain never offsets a bypass."""
    scorecard = {
        "criteria": [
            {"id": "1-1", "status": "evaluated", "points": 3},
            {"id": "1-2", "status": "evaluated", "points": 3},
        ]
    }
    result = evaluate_release_eligibility(
        scorecard, ["unapproved_write_detected"]
    )
    assert result["release_eligible"] is False
    assert "unapproved_write_detected" in result["hard_failures"]


def test_integ_missing_evidence_fixture_scores_zero():
    """INTEG-MISSING-EVIDENCE: fixtures never award product points."""
    criteria = [
        {"id": "1-1", "maximum": 3},
        {"id": "1-2", "maximum": 3},
    ]
    scorecard = collect_release_readiness(criteria, {})
    assert scorecard["verified_points"] == 0
    assert all(r["status"] == "not_evaluated" for r in scorecard["criteria"])


def test_integ_rubric_hard_points_never_offset_bypass():
    """INTEG-RUBRIC-HARD: a high total cannot cancel a hard failure."""
    criteria = [{"id": "1-1", "maximum": 3}]
    scorecard = collect_release_readiness(
        criteria,
        {"1-1": {"verified": True, "reviewed": True, "refs": ["e1"]}},
    )
    assert scorecard["verified_points"] == 3
    result = evaluate_release_eligibility(scorecard, ["approval_bypass"])
    assert result["release_eligible"] is False


def test_integ_assurance_offline_demo_is_not_governed():
    """INTEG-ASSURANCE: advisory runs never prove governed readiness."""
    result = launch_preflight(
        {"feature_x": {"stage": "enabled"}},
        {"offline_demo": True},
    )
    assert result["governed_ready"] is False
    assert result["advisory_only"] is True
    governed = launch_preflight(
        {"feature_x": {"stage": "enabled"}},
        {"same_uid_sandbox": True, "governed_run": True},
    )
    assert governed["governed_ready"] is True


def test_unmet_gate_blocks_eligibility():
    """An unexecuted required gate blocks release eligibility."""
    scorecard = {
        "criteria": [{"id": "1-1", "status": "evaluated", "points": 3}]
    }
    result = evaluate_release_eligibility(
        scorecard, [], {"clean_env_install": "not_run"}
    )
    assert result["release_eligible"] is False
    assert "clean_env_install" in result["unmet_gates"]


def test_wheel_asset_missing_named_no_fallback():
    """A missing wheel asset is named; no source fallback exists."""
    result = verify_wheel_assets(["pkg/a.py", "pkg/data.json"], ["pkg/a.py"])
    assert result["complete"] is False
    assert result["missing"] == ("pkg/data.json",)
    assert result["source_fallback"] is False


def test_restore_replays_tombstones_and_blocks_old_writer():
    """Restores replay deletions before activation; old writers stop."""
    backup = [{"id": "m1"}, {"id": "m2"}, {"id": "m3"}]
    tombstones = [{"target": "m2"}]
    result = restore_with_deletions(backup, tombstones, 5, 5)
    assert result["restored"] == 2
    assert result["tombstones_replayed"] == 1
    with pytest.raises(CyranoError) as exc:
        restore_with_deletions(backup, tombstones, 4, 5)
    assert exc.value.code == "MIGRATION_REQUIRED"
