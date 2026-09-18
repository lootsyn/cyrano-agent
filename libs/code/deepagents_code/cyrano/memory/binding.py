"""Release/epoch binding for memory views.

``bind_core`` fixes a release to a snapshot and epoch: the bound view
digest changes only when the inputs change, so identical runs share
the stable prefix while query views stay separate.
"""

import hashlib
import json
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError


@dataclass(frozen=True, slots=True)
class CoreBinding:
    """A release bound to a source snapshot and epoch."""

    release_id: str
    snapshot_digest: str
    epoch: str
    required_rules: tuple[str, ...]

    @property
    def view_digest(self) -> str:
        """Stable digest over the bound inputs only."""
        blob = json.dumps(
            {
                "release": self.release_id,
                "snapshot": self.snapshot_digest,
                "epoch": self.epoch,
                "rules": list(self.required_rules),
            },
            sort_keys=True,
        )
        return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


def bind_core(
    release_id: str,
    snapshot_digest: str,
    epoch: str,
    required_rules: tuple[str, ...],
    *,
    current_snapshot: str,
) -> CoreBinding:
    """Bind a release to a snapshot; a stale snapshot is refused.

    Cache warmth never keeps a stale binding alive — the bound digest
    must match the current source snapshot.
    """
    if snapshot_digest != current_snapshot:
        raise CyranoError(
            "STALE_SNAPSHOT",
            "release bound to a superseded source snapshot",
        )
    return CoreBinding(
        release_id=release_id,
        snapshot_digest=snapshot_digest,
        epoch=epoch,
        required_rules=tuple(required_rules),
    )
