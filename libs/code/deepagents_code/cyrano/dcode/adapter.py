"""Runtime port and fail-closed compatibility checks.

No substitute agent loop is created here.
"""

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Protocol

from deepagents_code.cyrano.contracts.types import CyranoError

REQUIRED = frozenset(
    {
        "extension_loading",
        "async_middleware",
        "child_observation",
        "tool_mediation",
        "sandbox_isolation",
        "trusted_approval",
        "context_manifest",
        "cancel_recovery",
    }
)


@dataclass(frozen=True, slots=True)
class AttemptRequest:
    """A broker-authorized attempt bound to code and runtime state."""

    attempt_id: str
    input_snapshot: str
    context_digest: str
    permit_ref: str
    runtime_lock_digest: str


class DcodeAttemptPort(Protocol):
    """An implementation must invoke a verified installed runtime."""

    async def run(self, request: AttemptRequest) -> str:
        """Return a result-artifact reference, not self-assessment."""
        ...


def require_governed(report: dict[str, str]) -> None:
    """Reject missing, failed, unsupported or not-tested probes.

    Raises:
        CyranoError: ``DCODE_RUNTIME_NOT_VERIFIED`` listing unverified
            probes.
    """
    missing = sorted(key for key in REQUIRED if report.get(key) != "verified")
    if missing:
        raise CyranoError("DCODE_RUNTIME_NOT_VERIFIED", ", ".join(missing))


def runtime_status() -> dict[str, object]:
    """Return truthful development status; no live integration claim."""
    return {
        "mode": "development_foundation",
        "dcode_integration": "not_tested",
        "governed_available": False,
        "automatic_learning_enabled": False,
    }


def require_capability(
    name: str,
    inventory: Collection[str] | Mapping[str, object],
) -> None:
    """Reject calls to capabilities the runtime never registered.

    Args:
        name: Capability the caller wants to invoke.
        inventory: Registered capability names or a mapping keyed by
            them.

    Raises:
        CyranoError: ``UNKNOWN_CAPABILITY`` for unregistered names; no
            call, write, or external side effect is performed.
    """
    known = inventory.keys() if isinstance(inventory, Mapping) else inventory
    if name not in known:
        raise CyranoError("UNKNOWN_CAPABILITY", name)


def require_permit(
    capability: str,
    scope: str,
    permits: Mapping[str, Collection[str]],
) -> None:
    """Bind a capability invocation to an already-approved scope.

    Args:
        capability: Registered capability name.
        scope: Exact scope being exercised.
        permits: ``capability -> approved scopes``.

    Raises:
        CyranoError: ``PERMIT_REQUIRED`` when nothing was approved, or
            ``PERMIT_SCOPE_REQUIRED`` when the request widens an
            existing grant; the existing permit is unchanged either way.
    """
    granted = permits.get(capability)
    if granted is None:
        raise CyranoError("PERMIT_REQUIRED", capability)
    if scope not in granted:
        detail = f"{capability}:{scope}"
        raise CyranoError("PERMIT_SCOPE_REQUIRED", detail)


def authorize_mutation(
    action: str,
    permit: Mapping[str, object] | None,
) -> None:
    """Refuse source changes not bound to an approved plan permit.

    Args:
        action: Mutation identifier being attempted.
        permit: Approved permit document binding ``actions``; ``None``
            means no approval exists.

    Raises:
        CyranoError: ``PLAN_APPROVAL_REQUIRED`` when no permit is
            approved, or ``ACTION_NOT_IN_PERMIT`` when the action is
            outside the grant.
    """
    if not permit or permit.get("approved") is not True:
        raise CyranoError("PLAN_APPROVAL_REQUIRED", action)
    actions = permit.get("actions")
    if (
        not isinstance(actions, Collection)
        or isinstance(actions, str)
        or action not in actions
    ):
        raise CyranoError("ACTION_NOT_IN_PERMIT", action)
