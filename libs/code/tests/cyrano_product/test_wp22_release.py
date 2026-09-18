"""WP22 release tests: quality harness, packaging, install safety."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from deepagents_code.cyrano.cli.launch import (
    aggregate_ci_results,
    check_format_scope,
    find_swallowed_errors,
    guard_quality_recipe,
    normalize_test_outcome,
    sanitize_test_env,
    scan_package_contents,
    split_baseline_findings,
    validate_quality_config,
    validate_runtime_support,
    verify_install_nonmutation,
    verify_locked_install,
)
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.quality.policy import QualityPolicy
from deepagents_code.cyrano.quality.runner import (
    run_native_checks,
    snapshot_python_files,
)

CODE = Path(__file__).resolve().parents[2]


def test_uh_py_01_ruff_diagnostics_and_exit_code(tmp_path):
    """UH-PY-01: style violations produce diagnostics and an exit."""
    target = tmp_path / "bad.py"
    target.write_text("import os\nimport sys\nx=1\n")
    manifest = snapshot_python_files(tmp_path)
    policy = QualityPolicy(
        policy_id="p-ruff",
        tool="ruff",
        select=frozenset({"E", "F"}),
        line_length=79,
        max_doc_length=72,
        scope_patterns=("*.py",),
    )
    report = run_native_checks(manifest, policy, tmp_path)
    assert report.status == "FAIL"
    assert report.exit_code == 1
    assert report.diagnostics
    assert all(d.rule for d in report.diagnostics)


def test_uh_py_02_line_length_policy_is_explicit(tmp_path):
    """UH-PY-02: the harness 79 policy applies explicitly."""
    target = tmp_path / "long.py"
    target.write_text("x = '" + "a" * 90 + "'\n")
    manifest = snapshot_python_files(tmp_path)
    policy = QualityPolicy(
        policy_id="p-e501",
        tool="ruff",
        select=frozenset({"E501"}),
        line_length=79,
        max_doc_length=72,
        scope_patterns=("*.py",),
    )
    report = run_native_checks(manifest, policy, tmp_path)
    assert report.status == "FAIL"
    assert any(d.rule == "E501" for d in report.diagnostics)


def test_uh_py_03_report_never_claims_full_pep8():
    """UH-PY-03: a formatter pass alone never claims full PEP8."""
    report = Path("cyrano/evidence/quality.json")
    if report.is_file():
        data = __import__("json").loads(report.read_text())
        assert data["full_PEP8_compliance_claimed"] is False


def test_uh_py_04_two_formatters_conflict():
    """UH-PY-04: black and ruff-format together are a conflict."""
    with pytest.raises(CyranoError) as exc:
        validate_quality_config(["black", "ruff-format"])
    assert exc.value.code == "FORMATTER_CONFLICT"
    validate_quality_config(["ruff-format"])
    validate_quality_config(["black"])


def test_uh_py_05_zero_collected_tests_is_not_pass():
    """UH-PY-05: zero collected tests fail or need a stated N/A."""
    outcome = normalize_test_outcome(
        collected=0, passed=0, skipped=0, required=5
    )
    assert outcome["outcome"] == "failed"
    assert outcome["reason"] == "no_tests_collected"


def test_uh_py_06_all_skipped_required_does_not_count():
    """UH-PY-06: all-skipped required tests are not a pass."""
    outcome = normalize_test_outcome(
        collected=10, passed=0, skipped=10, required=10
    )
    assert outcome["outcome"] == "not_applicable"
    assert outcome["counts_as_required"] is False


def test_uh_py_07_baseline_new_findings_separated():
    """UH-PY-07: baseline and new violations stay distinct."""
    result = split_baseline_findings(
        current=["old.py:1", "new.py:5", "exc.py:9"],
        baseline=["old.py:1"],
        approved_exceptions=["exc.py:9"],
    )
    assert result["existing"] == ["old.py:1"]
    assert result["unapproved_new"] == ("new.py:5",)
    assert "exc.py:9" in result["excepted"]


def test_uh_py_08_format_scope_blocks_out_of_scope():
    """UH-PY-08: a recipe writing outside scope is refused."""
    with pytest.raises(CyranoError) as exc:
        check_format_scope(["a.py", "outside/b.py"], ["a.py", "c.py"])
    assert exc.value.code == "PATH_POLICY_VIOLATION"
    check_format_scope(["a.py"], ["a.py"])


def test_uh_py_09_swallowed_errors_are_found():
    """UH-PY-09: ``except: pass`` patterns are reported, not silent."""
    source = "try:\n    work()\nexcept Exception:\n    pass\n"
    lines = find_swallowed_errors(source)
    assert lines == (3,)
    bare = "try:\n    work()\nexcept:\n    pass\n"
    assert find_swallowed_errors(bare) == (3,)
    clean = "try:\n    work()\nexcept ValueError:\n    report()\n"
    assert find_swallowed_errors(clean) == ()


def test_uh_py_10_uh_ops_01_manifest_byte_identical():
    """UH-PY-10/UH-OPS-01: target manifests must not change."""
    before = {"a.py": "sha256:1", "b.py": "sha256:2"}
    verify_install_nonmutation(before, dict(before))
    with pytest.raises(CyranoError) as exc:
        verify_install_nonmutation(before, {"a.py": "sha256:9"})
    assert exc.value.code == "INSTALL_MUTATION"


def test_uh_ops_04_core_source_untouched():
    """UH-OPS-04: operations must not modify core source files."""
    core = {"deepagents_code/core.py": "sha256:aa"}
    verify_install_nonmutation(core, dict(core))
    with pytest.raises(CyranoError):
        verify_install_nonmutation(
            core, {"deepagents_code/core.py": "sha256:bb"}
        )


def test_peq_py_t51_gate_rewrite_blocked_by_digest():
    """PEQ-PY-T51: a changed gate recipe is blocked before running."""
    with pytest.raises(CyranoError) as exc:
        guard_quality_recipe("sha256:always0", "sha256:pinned")
    assert exc.value.code == "TRUST_MISMATCH"
    guard_quality_recipe("sha256:pinned", "sha256:pinned")


def test_peq_py_t52_required_job_skipped_fails_aggregate():
    """PEQ-PY-T52: a skipped required CI job fails the aggregate."""
    jobs = [
        {"name": "lint", "required": True, "conclusion": "skipped"},
        {"name": "docs", "required": False, "conclusion": "success"},
    ]
    result = aggregate_ci_results(jobs)
    assert result["aggregate"] == "failed"
    assert result["blocking_job"] == "lint"
    jobs[0]["conclusion"] = "success"
    assert aggregate_ci_results(jobs)["aggregate"] == "passed"


def test_peq_py_t53_install_requires_locked():
    """PEQ-PY-T53: installs run ``--locked``; no lock rewrites."""
    verify_locked_install(["uv", "sync", "--locked"])
    with pytest.raises(CyranoError) as exc:
        verify_locked_install(["uv", "sync"])
    assert exc.value.code == "POLICY_VIOLATION"


def test_peq_py_t54_test_env_injection_stripped():
    """PEQ-PY-T54: plugin/option injection is removed from the env."""
    env = sanitize_test_env(
        {
            "PYTEST_ADDOPTS": "--ignore=required",
            "PYTEST_PLUGINS": "evil_plugin",
            "PATH": "/usr/bin",
        }
    )
    assert "PYTEST_ADDOPTS" not in env
    assert "PYTEST_PLUGINS" not in env
    assert env["PATH"] == "/usr/bin"


def test_pack_native_unsupported_platform_refused():
    """PACK-NATIVE: unsupported platforms refuse, never degrade."""
    with pytest.raises(CyranoError) as exc:
        validate_runtime_support("plan9", ["linux", "darwin"])
    assert exc.value.code == "CAPABILITY_UNSUPPORTED"
    validate_runtime_support("linux", ["linux", "darwin"])


def test_pack_quality_missing_tools_is_blocked_not_green():
    """PACK-QUALITY: missing tools produce a blocked exit.

    The drill intentionally degrades PATH, so the real quality
    evidence it overwrites is restored afterwards — a blocked drill
    must not masquerade as the latest gate result.
    """
    evidence = CODE / "cyrano/evidence/quality.json"
    saved = evidence.read_bytes() if evidence.is_file() else None
    env = dict(os.environ)
    env["PATH"] = "/nonexistent-path-only"
    try:
        proc = subprocess.run(
            [sys.executable, "cyrano/scripts/quality.py"],
            cwd=CODE,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
    finally:
        if saved is not None:
            evidence.write_bytes(saved)
    assert proc.returncode == 2
    import json

    marker = proc.stdout.index("{")
    report = json.loads(proc.stdout[marker : proc.stdout.rindex("}") + 1])
    assert report["status"] == "blocked"
    assert sorted(report["missing"]) == ["ruff", "ty"]


def test_pack_isolated_no_absolute_path_dependency(tmp_path):
    """PACK-ISOLATED: packaged content needs no local paths."""
    source = tmp_path / "src"
    source.mkdir()
    (source / "mod.py").write_text("VALUE = 1\n")
    manifest = snapshot_python_files(source)
    policy = QualityPolicy(
        policy_id="p-iso",
        tool="ruff",
        select=frozenset({"E", "F"}),
        line_length=79,
        max_doc_length=72,
        scope_patterns=("*.py",),
    )
    report = run_native_checks(manifest, policy, source)
    assert report.status == "PASS"


def test_r5_rf10_02_secret_content_rejected_with_evidence():
    """R5-RF10-02: secrets in a wheel are rejected with evidence."""
    result = scan_package_contents(
        [
            "deepagents_code/cyrano/cli.py",
            "config/api_key.txt",
            "cyrano/evidence/holdout/cases.json",
        ]
    )
    assert result["accepted"] is False
    assert "config/api_key.txt" in result["rejected"]
    assert result["evidence"] == "wheel_content_scan"


def test_drill_gate_status_reads_real_evidence(tmp_path, monkeypatch):
    """Missing, malformed and blocked drill evidence never pass."""
    sys.path.insert(0, str(CODE / "cyrano" / "scripts"))
    import release_check  # noqa: E402

    monkeypatch.setattr(release_check, "ROOT", tmp_path)
    drills = tmp_path / "evidence" / "drills"
    drills.mkdir(parents=True)
    assert release_check.drill_gate_status("key_rotation") == "not_run"
    (drills / "key_rotation.json").write_text("not json")
    assert release_check.drill_gate_status("key_rotation") == "failed"
    record = {
        "kind": "executed_readiness_drill",
        "status": "passed",
        "cleanup_verified": True,
    }
    (drills / "key_rotation.json").write_text(json.dumps(record))
    assert release_check.drill_gate_status("key_rotation") == "passed"
    record["cleanup_verified"] = False
    (drills / "key_rotation.json").write_text(json.dumps(record))
    assert release_check.drill_gate_status("key_rotation") == "failed"
    record["status"] = "blocked"
    (drills / "key_rotation.json").write_text(json.dumps(record))
    assert release_check.drill_gate_status("key_rotation") == "blocked"
