"""Serialized-request observation at the model-call boundary.

Implements the EVAL-WIRE-01 boundary: evidence is captured where the
assembled model request is handed to the provider transport, inside the
extension runtime middleware's ``wrap_model_call`` /
``awrap_model_call`` hook — the last safe request-construction point
before the provider handler runs.

Evidence is digest-based only. Message bodies, provider parameters,
authorization material, cookies, and any secret-bearing transport
structure are never persisted; every content-bearing field is reduced
to a canonical ``CYRANO-C14N-1`` digest plus non-secret role/type
labels. An adapter-level projection can establish
``context_projected`` but never ``wire_confirmed`` — that flag is set
only here, by an observation object that physically saw the serialized
request handed to the provider.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from ..contracts.canonical import digest

if TYPE_CHECKING:
    from collections.abc import Iterable


def _epoch_ms() -> int:
    """Wall-clock milliseconds for the observed_at stamp."""
    return int(time.time() * 1000)


def _safe_dump(value: object) -> object:
    """Return a JSON-safe projection of an arbitrary request value."""
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            return dump(mode="json")
        except (TypeError, ValueError):
            pass
    if isinstance(value, float):
        # Canonical encoding rejects floats by design; evidence binds
        # the textual form instead.
        return repr(value)
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {str(k): _safe_dump(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_dump(v) for v in value]
    return str(value)


def _as_str_map(value: object) -> dict[str, object] | None:
    """Narrow a dumped value to a string-keyed mapping, or None."""
    if not isinstance(value, dict):
        return None
    return {str(k): v for k, v in value.items()}


def _message_projection(message: object) -> dict[str, object]:
    """Project one chat message into a digest-safe structure."""
    proj: dict[str, object] = {}
    dumped = _as_str_map(_safe_dump(message))
    if dumped is not None:
        for key in ("type", "role", "name", "id", "tool_call_id", "status"):
            if dumped.get(key) is not None:
                proj[key] = dumped[key]
        if "content" in dumped:
            proj["content_digest"] = digest(dumped["content"])
        tool_calls = dumped.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            proj["tool_call_count"] = len(tool_calls)
            proj["tool_call_names"] = [
                str(tc.get("name", ""))
                for tc in tool_calls
                if isinstance(tc, dict)
            ]
        for key, value in dumped.items():
            if key not in proj and key not in {
                "content",
                "tool_calls",
                "additional_kwargs",
                "response_metadata",
            }:
                proj[key] = _safe_dump(value)
    else:
        proj["type"] = type(message).__name__
        proj["content_digest"] = digest(str(_safe_dump(message)))
    proj.setdefault("type", type(message).__name__)
    return proj


def _tool_projection(tool: object) -> dict[str, object]:
    """Project a bound tool into its schema identity."""
    dumped = _as_str_map(_safe_dump(tool))
    if dumped is not None and dumped.get("name") is not None:
        return {
            "name": str(dumped["name"]),
            "schema_digest": digest(dumped),
        }
    name = getattr(tool, "name", None)
    schema: object = {}
    schema_fn = getattr(tool, "get_input_schema", None)
    if callable(schema_fn):
        try:
            model = schema_fn()
            schema_method = getattr(model, "model_json_schema", None)
            if not callable(schema_method):
                raise TypeError("no schema projector")
            schema = _safe_dump(schema_method())
        except (TypeError, ValueError, AttributeError):
            schema = {"unprojectable": type(tool).__name__}
    return {
        "name": str(name) if name is not None else type(tool).__name__,
        "schema_digest": digest(schema),
    }


@dataclass(frozen=True, slots=True)
class WireEvidence:
    """Digest-only observation of one serialized model request.

    Carries no message content and no provider transport structure —
    only digests, role/type labels, and run linkage. ``wire_confirmed``
    is True by construction: this record type exists only when the
    observation happened at the provider-request boundary.
    """

    evidence_digest: str
    run_id: str
    sequence: int
    provider: str
    model: str
    message_roles: tuple[str, ...]
    message_digest: str
    context_digest: str
    obligation_digest: str
    tools_digest: str
    model_params_digest: str
    routing_digest: str
    wire_confirmed: bool = True
    observed_at_ms: int = 0


@dataclass(slots=True)
class WireCapture:
    """Boundary observer injected into the extension runtime middleware.

    ``record`` is invoked by ``GovernedObligationMiddleware`` at the
    exact point the assembled request is about to be handed to the
    provider handler. The captured list is the wire evidence for the
    run; ``context_digest``/``obligation_digest`` pin the internal
    projections so a study can distinguish *projected internally* from
    *serialized into the actual request*.
    """

    run_id: str
    context_digest: str = ""
    obligation_digest: str = ""
    routing_digest: str = ""
    now_ms: Callable[[], int] = field(default=_epoch_ms)
    sink: Callable[[WireEvidence], None] | None = None
    _evidence: list[WireEvidence] = field(default_factory=list)

    def record(self, request: object) -> WireEvidence:
        """Digest the request just before provider dispatch."""
        messages = list(getattr(request, "messages", None) or ())
        projections = [_message_projection(m) for m in messages]
        system = getattr(request, "system_message", None)
        if system is not None:
            projections.insert(0, _message_projection(system))
        tools = [
            _tool_projection(t)
            for t in (getattr(request, "tools", None) or ())
        ]
        model = getattr(request, "model", None)
        provider = str(
            getattr(model, "_llm_type", None)
            or getattr(model, "provider", None)
            or "unknown"
        )
        model_id = str(
            getattr(model, "model", None)
            or getattr(model, "model_name", None)
            or getattr(model, "model_id", None)
            or "unknown"
        )
        params = {
            "model_settings": _safe_dump(
                getattr(request, "model_settings", None)
            ),
            "tool_choice": _safe_dump(getattr(request, "tool_choice", None)),
            "response_format": _safe_dump(
                getattr(request, "response_format", None)
            ),
        }
        model_params_digest = digest(params)
        routing = self.routing_digest or digest(
            {
                "provider": provider,
                "model": model_id,
                "params": model_params_digest,
            }
        )
        core = {
            "run_id": self.run_id,
            "sequence": len(self._evidence),
            "provider": provider,
            "model": model_id,
            "messages": projections,
            "context_digest": self.context_digest,
            "obligation_digest": self.obligation_digest,
            "tools": tools,
            "model_params_digest": model_params_digest,
            "routing_digest": routing,
        }
        evidence = WireEvidence(
            evidence_digest=digest(core),
            run_id=self.run_id,
            sequence=len(self._evidence),
            provider=provider,
            model=model_id,
            message_roles=tuple(str(p.get("type", "")) for p in projections),
            message_digest=digest(projections),
            context_digest=self.context_digest,
            obligation_digest=self.obligation_digest,
            tools_digest=digest(tools),
            model_params_digest=model_params_digest,
            routing_digest=routing,
            wire_confirmed=True,
            observed_at_ms=self.now_ms(),
        )
        self._evidence.append(evidence)
        if self.sink is not None:
            self.sink(evidence)
        return evidence

    @property
    def evidence(self) -> tuple[WireEvidence, ...]:
        """Observed request records in capture order."""
        return tuple(self._evidence)

    def digests(self) -> tuple[str, ...]:
        """Evidence digests only — for receipts and manifests."""
        return tuple(e.evidence_digest for e in self._evidence)


def wire_receipt(
    capture: WireCapture | None,
    *,
    context_projected: bool,
) -> dict[str, object]:
    """Honest wire-status receipt for run evidence."""
    if capture is None or not capture.evidence:
        return {
            "wire_confirmed": False,
            "context_projected": context_projected,
            "evidence_refs": (),
        }
    return {
        "wire_confirmed": True,
        "context_projected": context_projected,
        "evidence_refs": capture.digests(),
    }


__all__: Iterable[str] = (
    "WireCapture",
    "WireEvidence",
    "wire_receipt",
)
