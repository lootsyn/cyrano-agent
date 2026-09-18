"""Release projection: pinned resolved paths and digests.

An attempt pins the exact resolved path and digest of every skill it
saw. Mixing two resolutions of one id inside a release is refused;
on resume under a different policy release the original pin stays
unless the caller explicitly restarts.
"""

from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError


@dataclass(frozen=True, slots=True)
class PinnedSkill:
    """A resolved skill bound into a release projection."""

    skill_id: str
    resolved_path: str
    digest: str


@dataclass(frozen=True, slots=True)
class AttemptPin:
    """An attempt's pinned release; stable across resume."""

    attempt_id: str
    release_id: str
    skills: tuple[PinnedSkill, ...]


class ReleaseProjection:
    """Pin resolved skills into a release; mixing is refused."""

    def __init__(self) -> None:
        """Start with no pins and no attempts."""
        self._releases: dict[str, dict[str, PinnedSkill]] = {}
        self._attempts: dict[str, AttemptPin] = {}

    def pin_skill(
        self,
        release_id: str,
        skill_id: str,
        *,
        resolved_path: str,
        digest: str,
    ) -> PinnedSkill:
        """Pin one resolution; a divergent digest is a release mix."""
        pins = self._releases.setdefault(release_id, {})
        existing = pins.get(skill_id)
        if existing is not None and (
            existing.digest != digest
            or existing.resolved_path != resolved_path
        ):
            raise CyranoError(
                "RELEASE_MIX",
                f"{skill_id} resolved twice inside {release_id}",
            )
        pin = PinnedSkill(skill_id, resolved_path, digest)
        pins[skill_id] = pin
        return pin

    def pin_attempt(self, attempt_id: str, release_id: str) -> AttemptPin:
        """Freeze an attempt's release view."""
        pins = tuple(
            sorted(
                self._releases.get(release_id, {}).values(),
                key=lambda p: p.skill_id,
            )
        )
        pin = AttemptPin(attempt_id, release_id, pins)
        self._attempts[attempt_id] = pin
        return pin

    def resume(
        self,
        attempt_id: str,
        *,
        offered_release: str,
        explicit_restart: bool = False,
    ) -> AttemptPin:
        """Resume keeps the pin; a new release needs a restart."""
        pin = self._attempts.get(attempt_id)
        if pin is None:
            raise CyranoError("UNKNOWN_ATTEMPT", attempt_id)
        if offered_release != pin.release_id and not explicit_restart:
            return pin  # policy release moved; the attempt pin stays
        if explicit_restart:
            return self.pin_attempt(attempt_id, offered_release)
        return pin
