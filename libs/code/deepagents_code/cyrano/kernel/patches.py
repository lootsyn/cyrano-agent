"""Permit-gated source apply with a preimage/postimage journal.

Applying a candidate to the real source is a separate authority from
executing work. Every file's preimage is checked before any write —
an externally modified file stops the apply rather than being
overwritten. Each file's preimage and postimage is journaled, so a
mid-apply failure reports ``partial`` with recovery data instead of a
full-apply claim. Rollback restores a file only while its bytes still
match the journaled postimage; a user edit is preserved and the apply
stays in reconciliation.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath

from deepagents_code.cyrano.contracts.types import CyranoError

DELIVERY_MODES = frozenset({"patch_only", "apply_to_source"})


@dataclass(frozen=True, slots=True)
class ApplyGrant:
    """The separate source-apply authority; approval is not one."""

    purpose: str
    subject_digest: str
    approved_paths: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class FilePatch:
    """One file replacement bound to its expected preimage digest."""

    path: str
    preimage_digest: str
    postimage: bytes


@dataclass(frozen=True, slots=True)
class ApplyEntry:
    """Per-file journal row; the recovery unit is the file."""

    path: str
    preimage_digest: str
    postimage_digest: str
    status: str


@dataclass(frozen=True, slots=True)
class ApplyJournal:
    """What an apply actually did; ``partial`` is an honest outcome."""

    journal_id: str
    status: str
    entries: tuple[ApplyEntry, ...]
    path: str


@dataclass(frozen=True, slots=True)
class RollbackReport:
    """Rollback restores matched files and preserves user edits."""

    status: str
    restored: tuple[str, ...]
    conflict_preserved: tuple[str, ...]
    needs_human_decision: bool


@dataclass(frozen=True, slots=True)
class WorkDelivery:
    """The deliverable; patch-only delivery never touched source."""

    mode: str
    patch_ref: str | None
    source_changed: bool
    applied_paths: tuple[str, ...]


def _file_digest(content: bytes) -> str:
    return "sha256:" + sha256(content).hexdigest()


def _write_file(target: Path, data: bytes) -> None:
    _ = target.write_bytes(data)


def _check_path(path: str) -> None:
    pure = PurePosixPath(path)
    if (
        not path
        or pure.is_absolute()
        or "\\" in path
        or any(p in {"", ".", ".."} for p in pure.parts)
    ):
        raise CyranoError("ACL_DENIED", path)


def _write_journal(
    journal_dir: Path,
    journal_id: str,
    status: str,
    rows: list[Mapping[str, object]],
) -> Path:
    journal_dir.mkdir(parents=True, exist_ok=True)
    path = journal_dir / f"{journal_id}.json"
    _ = path.write_text(
        json.dumps({"status": status, "files": rows}, indent=1)
    )
    return path


def apply_to_target(
    *,
    root: Path,
    patches: Sequence[FilePatch],
    grant: ApplyGrant | None,
    journal_dir: Path,
) -> ApplyJournal:
    """Apply approved patches; every preimage is checked first.

    A grant with the wrong purpose is refused, a patch outside the
    approved paths is denied, and a file that changed since approval
    raises ``PREIMAGE_CONFLICT`` before any byte is written.
    """
    if grant is None:
        raise CyranoError("APPROVAL_REQUIRED", "no source-apply grant")
    if grant.purpose != "source_apply":
        raise CyranoError("PURPOSE_MISMATCH", grant.purpose)
    for patch in patches:
        _check_path(patch.path)
        if (
            grant.approved_paths is not None
            and patch.path not in grant.approved_paths
        ):
            raise CyranoError("ACL_DENIED", patch.path)
        target = root / patch.path
        if target.is_symlink():
            raise CyranoError("PATH_ESCAPE", patch.path)
        if not target.exists():
            raise CyranoError("SOURCE_MISSING", patch.path)
        actual = _file_digest(target.read_bytes())
        if actual != patch.preimage_digest:
            raise CyranoError("PREIMAGE_CONFLICT", patch.path)
    journal_id = (
        "apply-"
        + sha256(
            (
                grant.subject_digest + "|" + "|".join(p.path for p in patches)
            ).encode("utf-8")
        ).hexdigest()[:12]
    )
    rows: list[Mapping[str, object]] = []
    entries: list[ApplyEntry] = []
    status = "applied"
    for patch in patches:
        target = root / patch.path
        preimage = target.read_bytes()
        row: dict[str, object] = {
            "path": patch.path,
            "preimage_digest": patch.preimage_digest,
            "preimage_b64": base64.b64encode(preimage).decode("ascii"),
            "postimage_digest": _file_digest(patch.postimage),
        }
        try:
            _write_file(target, patch.postimage)
            row["status"] = "applied"
            entries.append(
                ApplyEntry(
                    patch.path,
                    patch.preimage_digest,
                    str(row["postimage_digest"]),
                    "applied",
                )
            )
        except OSError as exc:
            status = "partial"
            row["status"] = "failed"
            row["error"] = str(exc)
            entries.append(
                ApplyEntry(
                    patch.path,
                    patch.preimage_digest,
                    str(row["postimage_digest"]),
                    "failed",
                )
            )
        rows.append(row)
    path = _write_journal(journal_dir, journal_id, status, rows)
    return ApplyJournal(journal_id, status, tuple(entries), str(path))


def deliver_result(
    mode: str,
    *,
    patch_ref: str | None,
    journal: ApplyJournal | None,
) -> WorkDelivery:
    """Deliver a patch or report an applied source — never both ways.

    ``patch_only`` hands over the patch artifact and reports the
    source as untouched; ``apply_to_source`` may only claim applied
    files that the journal actually recorded.
    """
    if mode not in DELIVERY_MODES:
        raise CyranoError("INVALID_OUTCOME", mode)
    if mode == "patch_only":
        return WorkDelivery(mode, patch_ref, False, ())
    if journal is None or journal.status != "applied":
        status = "no journal" if journal is None else journal.status
        raise CyranoError(
            "APPLY_INCOMPLETE", f"cannot claim apply; status={status}"
        )
    applied = tuple(e.path for e in journal.entries if e.status == "applied")
    return WorkDelivery(mode, patch_ref, True, applied)


def authorize_publish(publish_grant: ApplyGrant | None) -> None:
    """Publish is a distinct purpose; acceptance is not a push right."""
    if publish_grant is None:
        raise CyranoError("PURPOSE_MISMATCH", "no publish grant")
    if publish_grant.purpose != "publish":
        raise CyranoError("PURPOSE_MISMATCH", publish_grant.purpose)


def rollback_source(
    *,
    root: Path,
    journal: ApplyJournal,
) -> RollbackReport:
    """Restore preimages only where the postimage is still current.

    A file whose bytes no longer match the journaled postimage was
    changed outside this apply — it is preserved untouched and the
    apply stays ``reconciling`` for a human decision.
    """
    loaded: object = json.loads(Path(journal.path).read_text())
    files: list[object] = []
    if isinstance(loaded, Mapping):
        raw = loaded.get("files")
        if isinstance(raw, list):
            files = list(raw)
    restored: list[str] = []
    preserved: list[str] = []
    for row in files:
        if not isinstance(row, Mapping) or row.get("status") != "applied":
            continue
        path = str(row.get("path"))
        target = root / path
        current = _file_digest(target.read_bytes())
        if current != row.get("postimage_digest"):
            preserved.append(path)
            continue
        _ = target.write_bytes(base64.b64decode(str(row.get("preimage_b64"))))
        restored.append(path)
    if preserved:
        return RollbackReport(
            "reconciling",
            tuple(sorted(restored)),
            tuple(sorted(preserved)),
            True,
        )
    return RollbackReport("rolled_back", tuple(sorted(restored)), (), False)


class ExpectedChain:
    """Expected postimage per path; approved applies advance it.

    A dependent unit's preimage expectation follows the approved
    chain, so in-scope completed work updates the expectation instead
    of forcing a whole-spec re-approval.
    """

    def __init__(self, expected: Mapping[str, str]) -> None:
        """Start from the approved preimage expectations."""
        self._expected: dict[str, str] = dict(expected)

    def expect(self, path: str) -> str | None:
        """Return the current expected digest for a path."""
        return self._expected.get(path)

    def advance(self, journal: ApplyJournal, grant: ApplyGrant) -> None:
        """Fold an applied journal into the expectation chain.

        Every applied path must be inside the grant's approved paths;
        an out-of-grant write is refused and nothing advances.
        """
        applied = [e for e in journal.entries if e.status == "applied"]
        if grant.approved_paths is not None:
            for entry in applied:
                if entry.path not in grant.approved_paths:
                    raise CyranoError("ACL_DENIED", entry.path)
        for entry in applied:
            self._expected[entry.path] = entry.postimage_digest

    def check(self, path: str, digest: str) -> bool:
        """True when a patch's preimage matches the expected chain."""
        return self._expected.get(path) == digest
