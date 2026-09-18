"""Anchored edits: exact byte-range patches with a journal.

Anchors carry the file's byte range and the SHA-256 of the expected
preimage; short tags and fuzzy matching never substitute for that
identity. Every hunk validates before any write, each apply is
journaled, and a mid-apply failure is reconciled rather than
silently half-written.
"""

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Mapping

from deepagents_code.cyrano.contracts.types import CyranoError


@dataclass(frozen=True, slots=True)
class PatchAnchor:
    """Exact byte identity of the region an edit replaces."""

    path: str
    start: int
    end: int
    expected_digest: str


@dataclass(frozen=True, slots=True)
class EditHunk:
    """One anchored replacement; replacement is raw bytes."""

    anchor: PatchAnchor
    replacement: bytes


@dataclass(frozen=True, slots=True)
class ApplyResult:
    """Post-apply snapshot digests plus the journal entry id."""

    digests: Mapping[str, str]
    journal_id: str


def anchor_for(content: bytes, needle: bytes) -> tuple[int, int]:
    """Resolve a text anchor to a unique byte range.

    Raises:
        CyranoError: INPUT_INVALID when the text occurs more than
            once; PATCH_STALE when it does not occur.
    """
    first = content.find(needle)
    if first < 0:
        raise CyranoError("PATCH_STALE", "anchor text not found")
    if content.find(needle, first + 1) >= 0:
        raise CyranoError("INPUT_INVALID", "anchor text is not unique")
    return first, first + len(needle)


def _check_path(path: str) -> None:
    pure = PurePosixPath(path)
    if (
        not path
        or pure.is_absolute()
        or "\\" in path
        or any(p in {"", ".", ".."} for p in pure.parts)
    ):
        raise CyranoError("ACL_DENIED", path)


def _range_digest(content: bytes, start: int, end: int) -> str:
    if start < 0 or end > len(content) or start > end:
        raise CyranoError("INPUT_INVALID", "bad byte range")
    return "sha256:" + sha256(content[start:end]).hexdigest()


class AnchoredEditService:
    """Validate all hunks first; apply under a journal."""

    def validate_patch(
        self,
        hunks: list[EditHunk],
        snapshot: Mapping[str, bytes],
    ) -> None:
        """Verify every hunk's identity before any apply is legal."""
        for hunk in hunks:
            anchor = hunk.anchor
            _check_path(anchor.path)
            content = snapshot.get(anchor.path)
            if content is None:
                raise CyranoError("SOURCE_MISSING", anchor.path)
            actual = _range_digest(content, anchor.start, anchor.end)
            if actual != anchor.expected_digest:
                raise CyranoError("PATCH_STALE", anchor.path)

    def preimage_digest(self, content: bytes) -> str:
        """Whole-file digest binding the apply to one preimage."""
        return "sha256:" + sha256(content).hexdigest()

    def apply_candidate(
        self,
        root: Path,
        hunks: list[EditHunk],
        journal_dir: Path,
        *,
        preimage_digests: Mapping[str, str],
    ) -> ApplyResult:
        """Apply validated hunks under a journal; never half-hide.

        The journal records each file's preimage before writes; an
        I/O failure marks it needs_reconciliation instead of
        pretending success. A file that changed since validation —
        or became a symlink — is left untouched and reported.
        """
        journal_dir.mkdir(parents=True, exist_ok=True)
        journal_id = f"j{len(list(journal_dir.iterdir())) + 1}"
        journal = journal_dir / f"{journal_id}.json"
        journal.write_text(
            json.dumps(
                {
                    "status": "prepared",
                    "preimages": dict(preimage_digests),
                }
            )
        )
        by_path: dict[str, list[EditHunk]] = {}
        for hunk in hunks:
            by_path.setdefault(hunk.anchor.path, []).append(hunk)
        new_digests: dict[str, str] = {}
        try:
            for path, path_hunks in by_path.items():
                _check_path(path)
                target = root / path
                if target.is_symlink():
                    raise CyranoError(
                        "PATH_ESCAPE",
                        f"{path} became a symlink",
                    )
                content = target.read_bytes()
                if self.preimage_digest(content) != preimage_digests[path]:
                    raise CyranoError(
                        "PATCH_CONFLICT",
                        f"{path} changed since validation",
                    )
                for hunk in sorted(
                    path_hunks,
                    key=lambda h: h.anchor.start,
                    reverse=True,
                ):
                    content = (
                        content[: hunk.anchor.start]
                        + hunk.replacement
                        + content[hunk.anchor.end :]
                    )
                target.write_bytes(content)
                new_digests[path] = self.preimage_digest(content)
        except OSError as exc:
            journal.write_text(
                json.dumps(
                    {"status": "needs_reconciliation", "error": str(exc)}
                )
            )
            raise CyranoError("APPLY_INCOMPLETE", str(exc)) from exc
        except CyranoError as exc:
            journal.write_text(
                json.dumps({"status": "blocked", "error": exc.code})
            )
            raise
        journal.write_text(
            json.dumps({"status": "applied", "digests": new_digests})
        )
        return ApplyResult(digests=new_digests, journal_id=journal_id)
