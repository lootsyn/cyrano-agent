"""Verified-runtime bridge for governed dcode attempts.

A governed attempt only runs against a runtime whose probes all
verified (``start_verified_runtime``). Dispatch order is fixed:
binding -> durable attempt -> guard -> budget -> frozen context ->
handler -> usage settle. An unverified runtime refuses every attempt.
"""

import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.dcode.adapter import (
    AttemptRequest,
    require_governed,
)


@dataclass(frozen=True, slots=True)
class RuntimeHandle:
    """Handle to a runtime that passed every required probe."""

    verified: bool
    runtime_lock_digest: str
    probe_report: Mapping[str, str]


def start_verified_runtime(
    probe_report: Mapping[str, str],
    runtime_lock_digest: str,
) -> RuntimeHandle:
    """Bind a handle to a runtime; refuse unverified ones."""
    require_governed(dict(probe_report))
    return RuntimeHandle(
        verified=True,
        runtime_lock_digest=runtime_lock_digest,
        probe_report=dict(probe_report),
    )


@dataclass(frozen=True, slots=True)
class AttemptReceipt:
    """Durable source/evidence receipt for one attempt."""

    attempt_id: str
    result_ref: str
    context_digest: str
    usage: Mapping[str, int]
    events: tuple[str, ...]


Handler = Callable[[AttemptRequest], Awaitable[str]]


class AttemptBridge:
    """Drive one governed attempt through the fixed pipeline."""

    def __init__(
        self,
        handle: RuntimeHandle,
        *,
        guard: Callable[[str], bool] | None = None,
        budget_remaining: Callable[[], int] | None = None,
    ) -> None:
        """Bind the runtime handle and enforcement callbacks."""
        self._handle: RuntimeHandle = handle
        self._guard: Callable[[str], bool] | None = guard
        self._budget: Callable[[], int] | None = budget_remaining
        self._events: list[str] = []

    async def execute_attempt(
        self,
        request: AttemptRequest,
        handler: Handler,
    ) -> AttemptReceipt:
        """Run guard -> budget -> context -> handler -> usage.

        A request whose runtime lock digest differs from the
        verified handle's is stale and refused before any handler
        runs.
        """
        if not self._handle.verified:
            # Owned by adapter.py: an unverified handle lists every
            # probe as unverified and refuses dispatch.
            require_governed({})
        if request.runtime_lock_digest != self._handle.runtime_lock_digest:
            raise CyranoError(
                "STALE_SNAPSHOT",
                "attempt bound to a different runtime lock",
            )
        self._events.append(f"attempt.bound:{request.attempt_id}")
        if self._guard is not None and not self._guard(request.attempt_id):
            raise CyranoError(
                "SCOPE_DENIED", f"guard refused {request.attempt_id}"
            )
        if self._budget is not None and self._budget() <= 0:
            raise CyranoError("BUDGET_EXCEEDED", "attempt budget exhausted")
        self._events.append(f"attempt.frozen:{request.context_digest}")
        result_ref = await handler(request)
        self._events.append(f"attempt.settled:{request.attempt_id}")
        return AttemptReceipt(
            attempt_id=request.attempt_id,
            result_ref=result_ref,
            context_digest=request.context_digest,
            usage={},
            events=tuple(self._events),
        )

    async def execute_child(
        self,
        request: AttemptRequest,
        handler: Handler,
        parent_scope: frozenset[str],
        child_scope: frozenset[str],
    ) -> AttemptReceipt:
        """A child attempt may only narrow the parent's scope.

        ``DCODE-CHILD``: a child that claims paths outside the parent's
        granted scope is refused before dispatch.
        """
        if not child_scope <= parent_scope:
            raise CyranoError(
                "SCOPE_DENIED",
                "child scope exceeds the parent grant",
            )
        return await self.execute_attempt(request, handler)


def map_virtual_path(
    virtual_path: str,
    explicit_mapping: Mapping[str, str] | None = None,
) -> str | None:
    """Resolve a virtual path only through an explicit mapping.

    ``DCODE-VIRTUAL``: virtual paths are never auto-mapped onto host
    paths; without an approved mapping the path stays unmapped.
    """
    if explicit_mapping is None:
        return None
    return explicit_mapping.get(virtual_path)


def apply_override(
    name: str,
    allowlist: frozenset[str],
    *,
    allowlist_verified: bool,
) -> str:
    """An override applies only through a verified allowlist.

    ``DCODE-OVERRIDE``: an unverified or missing allowlist refuses
    every override, including plausible ones.
    """
    if not allowlist_verified or name not in allowlist:
        raise CyranoError(
            "SCOPE_DENIED", f"override {name!r} is not allowlisted"
        )
    return name


def attempt_digest(request: AttemptRequest) -> str:
    """Stable digest binding an attempt to its inputs."""
    blob = json.dumps(
        {
            "attempt_id": request.attempt_id,
            "context_digest": request.context_digest,
            "input_snapshot": request.input_snapshot,
            "permit_ref": request.permit_ref,
            "runtime_lock_digest": request.runtime_lock_digest,
        },
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()
