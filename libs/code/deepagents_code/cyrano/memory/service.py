"""Memory service facade.

Proposals become candidates; a separate activation decision promotes
them into the release view. Recall, export and search read only
active, in-scope, unexpired, fresh records — a deleted or stale fact
can never be served for cache warmth.
"""

import hashlib
import json
import sqlite3
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.memory.deletion import delete_memory
from deepagents_code.cyrano.memory.invalidation import (
    invalidate_memory,
)
from deepagents_code.cyrano.memory.models import (
    DeletionReceipt,
    MemoryRecord,
)
from deepagents_code.cyrano.memory.recall import (
    RecallResult,
    select_recall,
)
from deepagents_code.cyrano.memory.repository import MemoryRepository


@dataclass(frozen=True, slots=True)
class ExportManifest:
    """Digest-bound manifest of an exported corpus."""

    entries: tuple[tuple[str, str], ...]
    digest: str


class MemoryService:
    """Governed memory lifecycle over the scoped ledger."""

    def __init__(self, repository: MemoryRepository) -> None:
        """Bind the service to a durable memory repository."""
        self._repo: MemoryRepository = repository
        self._quarantine_log: list[str] = []

    # -------------------------------------------------- lifecycle --

    def propose_memory(
        self,
        scope_id: str,
        memory_id: str,
        *,
        kind: str,
        content: bytes,
        source_digest: str,
        evidence_refs: tuple[str, ...],
        at: int,
        expires_at: int | None = None,
        rank: int = 0,
    ) -> MemoryRecord:
        """Store a proposal as a candidate — never active by write."""
        record = MemoryRecord(
            memory_id=memory_id,
            revision=1,
            scope_id=scope_id,
            kind=kind,
            status="candidate",
            content_digest="sha256:" + hashlib.sha256(content).hexdigest(),
            source_digest=source_digest,
            evidence_refs=evidence_refs,
            created_at=at,
            expires_at=expires_at,
            supersedes=None,
            rank=rank,
        )
        self._repo.put_candidate(record, content, at)
        return record

    def activate_memory(
        self,
        scope_id: str,
        memory_id: str,
        *,
        expected_revision: int,
        supersedes: str | None = None,
        at: int,
    ) -> MemoryRecord:
        """Promote a candidate via CAS; stale revision refuses."""
        record = self._repo.get(scope_id, memory_id)
        if record is None:
            raise CyranoError(
                "SCOPE_DENIED", "memory not readable in this scope"
            )
        if record.status not in {"candidate", "stale"}:
            raise CyranoError(
                "INPUT_INVALID",
                f"cannot activate status {record.status}",
            )
        conflict = [
            r.memory_id
            for r in self._repo.list_scope(scope_id)
            if r.status == "active"
            and r.kind == record.kind
            and r.memory_id != memory_id
            and (supersedes is None or r.memory_id != supersedes)
        ]
        if conflict:
            msg = (
                f"active {conflict} share kind "
                f"{record.kind!r}; explicit supersedes required"
            )
            raise CyranoError("MEMORY_CONFLICT", msg)
        if supersedes is not None:
            old = self._repo.get(scope_id, supersedes)
            if old is not None and old.status == "active":
                _ = invalidate_memory(self._repo, scope_id, supersedes, at=at)
        return self._repo.transition(
            scope_id,
            memory_id,
            "active",
            expected_revision=expected_revision,
            new_revision=record.revision + 1,
            supersedes=supersedes,
            at=at,
        )

    def invalidate(self, scope_id: str, memory_id: str, at: int) -> list[str]:
        """Stale a record and its full dependency closure."""
        return invalidate_memory(self._repo, scope_id, memory_id, at=at)

    def delete(
        self,
        scope_id: str,
        memory_id: str,
        *,
        at: int,
        pending_projections: tuple[str, ...] = (),
    ) -> DeletionReceipt:
        """Tombstone a record; it leaves every live view at once."""
        return delete_memory(
            self._repo,
            scope_id,
            memory_id,
            at=at,
            pending_projections=pending_projections,
        )

    # ------------------------------------------------------ reads --

    def get(self, scope_id: str, memory_id: str) -> MemoryRecord | None:
        """Read one record inside the caller's scope."""
        return self._repo.get(scope_id, memory_id)

    def query_memory(
        self,
        scope_id: str,
        now: int,
        available_source_digests: frozenset[str],
        *,
        query_terms: frozenset[str] | None = None,
        limit: int = 10,
    ) -> RecallResult:
        """Immutable active view for one scope.

        A storage failure is ``MEMORY_STORE_UNAVAILABLE`` — never an
        empty success that looks like "no memories".
        """
        try:
            records = self._repo.list_scope(scope_id)
        except sqlite3.Error as exc:
            raise CyranoError("MEMORY_STORE_UNAVAILABLE", str(exc)) from exc
        return select_recall(
            records,
            scope_id,
            now,
            available_source_digests,
            query_terms=query_terms,
            limit=limit,
        )

    def mark_stale_if_source_moved(
        self,
        scope_id: str,
        current_source_digests: frozenset[str],
        at: int,
    ) -> list[str]:
        """Demote active records whose source digest is gone."""
        moved: list[str] = []
        for record in self._repo.list_scope(scope_id):
            if (
                record.status == "active"
                and record.source_digest not in current_source_digests
            ):
                _ = self._repo.transition(
                    scope_id,
                    record.memory_id,
                    "stale",
                    expected_revision=record.revision,
                    at=at,
                )
                moved.append(record.memory_id)
        return moved

    def quarantine(self, scope_id: str, memory_id: str, at: int) -> None:
        """Quarantine hostile content; it stays data, not authority."""
        record = self._repo.get(scope_id, memory_id)
        if record is None:
            raise CyranoError(
                "SCOPE_DENIED", "memory not readable in this scope"
            )
        _ = self._repo.transition(
            scope_id,
            memory_id,
            "quarantined",
            expected_revision=record.revision,
            at=at,
        )
        self._quarantine_log.append(memory_id)

    def reconcile_ghosts(self, scope_id: str) -> list[str]:
        """Demote records that lack their paired audit event."""
        return self._repo.reconcile_ghosts(scope_id)

    # -------------------------------------------------- documents --

    def export_corpus(
        self,
        scope_id: str,
        refs: frozenset[str],
    ) -> ExportManifest:
        """Copy only immutable, active, in-scope digests to export."""
        entries: list[tuple[str, str]] = []
        for record in self._repo.list_scope(scope_id):
            if record.status != "active" or record.content_digest not in refs:
                continue
            entries.append((record.memory_id, record.content_digest))
        manifest = json.dumps(sorted(entries))
        return ExportManifest(
            tuple(sorted(entries)),
            "sha256:" + hashlib.sha256(manifest.encode()).hexdigest(),
        )

    def import_index(
        self,
        scope_id: str,
        manifest: ExportManifest,
        blobs: dict[str, bytes],
    ) -> None:
        """Import blobs verified by digest; a mismatch refuses."""
        for memory_id, content_digest in manifest.entries:
            blob = blobs.get(content_digest)
            if blob is None:
                raise CyranoError(
                    "IMPORT_BLOB_MISSING", f"no blob for {memory_id}"
                )
            actual = "sha256:" + hashlib.sha256(blob).hexdigest()
            if actual != content_digest:
                raise CyranoError(
                    "IMPORT_DIGEST_MISMATCH",
                    f"import digest mismatch for {memory_id}",
                )
            if not self._repo.restore_content(
                scope_id, memory_id, content_digest, blob
            ):
                raise CyranoError(
                    "IMPORT_BLOB_MISSING",
                    f"no in-scope row for {memory_id}",
                )

    def search_documents(
        self,
        scope_id: str,
        query: str,
        *,
        now: int,
        available_source_digests: frozenset[str],
        revalidate: bool = True,
    ) -> list[tuple[str, str]]:
        """Lexical search over active records; empty means empty.

        ``revalidate`` re-checks each hit's freshness before return —
        a stale or deleted body never appears in results.
        """
        results: list[tuple[str, str]] = []
        for record in self._repo.list_scope(scope_id):
            if record.status != "active":
                continue
            if revalidate and (
                record.source_digest not in available_source_digests
                or (record.expires_at is not None and now >= record.expires_at)
            ):
                continue
            body = (
                self._repo.get_content(scope_id, record.content_digest) or b""
            )
            if query.encode() in body or query in record.kind:
                results.append((record.memory_id, record.content_digest))
        return results
