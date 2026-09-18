"""Path B code lane: self-edit containment to deployment-ready build.

No worker edits the live process — a write aimed at the running
package is denied and redirected to an external code proposal that
enters the normal development workflow. Candidates build and test in
an isolated source workspace; a wheel that imports dirty in a clean
environment is incomplete, never shipped. Schema changes carry an
approved migration/restore plan — rollback is never just a pointer
move when old code cannot read new data.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from deepagents_code.cyrano.contracts.canonical import (
    digest,
    raw_digest,
)
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.dcode.package_build import (
    check_wheel_resources,
    plan_copy,
)

#: Live-process paths a candidate may never overwrite.
_LIVE_PREFIXES = ("deepagents_code/", "pyproject.toml", "uv.lock")


@dataclass(frozen=True, slots=True)
class EditDecision:
    """A write guard verdict; denial carries the proposal redirect."""

    allowed: bool
    reason: str
    proposal_route: str | None


def guard_self_edit(path: str, *, write: bool = True) -> EditDecision:
    """Deny writes into the live process; redirect to a proposal.

    Reads are unaffected; only writes are checked. A write anywhere
    under the live package or build manifests is refused with a
    ``code_proposal`` route — the normal review workflow owns it.
    """
    normalized = str(PurePosixPath(path))
    if not write:
        return EditDecision(True, "read_allowed", None)
    if ".." in PurePosixPath(path).parts or normalized.startswith("/"):
        return EditDecision(False, "INVALID_PATH", "code_proposal")
    if normalized.startswith(_LIVE_PREFIXES):
        return EditDecision(
            False,
            "LIVE_PROCESS_FILE",
            "code_proposal",
        )
    return EditDecision(True, "allowed", None)


@dataclass(frozen=True, slots=True)
class WorkspaceManifest:
    """An isolated workspace copy; the running source is untouched."""

    workspace: str
    entries: int
    inventory_digest: str


def prepare_code_workspace(
    payload_root: str | Path,
    workspace_root: str | Path,
) -> WorkspaceManifest:
    """Stage an isolated copy of a candidate payload.

    The payload maps onto a fresh workspace directory; any conflict
    is fail-closed before a byte is written. The live checkout is
    never a target.
    """
    workspace = Path(workspace_root).resolve()
    entries = plan_copy(payload_root, workspace)
    created = sum(1 for e in entries if e.action == "create")
    return WorkspaceManifest(
        workspace=str(workspace),
        entries=created,
        inventory_digest=digest(sorted(e.relative for e in entries)),
    )


@dataclass(frozen=True, slots=True)
class BuildEvidence:
    """Build outcomes; a broken wheel import is incomplete."""

    source_tests_passed: bool
    wheel_ok: bool
    missing_resources: tuple[str, ...]
    complete: bool


def run_code_checks(
    *,
    source_tests_passed: bool,
    wheel_path: str | Path | None,
    required_resources: Iterable[str],
) -> BuildEvidence:
    """Record build evidence; wheel verification gates completeness.

    Source tests alone are insufficient — a wheel missing required
    resources or failing clean import keeps the evidence incomplete
    and requests a fix.
    """
    required = tuple(str(r) for r in required_resources)
    if wheel_path is None:
        return BuildEvidence(
            source_tests_passed=source_tests_passed,
            wheel_ok=False,
            missing_resources=required,
            complete=False,
        )
    check = check_wheel_resources(wheel_path, required=required)
    missing_raw = check["missing"]
    missing = (
        tuple(str(m) for m in missing_raw)
        if isinstance(missing_raw, (list, tuple))
        else ()
    )
    complete = bool(source_tests_passed) and bool(check["ok"])
    return BuildEvidence(
        source_tests_passed=source_tests_passed,
        wheel_ok=bool(check["ok"]),
        missing_resources=missing,
        complete=complete,
    )


@dataclass(frozen=True, slots=True)
class MigrationPlan:
    """A schema move with its approved restore path."""

    schema_change: str
    compatible_with_previous: bool
    restore_plan: str
    promotable: bool


def plan_migration(
    change: Mapping[str, object],
    *,
    restore_plan: str | None,
) -> MigrationPlan:
    """Gate a schema change on an approved rollback path.

    An incompatible schema without a restore or migration plan is
    blocked — rolling back the pointer alone would leave old code
    unable to read the new data.
    """
    schema = str(change.get("schema_change", ""))
    if not schema:
        raise CyranoError("INPUT_INVALID", "schema change required")
    compatible = bool(change.get("compatible_with_previous", False))
    if not compatible and not restore_plan:
        raise CyranoError(
            "ROLLBACK_PLAN_REQUIRED",
            "incompatible schema needs an approved restore plan",
        )
    return MigrationPlan(
        schema_change=schema,
        compatible_with_previous=compatible,
        restore_plan=str(restore_plan or ""),
        promotable=True,
    )


@dataclass(frozen=True, slots=True)
class RuntimeCandidate:
    """A deployment candidate bound to its build references."""

    candidate_id: str
    wheel_digest: str
    evidence_refs: tuple[str, ...]
    state: str  # pending_review


def prepare_runtime_candidate(
    build: BuildEvidence,
    *,
    wheel_path: str | Path,
    evidence_refs: Iterable[str],
) -> RuntimeCandidate:
    """Seal a complete build into a review-ready runtime candidate.

    An incomplete build never becomes a candidate — the wheel must
    have passed checks and carry its evidence references.
    """
    if not build.complete:
        raise CyranoError(
            "BUILD_INCOMPLETE",
            "source tests and wheel verification must both pass",
        )
    refs = tuple(str(r) for r in evidence_refs)
    if not refs:
        raise CyranoError("EVIDENCE_REQUIRED", "build evidence needed")
    wheel = Path(wheel_path)
    if wheel.is_file():
        wheel_digest = raw_digest(wheel.read_bytes())
    else:
        raise CyranoError("RUNTIME_ARTIFACT_MISSING", str(wheel))
    return RuntimeCandidate(
        candidate_id=digest([wheel.name, sorted(refs)]),
        wheel_digest=wheel_digest,
        evidence_refs=refs,
        state="pending_review",
    )
