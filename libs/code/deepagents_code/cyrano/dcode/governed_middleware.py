"""Governed-obligation mediation inside the real dcode agent loop.

This middleware is registered through the native extension API and
sits inside the same model/tool wrap chain as every other agent
middleware — it is not a second executor. Two boundaries matter:

* ``wrap_model_call`` / ``awrap_model_call`` — the last safe
  request-construction boundary before the provider handler. The
  session's ``currency_check`` runs first (a rule that moved,
  expired, or was revoked after approval stops dispatch), then the
  wire observer digests the serialized request, then the native
  chain continues unchanged.
* ``wrap_tool_call`` / ``awrap_tool_call`` — every tool call is
  mapped to a broker decision. Unknown tools are refused; mutating
  calls re-verify the permit at the apply boundary (a mid-run
  revocation still blocks the effect) and record the touched path.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.kernel.actions import (
    ActionBroker,
    Grant,
)
from deepagents_code.cyrano.kernel.approvals import (
    SignedPermit,
    verify_permit,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Iterable

    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey,
    )
    from langchain.agents.middleware.types import (
        ModelRequest,
        ModelResponse,
        ToolCallRequest,
    )
    from langchain_core.messages import AIMessage

    from deepagents_code.cyrano.dcode.wire import WireCapture
    from deepagents_code.cyrano.memory.obligations import RuleObligation

#: Tool name → (ACL action, path argument). ``write`` resolves to
#: ``create`` or ``write_existing`` at call time by preexistence.
#: Tools absent from this table are refused ``UNSUPPORTED_TOOL``
#: unless the operator explicitly lists them as unmediated.
PATH_ACTIONS: Mapping[str, tuple[str, str]] = {
    "read_file": ("read", "file_path"),
    "write_file": ("write", "file_path"),
    "edit_file": ("write_existing", "file_path"),
    "delete": ("delete", "file_path"),
    "ls": ("read", "path"),
    "glob": ("read", "path"),
    "grep": ("read", "path"),
}

_MUTATING = frozenset({"create", "write_existing", "delete"})


def _workspace_path(raw: object, root: Path) -> str:
    """Resolve a tool path argument to a workspace-relative grant path.

    The governed backend runs in real-path mode: an absolute argument
    must resolve inside ``root`` (no silent remap — a grant on
    ``etc/passwd`` must never authorize the host file), and a
    relative argument resolves under ``root``. Traversal and
    backslash forms are refused.
    """
    if not isinstance(raw, str) or not raw:
        raise CyranoError("ACL_DENIED", "missing path argument")
    if "\\" in raw:
        raise CyranoError("ACL_DENIED", raw)
    pure = PurePosixPath(raw)
    if pure.is_absolute():
        root_posix = PurePosixPath(root.resolve().as_posix())
        try:
            pure = pure.relative_to(root_posix)
        except ValueError as exc:
            raise CyranoError("ACL_DENIED", raw) from exc
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise CyranoError("ACL_DENIED", raw)
    return str(pure)


def _tool_name(tool: object) -> str | None:
    """Registered tool name, matching the runtime merge rule."""
    if isinstance(tool, dict):
        function = tool.get("function")
        if isinstance(function, dict):
            name = function.get("name")
            return name if isinstance(name, str) else None
        name = tool.get("name")
        return name if isinstance(name, str) else None
    name = getattr(tool, "name", None)
    return name if isinstance(name, str) else None


def _merged_tools(
    existing: Sequence[BaseTool | dict[str, Any]] | None,
    registered: Iterable[object],
) -> list[BaseTool | dict[str, Any]]:
    """Mirror the runtime middleware's deterministic tool merge.

    ``ExtensionRuntimeMiddleware`` replaces same-named tools and
    appends the rest; replaying that rule over the same registry
    snapshot reproduces the exact tool list the serialized request
    carries — the merge is idempotent, so applying it here and again
    downstream yields identical bytes.
    """
    tools: list[BaseTool | dict[str, Any]] = list(existing or ())
    indexes = {
        name: index
        for index, name in enumerate(map(_tool_name, tools))
        if name is not None
    }
    for item in registered:
        unit_obj: BaseTool | dict[str, Any] | None
        unit = getattr(item, "unit", item)
        if isinstance(unit, dict):
            unit_obj = {str(k): v for k, v in unit.items()}
        elif isinstance(unit, BaseTool):
            unit_obj = unit
        else:
            continue
        name = _tool_name(unit_obj)
        if name is None:
            continue
        index = indexes.get(name)
        if index is None:
            indexes[name] = len(tools)
            tools.append(unit_obj)
        else:
            tools[index] = unit_obj
    return tools


@dataclass(slots=True)
class GovernedSession:
    """Everything a governed attempt binds before dispatch.

    ``currency_check`` is the fail-closed revalidation hook: it must
    re-verify bound obligation revisions and the pinned view against
    live state and raise ``CyranoError`` on any drift. ``freshness``
    records whether the session can observe live revocation —
    ``"pinned"`` sessions honestly report they cannot.
    """

    broker: ActionBroker
    permit: SignedPermit
    trust_root: Ed25519PublicKey
    subject_digest: str
    root: Path
    currency_check: Callable[[], None]
    is_revoked: Callable[[str], bool]
    now: Callable[[], int]
    audit: Callable[[str], None]
    obligations: tuple[RuleObligation, ...] = ()
    unmediated: frozenset[str] = frozenset()
    path_actions: Mapping[str, tuple[str, str]] = field(
        default_factory=lambda: dict(PATH_ACTIONS)
    )
    freshness: str = "live"


class GovernedObligationMiddleware(AgentMiddleware):
    """Mediate model requests and tool calls for a governed session."""

    @property
    def name(self) -> str:
        """Stable registry name for this middleware instance."""
        return "cyrano_governed_obligations"

    def __init__(
        self,
        session: GovernedSession,
        *,
        wire: WireCapture | None = None,
        tool_units: Callable[[], Iterable[object]] | None = None,
    ) -> None:
        """Bind the session, optional wire observer, and tool view."""
        self._session = session
        self._wire = wire
        self._tool_units = tool_units
        self.touched: set[str] = set()
        self.denials: list[str] = []

    # -- model boundary --------------------------------------------

    def _observe_request(self, request: ModelRequest[Any]) -> None:
        self._session.currency_check()
        if self._wire is not None:
            tools = request.tools
            if self._tool_units is not None:
                merged = _merged_tools(tools, self._tool_units())
                if merged != list(tools or ()):
                    request = request.override(tools=merged)
            self._wire.record(request)

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any] | AIMessage],
    ) -> ModelResponse[Any] | AIMessage:
        """Check currency, record wire evidence, then delegate."""
        self._observe_request(request)
        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[
            [ModelRequest[Any]],
            Awaitable[ModelResponse[Any] | AIMessage],
        ],
    ) -> ModelResponse[Any] | AIMessage:
        """Check currency, record wire evidence, then delegate."""
        self._observe_request(request)
        return await handler(request)

    # -- tool boundary ----------------------------------------------

    def _map_call(self, request: ToolCallRequest) -> tuple[str, str] | None:
        """Resolve a tool call to (action, workspace path) or None."""
        name = request.tool_call["name"]
        spec = self._session.path_actions.get(name)
        if spec is None:
            return None
        action, key = spec
        args = request.tool_call.get("args") or {}
        path = _workspace_path(args.get(key), self._session.root)
        if action == "write":
            action = (
                "write_existing"
                if (self._session.root / path).exists()
                else "create"
            )
        return action, path

    def _deny(self, request: ToolCallRequest, code: str, detail: str):
        name = request.tool_call["name"]
        self.denials.append(f"{code}:{name}:{detail}")
        self._session.audit(f"denied:{name}:{code}:{detail}")
        return ToolMessage(
            content=f"CYRANO {code}: {detail}",
            tool_call_id=request.tool_call.get("id") or "",
            name=name,
            status="error",
        )

    def _decide(self, request: ToolCallRequest):
        """One broker decision for a path-bound call; deny on error."""
        name = request.tool_call["name"]
        try:
            mapped = self._map_call(request)
        except CyranoError as exc:
            return None, self._deny(request, exc.code, str(exc))
        if mapped is None:
            if name not in self._session.unmediated:
                return None, self._deny(request, "UNSUPPORTED_TOOL", name)
            self._session.audit(f"tool:{name}:unmediated")
            return None, None
        action, path = mapped
        session = self._session
        decision = session.broker.decide(
            tool=name,
            action=action,
            path=path,
            permit=session.permit,
            trust_root=session.trust_root,
            subject_digest=session.subject_digest,
            now=session.now(),
            is_revoked=session.is_revoked,
            mode="headless",
            preexisting=(session.root / path).exists(),
        )
        if not decision.allowed:
            return None, self._deny(
                request, decision.code, decision.detail or path
            )
        return (action, path), None

    def _authorize_mutation(self, path: str) -> None:
        """Re-verify the permit at the apply boundary; fail closed."""
        session = self._session
        session.audit(f"apply:{session.permit.permit_id}:{path}")
        verify_permit(
            session.permit,
            session.trust_root,
            purpose="execute",
            subject_digest=session.subject_digest,
            now=session.now(),
            is_revoked=session.is_revoked,
        )

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Any],
    ):
        """Mediate a sync tool call through the broker."""
        mapped, denial = self._decide(request)
        if denial is not None:
            return denial
        if mapped is None:
            return handler(request)
        action, path = mapped
        if action in _MUTATING:
            self._authorize_mutation(path)
            result = handler(request)
            if getattr(result, "status", "success") != "error":
                self._session.audit(
                    f"applied:{self._session.permit.permit_id}:{path}"
                )
                self.touched.add(path)
            return result
        self._session.audit(f"read:{request.tool_call['name']}:{path}")
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[Any]],
    ):
        """Mediate an async tool call through the broker."""
        mapped, denial = self._decide(request)
        if denial is not None:
            return denial
        if mapped is None:
            return await handler(request)
        action, path = mapped
        if action in _MUTATING:
            self._authorize_mutation(path)
            result = await handler(request)
            if getattr(result, "status", "success") != "error":
                self._session.audit(
                    f"applied:{self._session.permit.permit_id}:{path}"
                )
                self.touched.add(path)
            return result
        self._session.audit(f"read:{request.tool_call['name']}:{path}")
        return await handler(request)


# ------------------------------------------------ manifest loading --

_MANIFEST_KEYS = frozenset(
    {
        "permit",
        "trust_root",
        "subject_digest",
        "root",
        "grants",
        "tools",
        "unmediated",
        "obligations",
        "scope_id",
        "store_path",
        "audit_path",
        "revocations_path",
        "revoked_permits",
        "revoked_memories",
    }
)

_PERMIT_FIELDS = frozenset(
    {
        "permit_id",
        "subject_digest",
        "shown_digest",
        "user_event_id",
        "scope_id",
        "purpose",
        "audience",
        "nonce",
        "issued_at",
        "expires_at",
        "signature",
    }
)


def _manifest_json(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CyranoError("INPUT_INVALID", f"session manifest: {exc}") from exc
    if not isinstance(data, dict):
        raise CyranoError("INPUT_INVALID", "session manifest not an object")
    unknown = set(data) - _MANIFEST_KEYS
    if unknown:
        raise CyranoError(
            "INPUT_INVALID", f"manifest unknown keys {sorted(unknown)}"
        )
    return {str(k): v for k, v in data.items()}


def _str_map(value: object, *, field: str) -> dict[str, object]:
    """Narrow a manifest value to a string-keyed mapping."""
    if not isinstance(value, Mapping):
        raise CyranoError("INPUT_INVALID", f"manifest {field} must map")
    return {str(k): v for k, v in value.items()}


def _str_seq(value: object, *, field: str) -> tuple[object, ...]:
    """Narrow a manifest value to a sequence (rejects bare strings)."""
    if not isinstance(value, (list, tuple)):
        raise CyranoError("INPUT_INVALID", f"manifest {field} must list")
    return tuple(value)


def _manifest_permit(data: Mapping[str, object]) -> SignedPermit:
    raw = _str_map(data.get("permit"), field="permit")
    unknown = set(raw) - _PERMIT_FIELDS
    if unknown or set(raw) != _PERMIT_FIELDS:
        raise CyranoError(
            "INPUT_INVALID", f"permit fields mismatch {sorted(unknown)}"
        )
    issued_at = raw["issued_at"]
    expires_at = raw["expires_at"]
    if not isinstance(issued_at, int) or not isinstance(expires_at, int):
        raise CyranoError(
            "INPUT_INVALID", "permit.issued_at/expires_at not int"
        )
    for key in _PERMIT_FIELDS - {"issued_at", "expires_at"}:
        if not isinstance(raw[key], str):
            raise CyranoError("INPUT_INVALID", f"permit.{key} not str")
    return SignedPermit(
        permit_id=str(raw["permit_id"]),
        subject_digest=str(raw["subject_digest"]),
        shown_digest=str(raw["shown_digest"]),
        user_event_id=str(raw["user_event_id"]),
        scope_id=str(raw["scope_id"]),
        purpose=str(raw["purpose"]),
        audience=str(raw["audience"]),
        nonce=str(raw["nonce"]),
        issued_at=issued_at,
        expires_at=expires_at,
        signature=str(raw["signature"]),
    )


def _manifest_obligations(
    data: Mapping[str, object],
) -> tuple[RuleObligation, ...]:
    from deepagents_code.cyrano.memory.obligations import (
        RuleObligation,
        parse_scope_rule,
    )

    raw = _str_seq(data.get("obligations", ()), field="obligations")
    obligations: list[RuleObligation] = []
    for index, item_raw in enumerate(raw):
        item = _str_map(item_raw, field=f"obligation {index}")
        spec = parse_scope_rule(item.get("spec", {}))
        provenance = _str_seq(
            item.get("provenance", ()), field=f"obligation {index}.provenance"
        )
        try:
            obligation = RuleObligation(
                obligation_id=str(item["obligation_id"]),
                memory_id=str(item["memory_id"]),
                revision=int(str(item["revision"])),
                scope_id=str(item["scope_id"]),
                checker_id=str(item["checker_id"]),
                checker_digest=str(item["checker_digest"]),
                spec=spec,
                requirement_id=str(item["requirement_id"]),
                acceptance_id=str(item["acceptance_id"]),
                provenance=tuple(str(p) for p in provenance),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise CyranoError(
                "INPUT_INVALID", f"obligation {index}: {exc}"
            ) from exc
        obligations.append(obligation)
    return tuple(obligations)


def session_from_manifest(path: Path) -> GovernedSession:
    """Rebuild a governed session from an operator-written manifest.

    The manifest pins the permit, grants, obligation bindings and
    workspace. When ``store_path`` is present the session checks
    obligation currency against the live store on every model call;
    without it the session is ``freshness="pinned"`` — honest that
    mid-run revocation cannot be observed. ``audit_path`` is required:
    governed runs without a durable audit sink refuse to load.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
    )

    from deepagents_code.cyrano.context.binding import MemoryView
    from deepagents_code.cyrano.contracts.canonical import digest
    from deepagents_code.cyrano.memory.models import MemoryRecord
    from deepagents_code.cyrano.memory.obligations import (
        assert_obligations_current,
    )
    from deepagents_code.cyrano.memory.repository import MemoryRepository
    from deepagents_code.cyrano.sqlite.repository import ScopedRepository

    data = _manifest_json(path)
    permit = _manifest_permit(data)
    root = Path(str(data["root"]))
    audit_path = data.get("audit_path")
    if not audit_path:
        raise CyranoError(
            "CAPABILITY_UNAVAILABLE", "governed session needs audit_path"
        )
    audit_file = Path(str(audit_path))

    def audit(event: str) -> None:
        """Append one audit event line to the durable session sink."""
        with audit_file.open("a", encoding="utf-8") as handle:
            handle.write(event + "\n")

    trust_root = Ed25519PublicKey.from_public_bytes(
        bytes.fromhex(str(data["trust_root"]))
    )
    _ = trust_root.public_bytes(Encoding.Raw, PublicFormat.Raw)

    grants = tuple(
        Grant(
            path=str(g["path"]),
            allow=frozenset(
                str(a)
                for a in _str_seq(g.get("allow", ()), field="grants.allow")
            ),
            deny=frozenset(
                str(a)
                for a in _str_seq(g.get("deny", ()), field="grants.deny")
            ),
        )
        for g in (
            _str_map(item, field="grant")
            for item in _str_seq(data.get("grants", ()), field="grants")
        )
    )
    broker = ActionBroker(
        tools=frozenset(
            str(t) for t in _str_seq(data.get("tools", ()), field="tools")
        ),
        grants=grants,
        audit=audit,
    )
    obligations = _manifest_obligations(data)
    scope_id = str(data.get("scope_id", permit.scope_id))
    revocations_path = data.get("revocations_path")
    static_revoked = frozenset(
        str(p)
        for p in _str_seq(
            data.get("revoked_permits", ()), field="revoked_permits"
        )
    )

    def is_revoked(permit_id: str) -> bool:
        """Check revocation against static and file-based lists."""
        if permit_id in static_revoked:
            return True
        if revocations_path is None:
            return False
        try:
            lines = Path(str(revocations_path)).read_text().splitlines()
        except OSError:
            return False
        return permit_id in {line.strip() for line in lines}

    store_path = data.get("store_path")

    def _live_records() -> tuple[MemoryRecord, ...]:
        repo = ScopedRepository.open(Path(str(store_path)))
        try:
            return tuple(MemoryRepository(repo).list_scope(scope_id))
        finally:
            repo.close()

    if store_path is not None:

        def is_current(mid: str, rev: int) -> bool:
            """Check the bound revision is still the live record."""
            records = {r.memory_id: r for r in _live_records()}
            record = records.get(mid)
            return (
                record is not None
                and record.revision == rev
                and record.status == "active"
            )

        def live_view() -> MemoryView:
            """Project the live revoked-memory set from the store."""
            revoked = frozenset(
                r.memory_id for r in _live_records() if r.status != "active"
            )
            return MemoryView(digest(sorted(revoked)), "live", revoked)

        freshness = "live"
    else:
        revoked_static = frozenset(
            str(r)
            for r in _str_seq(
                data.get("revoked_memories", ()), field="revoked_memories"
            )
        )

        def is_current(mid: str, rev: int) -> bool:
            """Check a revision still matches the pinned binding."""
            bound = {o.memory_id: o.revision for o in obligations}
            return bound.get(mid) == rev

        def live_view() -> MemoryView:
            """Project the manifest's pinned revoked-memory set."""
            return MemoryView(
                digest(sorted(revoked_static)), "pinned", revoked_static
            )

        freshness = "pinned"

    def currency_check() -> None:
        """Fail closed if any bound obligation went stale or revoked."""
        assert_obligations_current(
            obligations,
            is_current=is_current,
            memory_view=live_view(),
        )

    return GovernedSession(
        broker=broker,
        permit=permit,
        trust_root=trust_root,
        subject_digest=str(data["subject_digest"]),
        root=root,
        currency_check=currency_check,
        is_revoked=is_revoked,
        now=lambda: int(time.time()),
        audit=audit,
        obligations=obligations,
        unmediated=frozenset(
            str(t)
            for t in _str_seq(data.get("unmediated", ()), field="unmediated")
        ),
        freshness=freshness,
    )
