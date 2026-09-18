"""R3-11: style and formatting via the real native checker."""

from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.dcode.bridge import start_verified_runtime
from deepagents_code.cyrano.quality import (
    QualityPolicy,
    resolve_quality_policy,
    run_native_checks,
    snapshot_python_files,
)

CLEAN = 'def add(a: int, b: int) -> int:\n    """Add two integers."""\n    return a + b\n'
TABS = "def f():\n\treturn 1\n"
TRAILING = "x = 1   \n\n\n\ndef f():\n    pass"
LONG_COMMENT = (
    "# " + "word " * 20 + "\n"
    "# https://example.com/" + "a" * 80 + "\n"
    "x = 1\n"
)


def _policy(**over) -> QualityPolicy:
    config = {"tool": "ruff", "scope": ["*.py"], "line_length": 79}
    config.update(over)
    return resolve_quality_policy(config)


def test_r3_11_01(tmp_path: Path):
    """A clean, correctly formatted file passes."""
    (tmp_path / "m.py").write_text(CLEAN)
    manifest = snapshot_python_files(tmp_path)
    report = run_native_checks(
        manifest, _policy(select=["E", "W", "F"]), tmp_path
    )
    assert report.status == "PASS"


def test_r3_11_02(tmp_path: Path):
    """Mixed tab/space indentation is diagnosed."""
    (tmp_path / "m.py").write_text(TABS)
    report = run_native_checks(
        snapshot_python_files(tmp_path),
        _policy(select=["W", "E1"]),
        tmp_path,
    )
    assert report.status == "FAIL"
    assert any(
        d.rule in {"W191", "E101"} for d in report.diagnostics
    )


def test_r3_11_03(tmp_path: Path):
    """Trailing space and excess blank lines are diagnosed."""
    (tmp_path / "m.py").write_text(TRAILING)
    report = run_native_checks(
        snapshot_python_files(tmp_path),
        _policy(select=["W291", "W292", "E303"]),
        tmp_path,
    )
    assert report.status == "FAIL"
    assert {d.rule for d in report.diagnostics} & {"W291", "E303"}


def test_r3_11_04(tmp_path: Path):
    """Under the 79/72 policy a long comment is W505; a URL is exempt."""
    (tmp_path / "m.py").write_text(LONG_COMMENT)
    policy = _policy(select=["W505"], max_doc_length=72)
    report = run_native_checks(
        snapshot_python_files(tmp_path), policy, tmp_path
    )
    w505 = [d for d in report.diagnostics if d.rule == "W505"]
    assert w505
    assert all("example.com" not in d.message for d in w505)


def test_r3_11_05():
    """Two authoritative formatter policies refuse to merge."""
    black = {
        "tool": "ruff-format", "scope": ["*.py"], "authoritative": True
    }
    ruff = {
        "tool": "ruff-format", "scope": ["*.py"], "authoritative": True
    }
    with pytest.raises(CyranoError) as exc:
        resolve_quality_policy([black, ruff])
    assert exc.value.code == "POLICY_CONFIG_MISMATCH"


def test_r3_11_06():
    """Live dcode authoring is refused without a verified runtime.

    The component gate is real: an unverified probe report cannot
    mint a runtime handle. The live authoring path stays not-run.
    """
    with pytest.raises(CyranoError) as exc:
        start_verified_runtime({}, "lock")
    assert exc.value.code == "DCODE_RUNTIME_NOT_VERIFIED"
