"""WP17 unit checks: knowledge candidate validation edges."""

from __future__ import annotations

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.improvement.knowledge_lane import (
    validate_knowledge_candidate,
)


def _base(**kw):
    p = {
        "kind": "fact",
        "scope_id": "ws",
        "subject": "u",
        "evidence_refs": ["e"],
        "freshness_epoch": 1,
        "source_snapshot": "s",
    }
    p.update(kw)
    return p


def test_unknown_kind_refused():
    with pytest.raises(CyranoError, match="INPUT_INVALID"):
        validate_knowledge_candidate(_base(kind="rumor"))


def test_missing_evidence_refused():
    with pytest.raises(CyranoError, match="EVIDENCE_REQUIRED"):
        validate_knowledge_candidate(_base(evidence_refs=[]))


def test_missing_scope_or_subject_refused():
    with pytest.raises(CyranoError, match="INPUT_INVALID"):
        validate_knowledge_candidate(_base(scope_id=""))
    with pytest.raises(CyranoError, match="INPUT_INVALID"):
        validate_knowledge_candidate(_base(subject=""))


def test_procedure_needs_precondition():
    with pytest.raises(CyranoError, match="INPUT_INVALID"):
        validate_knowledge_candidate(
            _base(kind="procedure", source_snapshot=None)
        )
    ok = validate_knowledge_candidate(
        _base(
            kind="procedure",
            source_snapshot=None,
            precondition="db-not-migrated",
        )
    )
    assert ok.kind == "procedure"


def test_negative_freshness_refused():
    with pytest.raises(CyranoError, match="INPUT_INVALID"):
        validate_knowledge_candidate(_base(freshness_epoch=-1))
