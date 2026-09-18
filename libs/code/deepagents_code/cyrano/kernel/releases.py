"""Release subjects and the CAS promotion lane.

A release starts as a staged subject bound to its parent, its patch
digest, its evidence, and an approval. Promotion is a
compare-and-swap on the live pointer: only a subject whose parent is
the live release may promote, and the patch digest evaluated must be
the digest being promoted — a body edited after evaluation is an
invalid approval, not a small amend. Without human approval or a
scoped prior delegation, promotion is refused by default.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError

SEQ = (list, tuple, set, frozenset)


@dataclass(frozen=True, slots=True)
class ReleaseSubject:
    """A staged release; approval is bound to this exact subject."""

    subject_id: str
    parent_id: str
    patch_digest: str
    evidence_refs: tuple[str, ...]
    approval_ref: str


def prepare_release(
    candidate: Mapping[str, object],
    *,
    parent_id: str,
    approval: Mapping[str, object] | None,
    scoped_delegation: bool = False,
) -> ReleaseSubject:
    """Stage a release subject; approval or delegation is required.

    Automatic promotion without human approval is disabled by
    default — only a scoped prior delegation substitutes, and it is
    recorded on the subject.
    """
    patch = str(candidate.get("patch_digest", ""))
    if not patch:
        raise CyranoError("INPUT_INVALID", "patch digest required")
    approval_id = approval.get("approval_id") if approval is not None else None
    if approval_id is None and not scoped_delegation:
        raise CyranoError(
            "RELEASE_APPROVAL_REQUIRED",
            "promotion needs human approval or scoped delegation",
        )
    evidence = candidate.get("evidence_refs", ())
    refs = tuple(str(e) for e in evidence) if isinstance(evidence, SEQ) else ()
    if not refs:
        raise CyranoError("EVIDENCE_REQUIRED", "release needs evidence")
    approval_ref = (
        str(approval_id)
        if approval_id is not None
        else "delegation:" + str(scoped_delegation)
    )
    return ReleaseSubject(
        subject_id=digest([patch, parent_id, approval_ref]),
        parent_id=parent_id,
        patch_digest=patch,
        evidence_refs=refs,
        approval_ref=approval_ref,
    )


@dataclass(frozen=True, slots=True)
class Release:
    """An immutable promoted release; history never rewrites it."""

    release_id: str
    parent_id: str
    patch_digest: str
    evidence_refs: tuple[str, ...]


class ReleaseLane:
    """Kernel CAS lane; only one child of the live release promotes."""

    def __init__(self, initial: Release) -> None:
        """Bind the lane to the live release."""
        self._live = initial
        self._history: list[Release] = [initial]
        self._revoked: set[str] = set()

    @property
    def live(self) -> Release:
        """The live release."""
        return self._live

    def history(self) -> tuple[Release, ...]:
        """Every release including revoked; evidence persists."""
        return tuple(self._history)

    def is_revoked(self, release_id: str) -> bool:
        """Whether a release is revoked — revocation outranks pins."""
        return release_id in self._revoked

    def promote(
        self,
        subject: ReleaseSubject,
        *,
        evaluated_digest: str,
    ) -> Release:
        """Promote via CAS; digest drift or a stale parent refuses.

        A subject whose evaluated digest differs from what is being
        promoted invalidates its approval; a subject whose parent is
        no longer live must rebase and re-evaluate. The pointer moves
        only on success.
        """
        if evaluated_digest != subject.patch_digest:
            raise CyranoError(
                "APPROVAL_INVALID",
                "evaluated digest differs from the subject",
            )
        if subject.parent_id != self._live.release_id:
            raise CyranoError(
                "STALE_REVISION",
                f"parent {subject.parent_id} is not live",
            )
        release = Release(
            release_id=digest([subject.subject_id, self._live.release_id]),
            parent_id=self._live.release_id,
            patch_digest=subject.patch_digest,
            evidence_refs=subject.evidence_refs,
        )
        self._history.append(release)
        self._live = release
        return release

    def revoke(self, release_id: str, *, reason: str) -> Release:
        """Revoke a release; the record stays, the flag is durable."""
        for release in self._history:
            if release.release_id == release_id:
                self._revoked.add(release_id)
                return release
        raise CyranoError("MISSING_RELEASE", release_id)

    def rollback(self, target_id: str) -> Release:
        """Re-point the lane to a prior immutable release.

        The superseded release stays in history; only the live
        pointer moves. The target must be a known release.
        """
        for release in self._history:
            if release.release_id == target_id:
                self._live = release
                return release
        raise CyranoError("MISSING_RELEASE", target_id)
