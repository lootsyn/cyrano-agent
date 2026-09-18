"""Read-only LSP session manager (RF02).

Sessions carry a generation number; a response that arrives after the
generation advanced is discarded as stale. Queries are restricted to
read methods, require verified capabilities, and bind to a source
snapshot — a changed snapshot makes the session stale.
"""

from dataclasses import dataclass, field

from deepagents_code.cyrano.contracts.canonical import JSON
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.intelligence.lsp import (
    classify_method,
    utf16_column,
)


@dataclass(slots=True)
class AnalysisSession:
    """One bound analysis session with generation and snapshot."""

    session_id: str
    generation: int
    snapshot_digest: str
    capabilities: frozenset[str]
    closed: bool = False
    denied_events: list[str] = field(default_factory=list)


class LspManager:
    """Issue generations, gate queries, discard stale responses."""

    def __init__(self, *, current_snapshot_digest: str) -> None:
        """Bind the manager to the current source snapshot."""
        self._snapshot_digest: str = current_snapshot_digest
        self._seq: int = 0

    def open_analysis(
        self,
        binding: str,
        capabilities: frozenset[str],
    ) -> AnalysisSession:
        """Issue a session bound to the snapshot and capabilities."""
        self._seq += 1
        return AnalysisSession(
            session_id=f"{binding}-{self._seq}",
            generation=self._seq,
            snapshot_digest=self._snapshot_digest,
            capabilities=capabilities,
        )

    def query(
        self,
        session: AnalysisSession,
        method: str,
        params: dict[str, JSON],
    ) -> dict[str, JSON]:
        """Gate a query: read-only, capable, and snapshot-fresh."""
        if session.closed:
            raise CyranoError("INPUT_INVALID", "session is closed")
        if classify_method(method) != "read":
            session.denied_events.append(f"DENIED:{method}")
            raise CyranoError(
                "SCOPE_DENIED",
                f"method {method!r} is not read-only",
            )
        if method not in session.capabilities:
            raise CyranoError(
                "CAPABILITY_UNAVAILABLE",
                f"server did not advertise {method!r}",
            )
        if session.snapshot_digest != self._snapshot_digest:
            raise CyranoError(
                "STALE_SNAPSHOT",
                "source changed since the session was bound",
            )
        return {"method": method, "params": params}

    def receive_response(
        self,
        session: AnalysisSession,
        generation: int,
        response: JSON,
    ) -> JSON | None:
        """Accept a response only for the current generation.

        A late response from an older generation is discarded — it can
        never re-enter state.
        """
        if generation != session.generation:
            return None
        return response

    def position(self, line_text: str, character_offset: int) -> int:
        """Expose UTF-16 conversion through the session boundary."""
        return utf16_column(line_text, character_offset)

    def close_analysis(self, session: AnalysisSession) -> None:
        """Close the session and release its generation."""
        session.closed = True
        session.generation = -1
