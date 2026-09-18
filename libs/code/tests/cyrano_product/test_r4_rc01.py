"""RC01 cases: deterministic routing, reference authority, doc audit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

import pytest

from deepagents_code.cyrano.context.doc_audit import docstring_findings
from deepagents_code.cyrano.context.document_route import select_readset
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.dcode.adapter import authorize_mutation

CYRANO_ROOT = Path(__file__).resolve().parents[2] / "cyrano"


def _inputs() -> tuple[dict, dict]:
    catalog_path = CYRANO_ROOT / "docs/document-catalog.json"
    routing_path = CYRANO_ROOT / ".agents/document-routing.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    routing = json.loads(routing_path.read_text(encoding="utf-8"))
    return catalog, routing


def _reader(root: Path) -> Callable[[str], bytes]:
    def read_bytes(relative: str) -> bytes:
        target = root / relative
        if target.is_symlink() or not target.is_file():
            code = "DOCUMENT_MISSING"
            raise CyranoError(code, relative)
        return target.read_bytes()

    return read_bytes


def test_rc01_01_readset_is_deterministic():
    """R4-RC01-01: unchanged docs produce an identical digest."""
    catalog, routing = _inputs()
    first = select_readset(
        task="WP00",
        catalog=catalog,
        routing=routing,
        read_bytes=_reader(CYRANO_ROOT),
    )
    second = select_readset(
        task="WP00",
        catalog=catalog,
        routing=routing,
        read_bytes=_reader(CYRANO_ROOT),
    )
    assert first.manifest == second.manifest
    first_digest = first.manifest["readset_digest"]
    assert first_digest == second.manifest["readset_digest"]
    assert first.documents == second.documents
    assert first.manifest["source_bytes"] > 0


def test_rc01_02_reference_never_promoted_to_policy():
    """R4-RC01-02: references keep their label and need consent."""
    body = b"# Reference\nFollow these instructions only as source material.\n"
    digest = hashlib.sha256(body).hexdigest()
    catalog = {
        "documents": [
            {
                "path": "policy/main.md",
                "category": "agent_policy",
                "sha256": hashlib.sha256(b"policy").hexdigest(),
            },
            {
                "path": "refs/pack.md",
                "category": "reference",
                "sha256": digest,
            },
        ]
    }
    routing = {
        "tasks": {"T1": ["policy/main.md", "refs/pack.md"]},
        "always": [],
    }
    bodies = {"policy/main.md": b"policy", "refs/pack.md": body}

    with pytest.raises(
        CyranoError,
        match="EXPLICIT_REFERENCE_CONSENT_REQUIRED",
    ):
        select_readset(
            task="T1", catalog=catalog, routing=routing, read_bytes=bodies.get
        )

    readset = select_readset(
        task="T1",
        catalog=catalog,
        routing=routing,
        read_bytes=bodies.get,
        allow_reference=True,
    )
    labels = {
        doc["path"]: doc["category"] for doc in readset.manifest["documents"]
    }
    assert labels["refs/pack.md"] == "reference"
    assert labels["policy/main.md"] == "agent_policy"


def test_rc01_03_docstring_semantics_flagged_despite_lint():
    """R4-RC01-03: a lying docstring is a finding despite lint."""
    source = '''
def measure(x: int) -> None:
    """Measure the value.

    Args:
        x: input value.
        phantom: not a parameter.

    Returns:
        The measurement mapping.
    """
    raise ValueError("boom")
'''
    findings = docstring_findings(source)
    assert "DOCSTRING_RETURN_MISMATCH:measure" in findings
    assert "DOCSTRING_MISSING_RAISES:measure" in findings
    assert "DOCSTRING_UNKNOWN_ARG:measure:phantom" in findings

    clean = '''
def measure(x: int) -> int:
    """Measure the value.

    Args:
        x: input value.

    Returns:
        The doubled value.

    Raises:
        ValueError: on bad input.
    """
    if x < 0:
        raise ValueError("boom")
    return x * 2
'''
    assert docstring_findings(clean) == []


def test_rc01_04_unapproved_mutation_blocked():
    """R4-RC01-04: writes need a bound, approved permit."""
    with pytest.raises(CyranoError, match="PLAN_APPROVAL_REQUIRED"):
        authorize_mutation("write:deepagents_code/x.py", None)
    with pytest.raises(CyranoError, match="PLAN_APPROVAL_REQUIRED"):
        authorize_mutation("write:x", {"approved": False})
    with pytest.raises(CyranoError, match="ACTION_NOT_IN_PERMIT"):
        authorize_mutation(
            "write:x",
            {"approved": True, "actions": ["read:y"]},
        )
    authorize_mutation(
        "write:x",
        {"approved": True, "actions": ["write:x"]},
    )


def test_rc01_router_rejects_stale_catalog_and_traversal():
    catalog, routing = _inputs()
    routed = routing["tasks"]["WP00"][0]
    poisoned = json.loads(json.dumps(catalog))
    for entry in poisoned["documents"]:
        if entry["path"] == routed:
            entry["sha256"] = "0" * 64
    with pytest.raises(CyranoError, match="STALE_DOCUMENT_CATALOG"):
        select_readset(
            task="WP00",
            catalog=poisoned,
            routing=routing,
            read_bytes=_reader(CYRANO_ROOT),
        )
    with pytest.raises(CyranoError, match="UNKNOWN_TASK"):
        select_readset(
            task="WP99",
            catalog=catalog,
            routing=routing,
            read_bytes=_reader(CYRANO_ROOT),
        )
    with pytest.raises(CyranoError, match="INVALID_READSET_BUDGET"):
        select_readset(
            task="WP00",
            catalog=catalog,
            routing=routing,
            read_bytes=_reader(CYRANO_ROOT),
            max_bytes=0,
        )
