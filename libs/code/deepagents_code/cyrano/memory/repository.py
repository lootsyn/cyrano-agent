"""Durable memory records over the scoped ledger connection.

Records live in an additive ``memory_records`` table written in the
same transaction as the ledger audit row, so a crash can never leave
a half-visible activation. Scope is enforced by ``scope_id`` columns;
cross-scope reads are refused before any row is touched.
"""

import json
from dataclasses import dataclass
from typing import cast

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.memory.models import (
    MemoryRecord,
    MemoryStatus,
)
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

MEMORY_DDL = """
CREATE TABLE IF NOT EXISTS memory_records (
    scope_id TEXT NOT NULL, memory_id TEXT NOT NULL,
    revision INTEGER NOT NULL, kind TEXT NOT NULL,
    status TEXT NOT NULL,
    content_digest TEXT NOT NULL, source_digest TEXT NOT NULL,
    evidence_refs TEXT NOT NULL, created_at INTEGER NOT NULL,
    expires_at INTEGER, supersedes TEXT,
    rank INTEGER NOT NULL DEFAULT 0,
    content BLOB NOT NULL,
    PRIMARY KEY (scope_id, memory_id)
);
"""


@dataclass(frozen=True, slots=True)
class MemoryRow:
    """Internal row view; callers receive ``MemoryRecord``."""

    record: MemoryRecord


class MemoryRepository:
    """Scope-bound durable store; every write is one transaction."""

    def __init__(self, repository: ScopedRepository) -> None:
        """Bind to a scoped repository; apply the additive DDL."""
        self._repo = repository
        repository.connection.executescript(MEMORY_DDL)

    def _row_to_record(
        self,
        row: tuple[
            str,
            int,
            str,
            str,
            str,
            str,
            str,
            str,
            int,
            int | None,
            str | None,
            int,
        ],
    ) -> MemoryRecord:
        return MemoryRecord(
            memory_id=row[0],
            revision=row[1],
            scope_id=row[2],
            kind=row[3],
            status=cast(MemoryStatus, row[4]),
            content_digest=row[5],
            source_digest=row[6],
            evidence_refs=tuple(json.loads(row[7])),
            created_at=row[8],
            expires_at=row[9],
            supersedes=row[10],
            rank=row[11],
        )

    def get(self, scope_id: str, memory_id: str) -> MemoryRecord | None:
        """Read one record; scope is part of the primary key."""
        row = self._repo.connection.execute(
            "SELECT memory_id,revision,scope_id,kind,status,"
            "content_digest,source_digest,evidence_refs,created_at,"
            "expires_at,supersedes,rank FROM memory_records "
            "WHERE scope_id=? AND memory_id=?",
            (scope_id, memory_id),
        ).fetchone()
        return None if row is None else self._row_to_record(row)

    def get_content(self, scope_id: str, content_digest: str) -> bytes | None:
        """Fetch a body by digest inside this scope only."""
        row = self._repo.connection.execute(
            "SELECT content FROM memory_records "
            "WHERE scope_id=? AND content_digest=?",
            (scope_id, content_digest),
        ).fetchone()
        return None if row is None else bytes(row[0])

    def restore_content(
        self,
        scope_id: str,
        memory_id: str,
        content_digest: str,
        blob: bytes,
    ) -> bool:
        """Attach a verified blob to an existing row; False if none."""
        cur = self._repo.connection.execute(
            "UPDATE memory_records SET content=? "
            "WHERE scope_id=? AND memory_id=? AND content_digest=?",
            (blob, scope_id, memory_id, content_digest),
        )
        return cur.rowcount > 0

    def list_scope(self, scope_id: str) -> list[MemoryRecord]:
        """List every record visible to this scope only."""
        rows = self._repo.connection.execute(
            "SELECT memory_id,revision,scope_id,kind,status,"
            "content_digest,source_digest,evidence_refs,created_at,"
            "expires_at,supersedes,rank FROM memory_records "
            "WHERE scope_id=? ORDER BY memory_id",
            (scope_id,),
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def put_candidate(
        self, record: MemoryRecord, content: bytes, at: int
    ) -> None:
        """Insert a candidate; revision 1, status candidate.

        An existing record with the same id is a conflict — never a
        silent overwrite. The body is durable with the row so a new
        process can serve the same record.
        """
        if record.status != "candidate":
            raise CyranoError("INPUT_INVALID", "proposals land as candidates")
        with self._repo.transaction() as db:
            existing = db.execute(
                "SELECT revision FROM memory_records "
                "WHERE scope_id=? AND memory_id=?",
                (record.scope_id, record.memory_id),
            ).fetchone()
            if existing is not None:
                raise CyranoError(
                    "IDEMPOTENCY_CONFLICT",
                    f"memory {record.memory_id!r} exists",
                )
            db.execute(
                "INSERT INTO memory_records VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    record.scope_id,
                    record.memory_id,
                    record.revision,
                    record.kind,
                    record.status,
                    record.content_digest,
                    record.source_digest,
                    json.dumps(list(record.evidence_refs)),
                    record.created_at,
                    record.expires_at,
                    record.supersedes,
                    record.rank,
                    content,
                ),
            )
            db.execute(
                "INSERT INTO audit_log(stream_id,detail,at) VALUES (?,?,?)",
                (record.memory_id, "proposed", str(at)),
            )

    def transition(
        self,
        scope_id: str,
        memory_id: str,
        to_status: MemoryStatus,
        *,
        expected_revision: int,
        new_revision: int | None = None,
        supersedes: str | None = None,
        at: int,
    ) -> MemoryRecord:
        """CAS a record's status; a stale expected revision refuses.

        The row update and the audit row commit together — a crash
        cannot produce a half-visible activation.
        """
        with self._repo.transaction() as db:
            row = db.execute(
                "SELECT revision,status FROM memory_records "
                "WHERE scope_id=? AND memory_id=?",
                (scope_id, memory_id),
            ).fetchone()
            if row is None:
                raise CyranoError(
                    "SCOPE_DENIED",
                    "memory not readable in this scope",
                )
            if int(row[0]) != expected_revision:
                raise CyranoError(
                    "STALE_REVISION",
                    f"{memory_id} at r{row[0]}, expected r{expected_revision}",
                )
            revision = new_revision or int(row[0])
            db.execute(
                "UPDATE memory_records SET status=?, revision=?, "
                "supersedes=COALESCE(?, supersedes) "
                "WHERE scope_id=? AND memory_id=?",
                (to_status, revision, supersedes, scope_id, memory_id),
            )
            db.execute(
                "INSERT INTO audit_log(stream_id,detail,at) VALUES (?,?,?)",
                (memory_id, f"status:{to_status}", str(at)),
            )
        record = self.get(scope_id, memory_id)
        assert record is not None
        return record

    def reconcile_ghosts(self, scope_id: str) -> list[str]:
        """Demote records whose audit row is missing.

        A crash between a record write and its audit event leaves a
        ghost; reconciliation removes it from any active view.
        """
        db = self._repo.connection
        rows = db.execute(
            "SELECT m.memory_id FROM memory_records m "
            "WHERE m.scope_id=? AND m.status='active' AND NOT EXISTS "
            "(SELECT 1 FROM audit_log a WHERE a.stream_id=m.memory_id "
            "AND a.detail='status:active')",
            (scope_id,),
        ).fetchall()
        ghost_ids = [str(r[0]) for r in rows]
        for memory_id in ghost_ids:
            record = self.get(scope_id, memory_id)
            if record is not None:
                _ = self.transition(
                    scope_id,
                    memory_id,
                    "stale",
                    expected_revision=record.revision,
                    at=0,
                )
        return ghost_ids
