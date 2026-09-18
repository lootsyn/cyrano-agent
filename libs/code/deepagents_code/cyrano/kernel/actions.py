"""Action broker: scope-checked dispatch behind signed permits.

Deny rules always win over allow rules; child scopes get the
intersection of grants, never a superset. Every mutation writes its
durable audit record before the side effect, and the permit is
re-verified at apply time so a mid-work revocation still blocks.
"""

from dataclasses import dataclass
from pathlib import PurePosixPath

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.kernel.approvals import (
    SignedPermit,
    verify_permit,
)

ACTIONS = frozenset(
    {"read", "create", "write_existing", "delete", "only_write"}
)

MODES = frozenset({"manual", "auto", "headless", "acp", "resume"})


@dataclass(frozen=True, slots=True)
class Grant:
    """One path rule; deny entries always win over allow entries."""

    path: str
    allow: frozenset[str] = frozenset()
    deny: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class Decision:
    """A broker decision; denials carry the refusal code."""

    allowed: bool
    code: str
    detail: str = ""


def _normalize(path: str) -> str:
    """Reject noncanonical paths before any grant lookup."""
    pure = PurePosixPath(path)
    if (
        not path
        or "\\" in path
        or pure.is_absolute()
        or any(p in {"", ".", ".."} for p in pure.parts)
    ):
        raise CyranoError("ACL_DENIED", path)
    return str(pure)


def intersect_grants(
    parent: tuple[Grant, ...], child: tuple[Grant, ...]
) -> tuple[Grant, ...]:
    """A child gets only what both levels allow; denies union."""
    result: list[Grant] = []
    for cg in child:
        for pg in parent:
            if pg.path != cg.path:
                continue
            result.append(
                Grant(
                    path=cg.path,
                    allow=cg.allow & pg.allow,
                    deny=cg.deny | pg.deny,
                )
            )
    parent_denies = [
        Grant(path=g.path, deny=g.deny)
        for g in parent
        if g.deny and all(r.path != g.path for r in result)
    ]
    return tuple(result + parent_denies)


def evaluate(
    action: str,
    path: str,
    grants: tuple[Grant, ...],
    *,
    preexisting: bool = False,
) -> Decision:
    """Pure ACL evaluation: deny wins, then action-specific allow."""
    normalized = _normalize(path)
    allowed_by: list[Grant] = []
    for grant in grants:
        if grant.path != normalized:
            continue
        effective_deny = set(grant.deny)
        if "only_write" in grant.allow:
            effective_deny.add("read")
        if action in effective_deny:
            return Decision(False, "DENIED", path)
        write_ok = action in {"create", "write_existing"}
        if action in grant.allow or (write_ok and "only_write" in grant.allow):
            allowed_by.append(grant)
    if not allowed_by:
        if action == "create" and not preexisting:
            return Decision(False, "CREATE_APPROVAL_REQUIRED", path)
        return Decision(False, "SCOPE_DENIED", path)
    return Decision(True, "ALLOWED", path)


class ActionBroker:
    """Broker over a ledger; audit precedes every mutation."""

    def __init__(
        self,
        tools: frozenset[str],
        grants: tuple[Grant, ...],
        audit,
    ) -> None:
        """Tools must be registered; audit writes durably."""
        self._tools = frozenset(tools)
        self._grants = grants
        self._audit = audit

    def decide(
        self,
        *,
        tool: str,
        action: str,
        path: str,
        permit: SignedPermit | None,
        trust_root,
        subject_digest: str,
        now: int,
        is_revoked,
        mode: str = "manual",
        actor: str | None = None,
        authenticated_actor: str | None = None,
        preexisting: bool = False,
        recipe_approved: bool = True,
        headless_policy: bool = True,
    ) -> Decision:
        """One checked dispatch decision; failure paths never mutate."""
        if mode not in MODES:
            return Decision(False, "UNSUPPORTED_MODE", mode)
        if actor is not None and actor != authenticated_actor:
            return Decision(False, "ACL_DENIED", actor)
        if tool not in self._tools:
            return Decision(False, "UNKNOWN_TOOL", tool)
        if tool == "execute_recipe" and not recipe_approved:
            return Decision(False, "UNVERIFIED_RECIPE", tool)
        if permit is None:
            return Decision(False, "APPROVAL_REQUIRED", path)
        try:
            verify_permit(
                permit,
                trust_root,
                purpose="execute",
                subject_digest=subject_digest,
                now=now,
                is_revoked=is_revoked,
            )
        except CyranoError as exc:
            return Decision(False, exc.code, str(exc))
        if not headless_policy and mode == "headless":
            return Decision(False, "BLOCKED", mode)
        return evaluate(action, path, self._grants, preexisting=preexisting)

    def apply_scoped_patch(
        self,
        *,
        permit: SignedPermit,
        trust_root,
        subject_digest: str,
        now: int,
        is_revoked,
        apply_fn,
    ):
        """Audit first, re-verify the permit, then apply via port."""
        try:
            self._audit(f"apply:{permit.permit_id}:{subject_digest}")
        except CyranoError:
            raise
        except Exception as exc:  # noqa: BLE001 - fail closed
            raise CyranoError("AUDIT_UNAVAILABLE", str(exc)) from exc
        verify_permit(
            permit,
            trust_root,
            purpose="execute",
            subject_digest=subject_digest,
            now=now,
            is_revoked=is_revoked,
        )
        result = apply_fn()
        self._audit(f"applied:{permit.permit_id}")
        return result

    def deny_event(self, detail: str) -> None:
        """Record a denial in the durable ledger."""
        self._audit(f"denied:{detail}")


def check_payload_budget(
    compressed: bytes, decompressed: bytes, cap: int
) -> None:
    """Reject decompressed results that exceed the byte cap."""
    if len(decompressed) > cap:
        raise CyranoError(
            "PAYLOAD_TOO_LARGE",
            f"{len(decompressed)} exceeds cap {cap}",
        )


def reject_ambiguous_path(names: list[str]) -> None:
    """Two distinct entries differing only by case are ambiguous."""
    lowered: dict[str, str] = {}
    for name in names:
        key = name.lower()
        if key in lowered and lowered[key] != name:
            raise CyranoError("PATH_AMBIGUOUS", name)
        lowered[key] = name
