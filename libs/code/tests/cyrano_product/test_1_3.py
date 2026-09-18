"""R3-13: docstring and comment content review (semantic, not lint)."""

from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.dcode.bridge import start_verified_runtime
from deepagents_code.cyrano.quality.documentation import (
    check_docstring_signature,
    inventory_public_symbols,
    run_semantic_review,
)

GOOD = (
    'def transfer(source: str, target: str) -> int:\n'
    '    """Move bytes between files.\n\n'
    "    Args:\n        source: origin path\n"
    "        target: destination path\n\n"
    "    Returns:\n        bytes moved\n\n"
    "    Raises:\n        OSError: on IO failure\n"
    '    """\n'
    "    raise OSError\n"
)
MISSING_DOC = "def authorize(user):\n    return check(user)\n"
STALE_ARGS = (
    'def send(payload, retries):\n'
    '    """Send.\n\n'
    "    Args:\n        old_param: removed last week\n"
    '    """\n    return payload\n'
)
PLACEHOLDER = 'def ingest(stream):\n    """TODO"""\n    return stream\n'
NOQA_IN_DOC = (
    'def f() -> int:\n    """See noqa note # noqa: F401."""\n'
    "    return 1\n"
)


def test_r3_13_01(tmp_path: Path):
    """A correctly documented public API produces no findings."""
    path = tmp_path / "api.py"
    path.write_text(GOOD)
    review = run_semantic_review([path])
    assert review.findings == ()
    assert review.symbol_count >= 1


def test_r3_13_02(tmp_path: Path):
    """A public function without a docstring is a finding."""
    path = tmp_path / "m.py"
    path.write_text(MISSING_DOC)
    findings = check_docstring_signature(path)
    assert any(f.code == "DOCSTRING_MISSING" for f in findings)


def test_r3_13_03(tmp_path: Path):
    """Args documented against an old signature are flagged."""
    path = tmp_path / "m.py"
    path.write_text(STALE_ARGS)
    findings = check_docstring_signature(path)
    assert any(
        f.code == "DOCSTRING_UNKNOWN_ARG" and "old_param" in f.detail
        for f in findings
    )


def test_r3_13_04(tmp_path: Path):
    """A TODO or name-echo docstring is a placeholder finding."""
    path = tmp_path / "m.py"
    path.write_text(PLACEHOLDER)
    findings = check_docstring_signature(path)
    assert any(f.code == "DOCSTRING_PLACEHOLDER" for f in findings)


def test_r3_13_05(tmp_path: Path):
    """A suppression directive inside docstring text is flagged."""
    path = tmp_path / "m.py"
    path.write_text(NOQA_IN_DOC)
    findings = check_docstring_signature(path)
    assert any(f.code == "SUPPRESSION_IN_TEXT" for f in findings)


def test_r3_13_06():
    """Native tool registration requires a verified runtime.

    The live schema-registration path stays not-run; unverified
    probes refuse a runtime handle.
    """
    with pytest.raises(CyranoError) as exc:
        start_verified_runtime({}, "lock")
    assert exc.value.code == "DCODE_RUNTIME_NOT_VERIFIED"


def test_inventory_records_inclusion_rule(tmp_path: Path):
    """The inventory manifest records which symbols were selected."""
    path = tmp_path / "m.py"
    path.write_text(GOOD)
    inv = inventory_public_symbols([path])
    assert inv.inclusion_rule
    assert any(e.name == "transfer" for e in inv.entries)
