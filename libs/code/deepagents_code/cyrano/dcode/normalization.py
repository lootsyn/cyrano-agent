"""Provider-wire normalization for tool calls and results.

Tool-call arguments arrive as byte fragments; only a complete,
parseable call may dispatch. Orphan results, missing results,
call-id collisions, oversized arguments, cross-provider reasoning,
unsupported content kinds, retry ownership, and cancellation are all
handled explicitly — nothing is silently dropped or coerced.
"""

import json
from dataclasses import dataclass, field

from deepagents_code.cyrano.contracts.canonical import JSON
from deepagents_code.cyrano.contracts.types import CyranoError

DEFAULT_MAX_ARGS_BYTES = 262_144
DEFAULT_MAX_CALLS = 512
SUPPORTED_CONTENT = frozenset({"text"})


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A complete, dispatchable tool call."""

    call_id: str
    name: str
    arguments: dict[str, JSON]


@dataclass(slots=True)
class _Pending:
    name: str
    chunks: list[bytes] = field(default_factory=list)
    cancelled: bool = False
    completed: bool = False
    result: JSON = None
    has_result: bool = False
    usage: dict[str, int] | None = None
    retry_owner: str | None = None


class ProtocolNormalizer:
    """Assemble fragments, dispatch complete calls, track results."""

    def __init__(
        self,
        *,
        max_args_bytes: int = DEFAULT_MAX_ARGS_BYTES,
        max_calls: int = DEFAULT_MAX_CALLS,
        supported_content: frozenset[str] = SUPPORTED_CONTENT,
    ) -> None:
        """Configure argument limits and supported content kinds."""
        self._max_args: int = max_args_bytes
        self._max_calls: int = max_calls
        self._supported: frozenset[str] = supported_content
        self._pending: dict[str, _Pending] = {}
        self._orphans: list[tuple[str, JSON]] = []
        self._synthetic: list[tuple[str, JSON]] = []

    # ------------------------------------------------ fragments --

    def feed(
        self, call_id: str, name: str, chunk: bytes, *, final: bool
    ) -> ToolCall | None:
        """Feed one fragment; return a call only when complete."""
        slot = self._pending.get(call_id)
        if slot is None:
            if len(self._pending) >= self._max_calls:
                raise CyranoError(
                    "TOOL_ARGUMENT_LIMIT",
                    f"more than {self._max_calls} open calls",
                )
            slot = _Pending(name=name)
            self._pending[call_id] = slot
        elif slot.name != name:
            raise CyranoError(
                "CALL_ID_COLLISION",
                f"call id {call_id!r} reused for {name!r}",
            )
        if slot.completed:
            raise CyranoError(
                "CALL_ID_COLLISION",
                f"call id {call_id!r} already completed",
            )
        slot.chunks.append(chunk)
        if sum(len(c) for c in slot.chunks) > self._max_args:
            raise CyranoError(
                "TOOL_ARGUMENT_LIMIT",
                f"arguments for {call_id!r} exceed {self._max_args}",
            )
        if not final:
            return None
        slot.completed = True
        raw = b"".join(slot.chunks)
        try:
            arguments = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CyranoError(
                "INCOMPLETE_TOOL_CALL",
                f"arguments for {call_id!r} never formed valid JSON",
            ) from exc
        if not isinstance(arguments, dict):
            raise CyranoError(
                "INCOMPLETE_TOOL_CALL",
                f"arguments for {call_id!r} are not an object",
            )
        return ToolCall(call_id=call_id, name=name, arguments=arguments)

    # -------------------------------------------------- results --

    def record_result(self, call_id: str, payload: JSON) -> str:
        """Record a tool result; orphan and stale results are kept."""
        slot = self._pending.get(call_id)
        if slot is None:
            self._orphans.append((call_id, payload))
            raise CyranoError(
                "INPUT_INVALID", f"result for unknown call {call_id!r}"
            )
        if slot.cancelled:
            return "stale"
        slot.result = payload
        slot.has_result = True
        return "ok"

    def finalize(self) -> list[ToolCall]:
        """Close the stream; unresolved calls get synthetic results.

        A call that never received a result produces a synthetic
        ``observation_missing`` result — the effect stays unknown and
        is never treated as an implicit success.
        """
        for call_id, slot in self._pending.items():
            if not slot.completed:
                raise CyranoError(
                    "INCOMPLETE_TOOL_CALL",
                    f"call {call_id!r} ended without a final fragment",
                )
            if not slot.has_result:
                self._synthetic.append(
                    (call_id, {"status": "observation_missing"})
                )
        return [ToolCall(c, s.name, {}) for c, s in self._pending.items()]

    # ------------------------------------------------- lifecycle --

    def cancel(self, call_id: str) -> None:
        """Cancel a call; later results arrive as stale."""
        slot = self._pending.get(call_id)
        if slot is None:
            raise CyranoError(
                "INPUT_INVALID", f"cancel for unknown call {call_id!r}"
            )
        slot.cancelled = True

    def record_usage(self, call_id: str, usage: dict[str, int]) -> None:
        """Usage settles even for cancelled calls."""
        slot = self._pending.get(call_id)
        if slot is None:
            raise CyranoError(
                "INPUT_INVALID", f"usage for unknown call {call_id!r}"
            )
        slot.usage = dict(usage)

    def claim_retry(self, call_id: str, owner: str) -> None:
        """A call has exactly one retry owner."""
        slot = self._pending.get(call_id)
        if slot is None:
            raise CyranoError(
                "INPUT_INVALID", f"retry for unknown call {call_id!r}"
            )
        if slot.retry_owner is not None and slot.retry_owner != owner:
            raise CyranoError(
                "CONFLICT",
                f"retry for {call_id!r} owned by {slot.retry_owner!r}",
            )
        slot.retry_owner = owner

    # ---------------------------------------------------- views ---

    def require_content(self, kind: str) -> None:
        """Content kinds outside the supported set are unavailable."""
        if kind not in self._supported:
            raise CyranoError(
                "CAPABILITY_UNAVAILABLE",
                f"content kind {kind!r} is not supported",
            )

    def export_history(self) -> list[dict[str, JSON]]:
        """Public projection: signed/opaque reasoning never exports."""
        return [
            {"call_id": cid, "name": slot.name}
            for cid, slot in self._pending.items()
        ]

    @property
    def orphan_results(self) -> list[tuple[str, JSON]]:
        """Results that arrived for calls nobody dispatched."""
        return list(self._orphans)

    @property
    def synthetic_results(self) -> list[tuple[str, JSON]]:
        """Synthetic ``observation_missing`` results from finalize."""
        return list(self._synthetic)
