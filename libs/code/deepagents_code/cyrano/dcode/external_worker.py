"""Optional external worker delegation over MCP snapshots / ACP / A2A.

A peer's declarations are untrusted metadata, never grants: usable
capability is the intersection of what the peer declares and what the
local permit allows. Peer ``completed`` means an artifact arrived, not
that acceptance passed — a local trusted runner verifies the artifact.
Cancel is a request, not a stop confirmation; late artifacts are billed
and audited but fenced out by generation. Submit timeouts leave the
delegation ``unknown`` — never a silent new task or a blind retry.
"""

from __future__ import annotations

import io
import ipaddress
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

STAGES = frozenset(
    {
        "unknown",
        "configured",
        "installed",
        "verified",
        "authorized",
        "active",
    }
)
PROTOCOLS = frozenset({"acp", "a2a"})
PEER_STATES = frozenset(
    {
        "accepted",
        "running",
        "input_required",
        "completed",
        "failed",
        "cancelled",
        "unknown",
    }
)


@dataclass(frozen=True, slots=True)
class DelegationEnvelope:
    """The sealed delegation request; fields follow runtime.schema."""

    delegation_id: str
    task_id: str
    generation: int
    protocol: str
    protocol_revision: str
    peer_identity: str
    capability_snapshot: str
    workspace_mapping: str
    input_refs: tuple[str, ...]
    budget_ref: str
    deadline_at: str
    execution_permit_ref: str
    expected_output_contract: str


@dataclass(frozen=True, slots=True)
class PeerReport:
    """A peer's status report; ``completed`` is delivery, not pass."""

    request_id: str
    state: str
    artifact_refs: tuple[str, ...] = ()
    usage_units: int = 0


@dataclass(frozen=True, slots=True)
class DelegationReceipt:
    """The local record of a submit; timeout leaves it unknown."""

    delegation_id: str
    external_ref: str | None
    state: str


@dataclass(frozen=True, slots=True)
class CapabilityDecision:
    """Usable capabilities = declared ∩ locally granted."""

    usable: frozenset[str]
    refused: frozenset[str]


class ExternalWorkerPort(Protocol):
    """A transport adapter for one configured external worker."""

    def submit(self, envelope: DelegationEnvelope) -> str:
        """Send the envelope; return the peer's request id."""
        ...

    def query(self, request_id: str) -> PeerReport:
        """Poll the peer; an unreachable peer reports ``unknown``."""
        ...

    def cancel(self, request_id: str) -> None:
        """Send cancel; a missing response proves nothing."""
        ...


class ExternalWorkerGateway:
    """Policy gate in front of an optional external worker port."""

    def __init__(
        self,
        *,
        port: ExternalWorkerPort | None,
        repo: ScopedRepository | None = None,
        scope_id: str = "",
        workspace_map: Mapping[str, str] | None = None,
        allowed_egress: frozenset[str] | None = None,
        granted_capabilities: frozenset[str] | None = None,
        max_artifact_bytes: int = 10_000_000,
        max_archive_ratio: int = 100,
    ) -> None:
        """Bind policy; a missing port is ``unavailable``, not fatal."""
        self._port: ExternalWorkerPort | None = port
        self._repo: ScopedRepository | None = repo
        self._scope: str = scope_id
        self._workspace_map: dict[str, str] = dict(workspace_map or {})
        self._egress: frozenset[str] = frozenset(allowed_egress or ())
        self._granted: frozenset[str] = frozenset(granted_capabilities or ())
        self._max_bytes: int = max_artifact_bytes
        self._max_ratio: int = max_archive_ratio
        self._stage: str = "configured" if port is not None else "unknown"
        self._schema_digest: str | None = None

    # -- handshake / capability negotiation ---------------------------

    def pin_schema(self, schema_digest: str) -> None:
        """Pin the tool schema digest the handshake observed."""
        self._schema_digest = schema_digest
        if self._stage == "configured":
            self._stage = "verified"

    def authorize(self) -> None:
        """Move a verified worker to authorized; no stage is skipped."""
        if self._stage != "verified":
            raise CyranoError(
                "WORKER_UNAVAILABLE",
                f"cannot authorize from {self._stage}",
            )
        self._stage = "authorized"

    def negotiate(
        self, declared_capabilities: frozenset[str]
    ) -> CapabilityDecision:
        """Intersect peer declarations with local grants.

        An AgentCard claiming broader access never widens the local
        permit; the result is only what both sides allow.
        """
        usable = declared_capabilities & self._granted
        return CapabilityDecision(
            usable=usable,
            refused=declared_capabilities - self._granted,
        )

    def check_schema_fresh(self, current_digest: str) -> None:
        """A changed tool schema stops invocations bound to the old."""
        if self._schema_digest != current_digest:
            raise CyranoError(
                "CAPABILITY_STALE",
                "peer schema changed; re-verify the inventory",
            )

    def ingest_tool_metadata(
        self, descriptions: Mapping[str, str]
    ) -> Mapping[str, Mapping[str, str]]:
        """Tool descriptions are untrusted data, never instructions."""
        return {
            name: {"description": text, "trust": "untrusted_declaration"}
            for name, text in descriptions.items()
        }

    # -- submit / query / cancel ---------------------------------------

    def submit(
        self, envelope: DelegationEnvelope, *, stream_id: str = ""
    ) -> DelegationReceipt:
        """Submit under the pinned contract; timeout stays unknown."""
        if self._port is None or self._stage not in {
            "authorized",
            "active",
        }:
            raise CyranoError(
                "WORKER_UNAVAILABLE",
                "no authorized external worker",
            )
        if envelope.protocol not in PROTOCOLS:
            raise CyranoError("INPUT_INVALID", envelope.protocol)
        if (
            self._schema_digest is not None
            and envelope.capability_snapshot != self._schema_digest
        ):
            raise CyranoError(
                "CAPABILITY_STALE",
                "envelope binds a different capability snapshot",
            )
        self._record(envelope, "submitted", None, stream_id)
        try:
            external_ref = self._port.submit(envelope)
        except CyranoError:
            # A local refusal means the envelope never dispatched.
            self._record(envelope, "rejected", None, stream_id)
            raise
        except Exception:  # noqa: BLE001 - transport outcome unknown
            # The peer may have received it; unknown, never success.
            self._record(envelope, "unknown", None, stream_id)
            return DelegationReceipt(envelope.delegation_id, None, "unknown")
        self._record(envelope, "submitted", external_ref, stream_id)
        self._stage = "active"
        return DelegationReceipt(
            envelope.delegation_id, external_ref, "submitted"
        )

    def query(self, request_id: str) -> str:
        """Map a peer state; peer ``completed`` is not acceptance."""
        if self._port is None:
            raise CyranoError("WORKER_UNAVAILABLE", "no worker")
        report = self._port.query(request_id)
        if report.state not in PEER_STATES:
            raise CyranoError("INPUT_INVALID", report.state)
        if report.state == "completed":
            return "artifact_delivered"
        return report.state

    def cancel(self, request_id: str, *, stream_id: str = "") -> str:
        """Send cancel; the result is ``cancel_requested``, not done."""
        if self._port is None:
            raise CyranoError("WORKER_UNAVAILABLE", "no worker")
        self._port.cancel(request_id)
        if self._repo is not None and stream_id:
            self._repo.audit(
                stream_id, f"external_cancel_requested ref={request_id}"
            )
        return "cancel_requested"

    def settle_external(
        self,
        request_id: str,
        report: PeerReport,
        *,
        cancelled: bool,
        current_generation: int,
        envelope_generation: int,
        stream_id: str = "",
    ) -> str:
        """Settle a peer result; late or stale results are evidence.

        A cancelled or superseded generation keeps the artifact's cost
        record but never applies it; peer ``completed`` maps to
        ``unverified`` until a local trusted runner passes it.
        """
        if self._repo is not None and report.usage_units:
            self._repo.record_usage(request_id, report.usage_units)
        if cancelled or envelope_generation != current_generation:
            if self._repo is not None and stream_id:
                self._repo.audit(
                    stream_id,
                    f"external_stale ref={request_id} state={report.state}",
                )
            return "stale"
        if report.state == "completed":
            return "unverified"
        if report.state == "cancelled":
            return "cancelled"
        if report.state in {"failed", "accepted", "running"}:
            return report.state
        return "unknown"

    def reconnect(self, request_id: str, *, supports_resume: bool) -> str:
        """Reconnect honestly; no silent replacement task is minted."""
        if not supports_resume:
            return "unsupported"
        return self.query(request_id)

    # -- path / artifact checks ----------------------------------------

    def map_workspace_path(self, remote_uri: str) -> str:
        """Map a remote absolute path through the approved map only."""
        parsed = urlparse(remote_uri)
        candidate = parsed.path if parsed.scheme else remote_uri
        for remote_prefix, local in self._workspace_map.items():
            prefix = remote_prefix.rstrip("/")
            if candidate == prefix:
                return local
            if candidate.startswith(prefix + "/"):
                return local + candidate[len(prefix) :]
        raise CyranoError("ACL_DENIED", remote_uri)

    def check_artifact_uri(self, uri: str) -> None:
        """Fetch policy: scheme, host allowlist, and SSRF denial."""
        parsed = urlparse(uri)
        if parsed.scheme != "https":
            raise CyranoError("ACL_DENIED", f"scheme {parsed.scheme}")
        host = parsed.hostname or ""
        if host not in self._egress:
            raise CyranoError("ACL_DENIED", host)
        try:
            addr = ipaddress.ip_address(host)
        except ValueError:
            return
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_multicast
            or addr.is_reserved
        ):
            raise CyranoError("ACL_DENIED", f"address {host}")

    def inspect_artifact(self, data: bytes, *, media_type: str) -> None:
        """Size, archive-bomb, symlink, and path checks on artifacts."""
        if len(data) > self._max_bytes:
            raise CyranoError(
                "INPUT_INVALID", f"artifact exceeds {self._max_bytes}"
            )
        if media_type != "application/zip":
            return
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            total = 0
            for info in archive.infolist():
                total += info.file_size
                name = info.filename
                mode = (info.external_attr >> 16) & 0o170000
                if (
                    name.startswith("/")
                    or ".." in name.split("/")
                    or mode == 0o120000
                    or any(ord(c) < 32 for c in name)
                ):
                    raise CyranoError("INPUT_INVALID", name)
                if info.file_size > self._max_bytes:
                    raise CyranoError("INPUT_INVALID", name)
            if total > self._max_bytes:
                raise CyranoError(
                    "INPUT_INVALID",
                    f"decompressed {total} exceeds {self._max_bytes}",
                )
            compressed = sum(i.compress_size for i in archive.infolist())
            if compressed and total / compressed > self._max_ratio:
                raise CyranoError("INPUT_INVALID", "archive expansion ratio")

    # -- durable record ------------------------------------------------

    def _record(
        self,
        envelope: DelegationEnvelope,
        state: str,
        external_ref: str | None,
        stream_id: str,
    ) -> None:
        if self._repo is None:
            return
        with self._repo.transaction() as db:
            _ = db.execute(
                "INSERT INTO external_delegations VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(delegation_id) DO UPDATE SET "
                "state=excluded.state,external_ref=excluded.external_ref",
                (
                    envelope.delegation_id,
                    self._scope,
                    stream_id,
                    envelope.generation,
                    state,
                    external_ref,
                    "now",
                ),
            )

    def delegation_state(self, delegation_id: str) -> str:
        """Return the durable delegation state, or ``unknown``."""
        if self._repo is None:
            return "unknown"
        row = self._repo.connection.execute(
            "SELECT state FROM external_delegations WHERE delegation_id=?",
            (delegation_id,),
        ).fetchone()
        return str(row[0]) if row else "unknown"
