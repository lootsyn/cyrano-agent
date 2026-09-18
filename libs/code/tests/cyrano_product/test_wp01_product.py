"""WP01 product tests: strict contracts, digests, references.

Each acceptance case from ``cyrano/tests`` runs against the real
parser, registry, and projection tables loaded from the checked-in
contract files — no fixture shortcuts substitute for validation.
"""

import json
from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.ingress import (
    parse_document,
)
from deepagents_code.cyrano.contracts.legacy import (
    derive_authority,
    inspect_legacy_approval,
    require_receipt_binding,
)
from deepagents_code.cyrano.contracts.projections import (
    ProjectionTable,
)
from deepagents_code.cyrano.contracts.references import (
    _cycles,
    validate_references,
)
from deepagents_code.cyrano.contracts.registry import (
    ContractRegistry,
)
from deepagents_code.cyrano.contracts.types import CyranoError

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "cyrano" / "contracts"
DIGEST = "sha256:" + "0" * 64


@pytest.fixture(scope="module")
def registry() -> ContractRegistry:
    return ContractRegistry.from_root(CONTRACTS)


@pytest.fixture(scope="module")
def table() -> ProjectionTable:
    return ProjectionTable.from_root(CONTRACTS)


def _value(field: str) -> object:
    if field.endswith("_digest") or field.endswith("_digests"):
        return DIGEST
    if field.endswith("_refs") or field in {
        "included",
        "bindings_list",
    }:
        return []
    if field in {"scope"}:
        return {"tenant": "t", "user": "u", "workspace": "w"}
    if field in {"bindings", "permission_set", "budget"}:
        return {}
    if field == "attestation":
        return {}
    return "x"


def _snake(type_name: str) -> str:
    out = []
    for char in type_name:
        if char.isupper() and out:
            out.append("_")
        out.append(char.lower())
    return "".join(out)


def _document(table: ProjectionTable, type_name: str, **over):
    rule = table.rule(type_name)
    doc = {field: _value(field) for field in rule.subject_fields}
    doc.update({field: _value(field) for field in rule.envelope_fields})
    doc["kind"] = _snake(type_name)
    doc["schema_version"] = "2.0" if rule.schema_version == "2" else "1.0"
    doc["id"] = f"{_snake(type_name)}-1"
    doc.update(over)
    return doc


class TestStrictIngress:
    """INTEG-JSON-STRICT and CONTRACT-FLOAT boundary rejections."""

    def test_duplicate_key_rejected(self):
        with pytest.raises(CyranoError) as exc:
            parse_document(b'{"a": 1, "a": 2}')
        assert exc.value.code == "STRICT_DUPLICATE_KEY"

    def test_float_and_nonfinite_rejected(self):
        for raw in (b'{"x": 0.1}', b'{"x": NaN}', b'{"x": Infinity}'):
            with pytest.raises(CyranoError) as exc:
                parse_document(raw)
            assert exc.value.code == "STRICT_NUMBER"

    def test_deep_nesting_rejected(self):
        raw = b'{"x":' + b"[" * 40 + b"1" + b"]" * 40 + b"}"
        with pytest.raises(CyranoError) as exc:
            parse_document(raw)
        assert exc.value.code == "STRICT_DEPTH"

    def test_oversize_rejected(self):
        with pytest.raises(CyranoError) as exc:
            parse_document(b'{"x": "aaaa"}', max_bytes=8)
        assert exc.value.code == "STRICT_SIZE"

    def test_surrogate_and_range_rejected(self):
        with pytest.raises(CyranoError) as exc:
            parse_document(b'{"\\ud800": 1}')
        assert exc.value.code == "STRICT_UNICODE"
        with pytest.raises(CyranoError) as exc:
            parse_document(b'{"x": 9007199254740993}')
        assert exc.value.code == "STRICT_RANGE"

    def test_syntax_and_non_object_rejected(self):
        with pytest.raises(CyranoError) as exc:
            parse_document(b'{"x": }')
        assert exc.value.code == "STRICT_SYNTAX"
        with pytest.raises(CyranoError) as exc:
            parse_document(b"[1, 2]")
        assert exc.value.code == "SCHEMA_INVALID"


class TestRegistry:
    """CONTRACT-UNKNOWN: explicit dispatch, no default inference."""

    def test_positive_session_query(self, registry):
        doc = registry.validate_document(
            b'{"kind": "session_query", "schema_version": "2.0",'
            b' "session_id": "s1", "expected_revision": 0}'
        )
        assert doc["kind"] == "session_query"

    def test_unknown_kind_rejected(self, registry):
        with pytest.raises(CyranoError) as exc:
            registry.validate_document(
                b'{"kind": "surprise", "schema_version": "2.0"}'
            )
        assert exc.value.code == "UNKNOWN_KIND"

    def test_future_version_rejected(self, registry):
        raw = (
            b'{"kind": "session_query", "schema_version": "9.9",'
            b' "session_id": "s1", "expected_revision": 0}'
        )
        with pytest.raises(CyranoError) as exc:
            registry.validate_document(raw)
        assert exc.value.code == "UNSUPPORTED_SCHEMA_VERSION"

    def test_unknown_field_rejected(self, registry):
        raw = (
            b'{"kind": "session_query", "schema_version": "2.0",'
            b' "session_id": "s1", "expected_revision": 0,'
            b' "debug": true}'
        )
        with pytest.raises(CyranoError) as exc:
            registry.validate_document(raw)
        assert exc.value.code == "SCHEMA_INVALID"

    def test_missing_kind_rejected(self, registry):
        with pytest.raises(CyranoError) as exc:
            registry.validate_document(b'{"schema_version": "2.0"}')
        assert exc.value.code == "SCHEMA_INVALID"

    def test_wrong_field_type_rejected(self, registry):
        raw = (
            b'{"kind": "session_query", "schema_version": "2.0",'
            b' "session_id": "s1", "expected_revision": "zero"}'
        )
        with pytest.raises(CyranoError) as exc:
            registry.validate_document(raw)
        assert exc.value.code == "SCHEMA_INVALID"

    def test_semantic_layer_enforced(self, registry):
        doc = {
            "kind": "memory_record",
            "schema_version": "1.0",
            "id": "m1",
            "scope": {
                "tenant": "t",
                "user": "u",
                "workspace": "w",
            },
            "memory_kind": "semantic",
            "status": "active",
            "title": "x",
            "content_digest": DIGEST,
            "evidence_refs": [],
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_until": "2026-02-01T00:00:00Z",
            "depends_on_digests": [],
            "valid_when": "always",
            "counterexamples": [],
            "supersedes": [],
            "approval_ref": None,
            "lineage_ids": [],
            "version": 1,
        }
        with pytest.raises(CyranoError) as exc:
            registry.validate_document(json.dumps(doc).encode())
        assert exc.value.code == "UNGROUNDED_MEMORY"


class TestSubjectDigests:
    """CONTRACT-RECEIPT and CONTRACT-SUBJECT digest semantics."""

    def test_envelope_change_keeps_subject(self, table):
        receipt = _document(table, "TrustedApprovalReceipt")
        signed = dict(receipt)
        signed["attestation"] = {
            "algorithm": "Ed25519",
            "key_id": "k1",
            "canonicalization": "CYRANO-C14N-1",
            "signature": "a" * 86,
        }
        first = table.binding_digest("TrustedApprovalReceipt", signed)
        other = dict(signed)
        other["attestation"] = {
            "algorithm": "Ed25519",
            "key_id": "k2",
            "canonicalization": "CYRANO-C14N-1",
            "signature": "b" * 86,
        }
        second = table.binding_digest("TrustedApprovalReceipt", other)
        assert first == second
        assert digest(signed) != digest(other)

    def test_body_change_breaks_binding(self, table):
        receipt = _document(table, "TrustedApprovalReceipt")
        tampered = dict(receipt, action="different_action")
        assert table.binding_digest(
            "TrustedApprovalReceipt", receipt
        ) != table.binding_digest("TrustedApprovalReceipt", tampered)

    def test_incomplete_envelope_rejected(self, table):
        receipt = _document(table, "TrustedApprovalReceipt")
        del receipt["attestation"]
        with pytest.raises(CyranoError) as exc:
            table.binding_digest("TrustedApprovalReceipt", receipt)
        assert exc.value.code == "INVALID_SUBJECT_FIELDS"


class TestReferences:
    """CONTRACT-DIGEST: cycles rejected; declared lineage allowed."""

    def test_allowed_lineage_has_no_findings(self, table):
        plan = _document(table, "LearningWorkPlan")
        candidate = _document(
            table,
            "CandidateProposal",
            learning_work_plan_digest=table.binding_digest(
                "LearningWorkPlan", plan
            ),
        )
        findings = validate_references(
            [plan, candidate],
            table,
            known_digests={DIGEST, "x"},
        )
        assert findings == []

    def test_reverse_reference_rejected(self, table):
        plan = _document(table, "ExperimentPlan")
        candidate = _document(
            table,
            "CandidateProposal",
            learning_work_plan_digest=table.binding_digest(
                "ExperimentPlan", plan
            ),
        )
        findings = validate_references(
            [plan, candidate],
            table,
            known_digests={DIGEST, "x"},
        )
        assert any(f.code == "FORBIDDEN_REFERENCE" for f in findings)

    def test_residual_cycle_detected(self):
        subjects = {"dg-a": {"id": "a"}, "dg-b": {"id": "b"}}
        edges = {"a": {"dg-b"}, "b": {"dg-a"}}
        findings = _cycles(subjects, edges)
        assert findings
        assert all(f.code == "CIRCULAR_IDENTITY" for f in findings)

    def test_candidate_cannot_reverse_reference(self, registry):
        raw = {
            "kind": "candidate_proposal",
            "schema_version": "1.0",
            "experiment_plan_digest": DIGEST,
        }
        with pytest.raises(CyranoError) as exc:
            registry.validate_document(json.dumps(raw).encode())
        assert exc.value.code == "SCHEMA_INVALID"

    def test_dangling_and_scope_mismatch(self, table):
        other_scope = {
            "tenant": "t",
            "user": "u",
            "workspace": "other",
        }
        target = _document(table, "LearningWorkPlan", scope=other_scope)
        candidate = _document(
            table,
            "CandidateProposal",
            learning_work_plan_digest=table.binding_digest(
                "LearningWorkPlan", target
            ),
            patch_digest="sha256:" + "f" * 64,
        )
        findings = validate_references(
            [target, candidate], table, known_digests={"x"}
        )
        codes = {f.code for f in findings}
        assert "SCOPE_MISMATCH" in codes
        assert "DANGLING_REFERENCE" in codes

    def test_digest_mismatch_reported(self, table):
        plan = _document(table, "LearningWorkPlan")
        candidate = _document(
            table,
            "CandidateProposal",
            learning_work_plan_digest=table.binding_digest(
                "LearningWorkPlan", plan
            ),
        )
        findings = validate_references(
            [plan, candidate],
            table,
            known_digests={DIGEST, "x"},
            expected={"learning_work_plan_digest": DIGEST},
        )
        assert any(f.code == "DIGEST_MISMATCH" for f in findings)


class TestLegacyConversion:
    """INTEG-AUTH-CONVERSION: preserved bytes, never authority."""

    def _permit_bytes(self) -> bytes:
        return json.dumps(
            {
                "kind": "permit",
                "schema_version": "1.0",
                "id": "legacy-1",
                "signature_ref": "sig:legacy",
            }
        ).encode()

    def test_legacy_bytes_preserved_not_executable(self):
        legacy = inspect_legacy_approval(self._permit_bytes())
        assert legacy.format == "permit_v1"
        assert legacy.raw.startswith(b'{"kind": "permit"')
        assert legacy.executable is False
        with pytest.raises(CyranoError) as exc:
            derive_authority(legacy)
        assert exc.value.code == "LEGACY_AUTHORITY"

    def test_receipt_without_binding_rejected(self):
        legacy = inspect_legacy_approval(self._permit_bytes())
        receipt = {
            "kind": "trusted_approval_receipt",
            "bindings": {"snapshot_digest": DIGEST},
        }
        with pytest.raises(CyranoError) as exc:
            require_receipt_binding(legacy, receipt)
        assert exc.value.code == "MISSING_RECEIPT_BINDING"

    def test_receipt_binding_returns_reference(self):
        legacy = inspect_legacy_approval(self._permit_bytes())
        receipt = {
            "kind": "trusted_approval_receipt",
            "bindings": {"snapshot_digest": legacy.raw_digest},
        }
        bound = require_receipt_binding(legacy, receipt)
        assert bound == legacy.raw_digest

    def test_non_receipt_cannot_bind(self):
        legacy = inspect_legacy_approval(self._permit_bytes())
        with pytest.raises(CyranoError) as exc:
            require_receipt_binding(legacy, {"kind": "permit", "bindings": {}})
        assert exc.value.code == "LEGACY_AUTHORITY"


class TestModuleBoundaries:
    """New WP01 error codes must not collide with other modules."""

    def test_codes_do_not_collide(self):
        import re

        import deepagents_code.cyrano as pkg

        new = {"ingress", "registry", "projections", "references", "legacy"}
        reused = {"UNKNOWN_SUBJECT_TYPE", "INVALID_SUBJECT_FIELDS"}
        new_codes: set[str] = set()
        pattern = re.compile(r'CyranoError\(\s*"([A-Z_]+)"')
        base = Path(pkg.__path__[0])
        by_file = {
            file: set(pattern.findall(file.read_text()))
            for file in base.rglob("*.py")
        }
        for file, codes in by_file.items():
            if file.stem in new:
                new_codes |= codes
        for file, codes in by_file.items():
            if file.stem not in new:
                collisions = (new_codes - reused) & codes
                assert not collisions, f"{file}: {collisions}"
