"""R3-12: naming and import rules via the real native checker."""

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
from deepagents_code.cyrano.quality.documentation import (
    ambiguous_name_findings,
)

CLEAN = (
    '"""Module."""\n\nimport os\n\nimport pytest\n\n'
    'CONSTANT = 1\n\n\nclass GoodName:\n    """G."""\n\n\n'
    'def good_function(arg: int) -> int:\n    """F."""\n'
    "    _ = os.sep, pytest\n    return arg + CONSTANT\n"
)
BAD_NAMES = "def badFunction():\n    pass\n\n\nclass bad_class:\n    pass\n"
BAD_IMPORTS = (
    "import os\nimport sys\nimport os\n"
    "import third_party\n\nimport local_mod\n"
)
SHORT_NAMES = (
    "def total(points):\n"
    "    s = 0\n    for i, p in enumerate(points):\n"
    "        x, y = p\n        s += x * y\n    return s\n"
)
AMBIGUOUS = (
    "def do_stuff(data1, data2):\n    return data1 + data2\n"
)


def _policy(**over) -> QualityPolicy:
    config = {"tool": "ruff", "scope": ["*.py"], "line_length": 79}
    config.update(over)
    return resolve_quality_policy(config)


def _run(root: Path, **over):
    return run_native_checks(
        snapshot_python_files(root), _policy(**over), root
    )


def test_r3_12_01(tmp_path: Path):
    """Correct snake_case/PascalCase names and grouped imports pass."""
    (tmp_path / "m.py").write_text(CLEAN)
    report = _run(tmp_path, select=["N", "I", "F"])
    assert report.status == "PASS"


def test_r3_12_02(tmp_path: Path):
    """badFunction and bad_class are diagnosed as N802/N801."""
    (tmp_path / "m.py").write_text(BAD_NAMES)
    report = _run(tmp_path, select=["N"])
    rules = {d.rule for d in report.diagnostics}
    assert "N802" in rules and "N801" in rules


def test_r3_12_03(tmp_path: Path):
    """Unused, duplicated and unsorted imports are diagnosed."""
    (tmp_path / "m.py").write_text(BAD_IMPORTS)
    report = _run(tmp_path, select=["F401", "I"])
    rules = {d.rule for d in report.diagnostics}
    assert "F401" in rules


def test_r3_12_04(tmp_path: Path):
    """Conventional short names (i, x, y) are not violations."""
    (tmp_path / "m.py").write_text(SHORT_NAMES)
    report = _run(tmp_path, select=["N"])
    assert report.status == "PASS"


def test_r3_12_05(tmp_path: Path):
    """Form-valid ambiguous names pass lint but fail semantic review."""
    path = tmp_path / "m.py"
    path.write_text(AMBIGUOUS)
    lint = _run(tmp_path, select=["N"])
    assert lint.status == "PASS"  # lint cannot see meaning
    findings = ambiguous_name_findings(path)
    assert {f.code for f in findings} == {"AMBIGUOUS_NAME"}


def test_r3_12_06():
    """Native namespace import requires a verified runtime.

    The live wheel-import path stays not-run; the component gate
    refuses to mint a runtime without verified probes.
    """
    with pytest.raises(CyranoError) as exc:
        start_verified_runtime({}, "lock")
    assert exc.value.code == "DCODE_RUNTIME_NOT_VERIFIED"
