"""WP18/WP19 R4-RC36 contract scenarios: isolated code deployment."""

from __future__ import annotations

import zipfile

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.dcode.package_build import (
    apply_copy,
    plan_copy,
)
from deepagents_code.cyrano.improvement.code_lane import (
    guard_self_edit,
    plan_migration,
    run_code_checks,
)


def _wheel(tmp_path, members):
    tmp_path.mkdir(parents=True, exist_ok=True)
    wheel = tmp_path / "cand-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name in members:
            archive.writestr(name, b"payload\n")
    return wheel


def test_rc36_01_isolated_build_running_files_immutable(tmp_path):
    live = tmp_path / "live"
    (live / "deepagents_code").mkdir(parents=True)
    (live / "deepagents_code" / "core.py").write_text(
        "orig = True\n", encoding="utf-8"
    )
    payload = tmp_path / "payload"
    (payload / "deepagents_code" / "cyrano").mkdir(parents=True)
    (payload / "deepagents_code" / "cyrano" / "lane.py").write_text(
        "new = 1\n", encoding="utf-8"
    )
    before = (live / "deepagents_code" / "core.py").read_bytes()
    apply_copy(plan_copy(payload, live))
    assert (live / "deepagents_code" / "core.py").read_bytes() == before
    assert (live / "deepagents_code" / "cyrano" / "lane.py").exists()


def test_rc36_02_protected_write_denied_with_audit_marker():
    decision = guard_self_edit("deepagents_code/cyrano/plugins/extension.py")
    assert decision.allowed is False
    assert decision.reason == "LIVE_PROCESS_FILE"
    pyproject = guard_self_edit("pyproject.toml")
    assert pyproject.allowed is False


def test_rc36_03_incompatible_schema_blocked_without_plan():
    with pytest.raises(CyranoError, match="ROLLBACK_PLAN_REQUIRED"):
        plan_migration(
            {"schema_change": "s2", "compatible_with_previous": False},
            restore_plan=None,
        )
    compatible = plan_migration(
        {"schema_change": "s2", "compatible_with_previous": True},
        restore_plan=None,
    )
    assert compatible.promotable is True


def test_rc36_04_wheel_missing_required_files_fails_smoke(tmp_path):
    wheel = _wheel(tmp_path, members=("deepagents_code/x.py",))
    evidence = run_code_checks(
        source_tests_passed=True,
        wheel_path=wheel,
        required_resources=(
            "deepagents_code/cyrano/__init__.py",
            "deepagents_code/cyrano/contracts/v1/cyrano.schema.json",
        ),
    )
    assert evidence.complete is False
    assert (
        "deepagents_code/cyrano/contracts/v1/cyrano.schema.json"
        in evidence.missing_resources
    )
    ok = _wheel(
        tmp_path / "ok",
        members=(
            "deepagents_code/cyrano/__init__.py",
            "deepagents_code/cyrano/contracts/v1/cyrano.schema.json",
        ),
    )
    passed = run_code_checks(
        source_tests_passed=True,
        wheel_path=ok,
        required_resources=(
            "deepagents_code/cyrano/__init__.py",
            "deepagents_code/cyrano/contracts/v1/cyrano.schema.json",
        ),
    )
    assert passed.complete is True
