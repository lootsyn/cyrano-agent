"""Cross-document reference checks: dangling, scope, digest, type.

Subject digests identify signable bodies. A document may reference
only digests that exist in the supplied document set or the caller's
known-digest ledger, scopes must match, lineage fields must resolve
to their declared target types, and residual cycles are rejected.
"""

from dataclasses import dataclass
from typing import Iterable, Mapping

from deepagents_code.cyrano.contracts.ingress import JSON
from deepagents_code.cyrano.contracts.projections import (
    ProjectionTable,
)
from deepagents_code.cyrano.contracts.types import CyranoError

REFERENCE_SUFFIXES = ("_digest", "_digests", "_ref", "_refs")

# Declared target types for lineage/authority digest fields. Content
# digests (patch, artifact, snapshot, …) carry no subject type and
# are checked only for dangling/scope, never for target type.
_REFERENCE_TARGETS: dict[str, frozenset[str]] = {
    "learning_work_plan_digest": frozenset({"LearningWorkPlan"}),
    "candidate_digest": frozenset({"CandidateProposal"}),
    "candidate_input_digest": frozenset({"CandidateProposal"}),
    "experiment_plan_digest": frozenset({"ExperimentPlan"}),
    "baseline_release_digest": frozenset({"HarnessRelease"}),
    "baseline_input_digest": frozenset({"HarnessRelease"}),
    "parent_release_digest": frozenset({"HarnessRelease"}),
    "rollback_release_digest": frozenset({"HarnessRelease"}),
    "release_digest": frozenset({"HarnessRelease"}),
    "release_subject_digest": frozenset({"HarnessRelease"}),
    "contract_digest": frozenset({"InterviewContract"}),
    "contract_subject_digest": frozenset({"InterviewContract"}),
    "work_plan_subject_digest": frozenset({"GovernedWorkPlan"}),
    "memory_subject_digest": frozenset({"MemoryRecord"}),
    "depends_on_digests": frozenset({"MemoryRecord"}),
}


@dataclass(frozen=True, slots=True)
class ReferenceFinding:
    """One typed reference defect; callers reject on any findings."""

    code: str
    document_id: str
    field: str
    detail: str


def _ref_values(
    document: Mapping[str, JSON],
) -> Iterable[tuple[str, str]]:
    for key, value in document.items():
        if key.endswith("_digest") and isinstance(value, str):
            yield key, value
        elif key.endswith("_digests") and isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    yield key, item
        elif key.endswith("_ref") and isinstance(value, str):
            yield key, value
        elif key.endswith("_refs") and isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    yield key, item


def _doc_id(document: Mapping[str, JSON]) -> str:
    value = document.get("id")
    return str(value) if value is not None else "<no-id>"


def _type_name(document: Mapping[str, JSON]) -> str:
    kind = document.get("kind")
    if not isinstance(kind, str):
        return ""
    return "".join(part.capitalize() for part in kind.split("_"))


def _scope_key(document: Mapping[str, JSON]) -> object:
    scope = document.get("scope")
    if not isinstance(scope, dict):
        return None
    return tuple(str(scope.get(k)) for k in ("tenant", "user", "workspace"))


def _subject_digests(
    docs: list[Mapping[str, JSON]], table: ProjectionTable
) -> dict[str, Mapping[str, JSON]]:
    subjects: dict[str, Mapping[str, JSON]] = {}
    for doc in docs:
        type_name = _type_name(doc)
        if not type_name:
            continue
        try:
            rule = table.rule(type_name)
        except CyranoError:
            continue
        try:
            subjects[table.binding_digest(rule.type_name, doc)] = doc
        except CyranoError:
            continue
    return subjects


def validate_references(
    documents: Iterable[Mapping[str, JSON]],
    table: ProjectionTable,
    *,
    known_digests: Iterable[str] = (),
    expected: Mapping[str, str] | None = None,
) -> list[ReferenceFinding]:
    """Return dangling, scope, digest and identity findings."""
    docs = list(documents)
    subjects = _subject_digests(docs, table)
    known = set(known_digests) | set(subjects)
    findings: list[ReferenceFinding] = []
    edges: dict[str, set[str]] = {}
    for doc in docs:
        doc_id = _doc_id(doc)
        refs: set[str] = set()
        for field, value in _ref_values(doc):
            refs.add(value)
            if value not in known:
                findings.append(
                    ReferenceFinding(
                        "DANGLING_REFERENCE", doc_id, field, value
                    )
                )
                continue
            target = subjects.get(value)
            if target is None:
                continue
            if _scope_key(target) != _scope_key(doc):
                findings.append(
                    ReferenceFinding("SCOPE_MISMATCH", doc_id, field, value)
                )
            allowed = _REFERENCE_TARGETS.get(field)
            if allowed is not None and _type_name(target) not in (allowed):
                findings.append(
                    ReferenceFinding(
                        "FORBIDDEN_REFERENCE", doc_id, field, value
                    )
                )
            if expected and field in expected:
                if expected[field] != value:
                    findings.append(
                        ReferenceFinding(
                            "DIGEST_MISMATCH", doc_id, field, value
                        )
                    )
        edges[doc_id] = refs
    findings.extend(_cycles(subjects, edges))
    return findings


def _cycles(
    subjects: Mapping[str, Mapping[str, JSON]],
    edges: Mapping[str, set[str]],
) -> list[ReferenceFinding]:
    """Reject reference loops that survive digest addressing."""
    owner = {
        digest_value: _doc_id(doc) for digest_value, doc in subjects.items()
    }
    findings: list[ReferenceFinding] = []
    for doc_id in edges:
        visiting: set[str] = set()
        stack = [doc_id]
        while stack:
            node = stack.pop()
            for ref in edges.get(node, set()):
                target = owner.get(ref)
                if target is None:
                    continue
                if target == doc_id:
                    findings.append(
                        ReferenceFinding(
                            "CIRCULAR_IDENTITY",
                            doc_id,
                            "subject_graph",
                            ref,
                        )
                    )
                    break
                if target not in visiting:
                    visiting.add(target)
                    stack.append(target)
    return findings
