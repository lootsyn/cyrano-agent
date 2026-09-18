"""Capability resolution for the governed dcode runtime.

A capability is ``verified`` only after a probe ran; ``declared`` means
a manifest claimed it without a probe; ``unknown`` covers everything
else. Model identifiers are recorded as telemetry and never branch
policy (UH-CACHE-10).
"""

from collections.abc import Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError

VERIFIED = "verified"
DECLARED = "declared"
UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CapabilityEvidence:
    """One capability's provenance level."""

    name: str
    level: str


class CapabilityService:
    """Resolve and enforce capability levels for one runtime."""

    def __init__(
        self,
        probed: Mapping[str, bool],
        declared: tuple[str, ...] = (),
        *,
        model_id: str | None = None,
    ) -> None:
        """Record probe results; the model id is telemetry only."""
        self._probed: dict[str, bool] = dict(probed)
        self._declared: set[str] = set(declared)
        self.model_id: str | None = model_id

    def resolve(self, name: str) -> str:
        """Return ``verified``, ``declared`` or ``unknown``."""
        if self._probed.get(name) is True:
            return VERIFIED
        if name in self._declared:
            return DECLARED
        return UNKNOWN

    def require(self, name: str) -> None:
        """Raise ``CAPABILITY_UNAVAILABLE`` unless verified."""
        if self.resolve(name) != VERIFIED:
            raise CyranoError(
                "CAPABILITY_UNAVAILABLE",
                f"capability {name!r} is {self.resolve(name)}",
            )
