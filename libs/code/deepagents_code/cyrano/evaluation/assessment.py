"""Pure assessment-data checks, not attestation or product scoring.

The real evaluator must authenticate producer identity, artifact
bindings, review authority, and run receipts before awarding credit.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

WEIGHTS = {
    "1-1": 3,
    "1-2": 3,
    "1-3": 4,
    "2-1": 2,
    "2-2": 3,
    "2-3": 3,
    "2-4": 2,
    "3-1": 2,
    "3-2": 3,
    "3-3": 3,
    "3-4": 2,
    "4-1": 3,
    "4-2": 3,
    "4-3": 2,
    "4-4": 2,
}
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
BINDINGS = ("source_digest", "runtime_digest", "policy_digest", "suite_digest")


def rubric_errors(rubric: Mapping, cases: list[dict]) -> list[str]:
    """Validate exact user weights and test membership.

    Args:
        rubric: Parsed local rubric document.
        cases: Canonical 90 newly designed grading cases.

    Returns:
        Stable diagnostic codes; empty means consistency is met.
    """
    errors: list[str] = []
    rows = rubric.get("criteria", [])
    ids = [item.get("id") for item in rows]
    if len(ids) != len(set(ids)):
        errors.append("DUPLICATE_CRITERION")
    if set(ids) != set(WEIGHTS):
        errors.append("CRITERION_SET_MISMATCH")
    case_ids = [item["id"] for item in cases]
    if len(case_ids) != len(set(case_ids)):
        errors.append("DUPLICATE_CASE")
    by_case = {item["id"]: item for item in cases}
    all_atoms: list[str] = []
    covered: set[str] = set()
    for item in rows:
        cid = item.get("id")
        weight = item.get("max_points")
        if type(weight) is not int or weight != WEIGHTS.get(cid):
            errors.append("WEIGHT_MISMATCH:" + str(cid))
        atoms = item.get("atoms", [])
        all_atoms += [atom.get("id", "") for atom in atoms]
        if (
            not atoms
            or any(type(a.get("points")) is not int for a in atoms)
            or sum(a.get("points", 0) for a in atoms) != weight
        ):
            errors.append("ATOM_TOTAL_MISMATCH:" + str(cid))
        refs = item.get("mandatory_case_ids", [])
        if not refs or len(refs) != len(set(refs)):
            errors.append("INVALID_CASE_SET:" + str(cid))
        for ref in refs:
            covered.add(ref)
            if ref not in by_case:
                errors.append("UNKNOWN_CASE:" + ref)
            elif by_case[ref].get("criterion_id") != cid:
                errors.append("CASE_CRITERION_MISMATCH:" + ref)
    if len(all_atoms) != len(set(all_atoms)):
        errors.append("DUPLICATE_ATOM")
    if rubric.get("maximum") != 40:
        errors.append("MAXIMUM_MISMATCH")
    if covered != set(case_ids):
        errors.append("UNCOVERED_CASES")
    return errors


def evidence_structure_errors(
    evidence: Mapping, expected_binding: Mapping, expected_cases: set[str]
) -> list[str]:
    """Reject incomplete or inconsistent exported evidence metadata.

    Signatures, access controls, raw artifacts, and facts are not
    verified here; this function is never an authorization or scorer.
    """
    errors: list[str] = []
    if evidence.get("schema_version") != "cyrano.assessment-evidence/3":
        errors.append("EVIDENCE_VERSION")
    if evidence.get("template_not_execution", False):
        errors.append("TEMPLATE_NOT_EVIDENCE")
    for name in BINDINGS:
        value = evidence.get(name)
        if (
            not isinstance(value, str)
            or not DIGEST.fullmatch(value)
            or value == "sha256:" + "0" * 64
        ):
            errors.append("INVALID_BINDING:" + name)
        if value != expected_binding.get(name):
            errors.append("STALE_BINDING:" + name)
    records = evidence.get("records", [])
    if not isinstance(records, list) or not records:
        return errors + ["EMPTY_EXECUTION_SET"]
    seen: set[str] = set()
    for record in records:
        cid = record.get("case_id")
        if cid in seen:
            errors.append("DUPLICATE_RESULT:" + str(cid))
        seen.add(cid)
        if cid not in expected_cases:
            errors.append("UNDECLARED_CASE:" + str(cid))
        if record.get("status") != "passed":
            errors.append("CASE_NOT_PASSED:" + str(cid))
        executed = record.get("tests_executed")
        if type(executed) is not int or executed <= 0:
            errors.append("NO_EXECUTED_TESTS:" + str(cid))
        if any(record.get(k, 0) for k in ("skipped", "xfailed", "deselected")):
            errors.append("MANDATORY_CASE_NOT_EXECUTED:" + str(cid))
        if not record.get("raw_artifact_refs"):
            errors.append("NO_RAW_ARTIFACTS:" + str(cid))
        if not record.get("review_ref"):
            errors.append("NO_INDEPENDENT_REVIEW:" + str(cid))
        if record.get("evidence_kind") in {"example", "self_report", "design"}:
            errors.append("NOT_EXECUTION_EVIDENCE:" + str(cid))
        for name in BINDINGS:
            if record.get(name) != evidence.get(name):
                errors.append("RECORD_BINDING_MISMATCH:" + str(cid))
    if expected_cases - seen:
        errors.append("MISSING_MANDATORY_CASES")
    return errors


def scorecard_template(rubric: Mapping) -> dict:
    """Return unassessed state; local tests are not product credit."""
    return {
        "schema_version": "cyrano.assessment-scorecard/3",
        "status": "not_evaluated",
        "official_score": None,
        "verified_points": 0,
        "maximum": 40,
        "release_eligible": False,
        "criteria": [
            {
                "id": row["id"],
                "max_points": row["max_points"],
                "points": 0,
                "status": "not_evaluated",
                "evidence_refs": [],
            }
            for row in rubric["criteria"]
        ],
        "limitation": "Local structural checks cannot award product credit.",
    }


#: Roles that may never read sealed detailed output — aggregate only.
_SEALED_DENIED_ROLES = frozenset({"author", "candidate", "agent"})


def read_sealed_output(
    bundle: Mapping, *, requester_role: str
) -> Mapping[str, object]:
    """Disclose sealed output under the aggregate-only policy.

    An author, candidate, or agent principal is denied the detailed
    sealed record — they receive the aggregate view and an explicit
    denial, not the raw rows.
    """
    if requester_role in _SEALED_DENIED_ROLES:
        return {
            "status": "denied",
            "disclosure": "aggregate_only",
            "detail": None,
        }
    return {
        "status": "ok",
        "disclosure": "full",
        "detail": bundle.get("detail"),
    }


def reconstruction_report(evidence: Mapping) -> Mapping[str, object]:
    """Report whether the record supports full reconstruction.

    A sensitive prompt body that was redacted at ingest cannot be
    reconstructed — the report says so instead of implying a complete
    record exists.
    """
    redacted = bool(evidence.get("prompt_body_redacted", False))
    return {
        "full_reconstruction": not redacted,
        "redacted_fields": ("prompt_body",) if redacted else (),
    }


def tamper_evidence_scope(has_trusted_head: bool) -> Mapping[str, object]:
    """Declare how far integrity verification reaches.

    Without a trusted hash-chain head the verifier can detect only
    intra-bundle inconsistency — the boundary is declared, not hidden.
    """
    return {
        "chain_anchor": has_trusted_head,
        "tamper_evidence_scope": (
            "full_chain" if has_trusted_head else "intra_bundle_only"
        ),
    }


def bind_baseline_failures(
    baseline_failures: Iterable[str],
    candidate_cases: Iterable[str],
) -> Mapping[str, object]:
    """Bind pre-existing failures to the cases they affect.

    A candidate cannot claim improvement on a case the baseline
    already failed — those cases stay blocked rather than counted
    as regressions or ignored.
    """
    failed = frozenset(map(str, baseline_failures))
    cases = frozenset(map(str, candidate_cases))
    affected = sorted(failed & cases)
    return {
        "affected": tuple(affected),
        "blocked": bool(affected),
    }


def dedupe_dataset(
    sources: Iterable[Iterable[str]],
) -> Mapping[str, object]:
    """Merge case lists; identical case ids share one obligation.

    The same case appearing in two sources is one family/obligation —
    duplication never inflates the independent sample count.
    """
    seen: set[str] = set()
    duplicates: set[str] = set()
    for source in sources:
        for case_id in source:
            cid = str(case_id)
            if cid in seen:
                duplicates.add(cid)
            seen.add(cid)
    return {
        "cases": tuple(sorted(seen)),
        "independent_count": len(seen),
        "deduplicated": tuple(sorted(duplicates)),
    }
