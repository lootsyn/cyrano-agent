"""Scope-aware transactional repository over the target schema.

Every mutation is a single transaction: expected control revision
check, event insert, entity projection, idempotency record, and the
required outbox row. Telemetry uses the global ``event_seq``; the
semantic ``streams.revision`` moves only on control commands.
"""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from deepagents_code.cyrano.contracts.canonical import (
    canonical_bytes,
    digest,
    raw_digest,
)
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.sqlite.migrations import (
    SUPPORTED_SCHEMA_VERSION,
    guard_supported,
)

EXTENSION_DDL = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY, value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    audit_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    stream_id TEXT NOT NULL, detail TEXT NOT NULL, at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS checkpoints (
    stream_id TEXT PRIMARY KEY, format_version INTEGER NOT NULL,
    body_digest TEXT NOT NULL, body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS effect_reservations (
    effect_key TEXT PRIMARY KEY, scope_id TEXT NOT NULL,
    stream_id TEXT NOT NULL, status TEXT NOT NULL
        CHECK(status IN('reserved','dispatched','unknown','cancelled')),
    request_digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS node_reservations (
    stream_id TEXT NOT NULL, node_id TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    PRIMARY KEY(stream_id, node_id)
);
CREATE TABLE IF NOT EXISTS responses (
    stream_id TEXT NOT NULL, request_id TEXT NOT NULL,
    payload_digest TEXT NOT NULL, received_at TEXT NOT NULL,
    PRIMARY KEY(stream_id, request_id)
);
CREATE TABLE IF NOT EXISTS tombstones (
    stream_id TEXT PRIMARY KEY, deleted_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS usage_log (
    job_id TEXT PRIMARY KEY, units INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS event_blobs (
    raw_digest TEXT PRIMARY KEY, scope_id TEXT NOT NULL,
    body BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS coord_tasks (
    stream_id TEXT NOT NULL, task_id TEXT NOT NULL,
    revision INTEGER NOT NULL, state TEXT NOT NULL
        CHECK(state IN('ready','leased','completed','failed',
                       'recovery_check','cancelled')),
    worker_id TEXT, fence INTEGER NOT NULL DEFAULT 0,
    write_paths TEXT NOT NULL, depends_on TEXT NOT NULL,
    budget_reserved INTEGER NOT NULL DEFAULT 0,
    parent_task TEXT, last_heartbeat INTEGER NOT NULL DEFAULT 0,
    progress_mark INTEGER NOT NULL DEFAULT 0,
    lease_until INTEGER NOT NULL DEFAULT 0,
    result_digest TEXT,
    PRIMARY KEY(stream_id, task_id)
);
CREATE TABLE IF NOT EXISTS mailbox (
    message_id TEXT PRIMARY KEY, scope_id TEXT NOT NULL,
    stream_id TEXT NOT NULL, sender TEXT NOT NULL,
    recipient TEXT NOT NULL, generation INTEGER NOT NULL,
    payload_digest TEXT NOT NULL, expires_at INTEGER NOT NULL,
    consumed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS scope_budgets (
    scope_id TEXT PRIMARY KEY, cap INTEGER NOT NULL,
    reserved INTEGER NOT NULL DEFAULT 0,
    spent INTEGER NOT NULL DEFAULT 0,
    unknown_liability INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS worktree_leases (
    lease_id TEXT PRIMARY KEY, stream_id TEXT NOT NULL,
    task_id TEXT NOT NULL, generation INTEGER NOT NULL,
    path TEXT NOT NULL, baseline_digest TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS result_journal (
    stream_id TEXT NOT NULL, node_id TEXT NOT NULL,
    snapshot_digest TEXT NOT NULL, input_digest TEXT NOT NULL,
    result_digest TEXT NOT NULL, status TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY(stream_id, node_id, snapshot_digest, input_digest)
);
CREATE TABLE IF NOT EXISTS run_cancellations (
    stream_id TEXT PRIMARY KEY, generation INTEGER NOT NULL,
    state TEXT NOT NULL
        CHECK(state IN('cancelling','reconciling','reconciled')),
    at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS external_delegations (
    delegation_id TEXT PRIMARY KEY, scope_id TEXT NOT NULL,
    stream_id TEXT NOT NULL, generation INTEGER NOT NULL,
    state TEXT NOT NULL, external_ref TEXT,
    recorded_at TEXT NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class Receipt:
    """Command result: control revision plus idempotency marker."""

    revision: int
    event_id: str
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class Lease:
    """An outbox claim bound to a fencing token."""

    job_id: str
    fence: int
    lease_until: str


class ScopedRepository:
    """A verified-scope ledger; callers open one connection each."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Wrap a caller-owned SQLite connection."""
        self._db = connection

    @classmethod
    def create(cls, path: Path, target_ddl: str) -> "ScopedRepository":
        """Initialize a fresh database with the target schema."""
        db = sqlite3.connect(str(path), isolation_level=None)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(target_ddl)
        db.executescript(EXTENSION_DDL)
        db.execute(f"PRAGMA user_version={SUPPORTED_SCHEMA_VERSION}")
        return cls(db)

    @classmethod
    def open(cls, path: Path) -> "ScopedRepository":
        """Open an existing database after version/integrity checks."""
        db = sqlite3.connect(str(path), isolation_level=None)
        db.execute("PRAGMA foreign_keys=ON")
        try:
            guard_supported(db)
        except BaseException:
            db.close()
            raise
        info_tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if "streams" not in info_tables:
            db.close()
            raise CyranoError(
                "UNINITIALIZED_DATABASE",
                "no schema; use create() or an explicit migration",
            )
        db.executescript(EXTENSION_DDL)
        return cls(db)

    def close(self) -> None:
        """Close the underlying connection."""
        self._db.close()

    # -- transaction helper --------------------------------------------

    @property
    def connection(self) -> sqlite3.Connection:
        """Underlying connection shared by owner modules in one tx."""
        return self._db

    def transaction(self):
        """Public transaction scope; same atomicity as ``_tx``."""
        return self._tx()

    def _tx(self):
        """One immediate transaction; any failure rolls back fully."""
        repo = self

        class _Tx:
            def __enter__(self):
                repo._db.execute("BEGIN IMMEDIATE")
                return repo._db

            def __exit__(self, exc_type, exc, tb):
                repo._db.execute("ROLLBACK" if exc_type else "COMMIT")
                return False

        return _Tx()

    # -- scope and streams ---------------------------------------------

    def register_scope(self, tenant: str, user: str, workspace: str) -> str:
        """Register an exact scope and return its stable scope_id."""
        if not all((tenant, user, workspace)) or "*" in (
            tenant,
            user,
            workspace,
        ):
            raise CyranoError("INVALID_SCOPE", "scope fields must be exact")
        scope_id = digest(
            {"tenant": tenant, "user": user, "workspace": workspace}
        )
        with self._tx() as db:
            db.execute(
                "INSERT OR IGNORE INTO scopes VALUES (?,?,?,?,0)",
                (scope_id, tenant, user, workspace),
            )
        return scope_id

    def create_stream(
        self, scope_id: str, stream_id: str, entity_type: str
    ) -> None:
        """Create a stream owned by an existing scope."""
        with self._tx() as db:
            if not db.execute(
                "SELECT 1 FROM scopes WHERE scope_id=?", (scope_id,)
            ).fetchone():
                raise CyranoError("SCOPE_DENIED", "unknown scope")
            db.execute(
                "INSERT INTO streams VALUES (?,?,0,?,'open')",
                (stream_id, scope_id, entity_type),
            )

    def _stream_scope(self, stream_id: str) -> str | None:
        row = self._db.execute(
            "SELECT scope_id FROM streams WHERE stream_id=?",
            (stream_id,),
        ).fetchone()
        return str(row[0]) if row else None

    def _require_scope(self, scope_id: str, stream_id: str) -> None:
        """Cross-scope access never reveals whether the id exists."""
        owner = self._stream_scope(stream_id)
        if owner is None or owner != scope_id:
            raise CyranoError(
                "SCOPE_DENIED", "entity not readable in this scope"
            )

    # -- commands / events ---------------------------------------------

    def execute_command(
        self,
        scope_id: str,
        actor: str,
        command: str,
        idempotency_key: str,
        payload: Mapping[str, object],
        stream_id: str,
        expected_revision: int,
        *,
        enqueue: bool = False,
        producer: str = "cli",
        producer_seq: int | None = None,
    ) -> Receipt:
        """Idempotent scoped command: CAS, event, outbox in one tx."""
        if payload.get("approved") is True:
            raise CyranoError(
                "WRONG_PURPOSE",
                "payload fields never grant approval",
            )
        request_digest = digest(
            {
                "actor": actor,
                "command": command,
                "payload": payload,
                "expected": expected_revision,
            }
        )
        with self._tx() as db:
            self._require_scope(scope_id, stream_id)
            old = db.execute(
                "SELECT request_digest, response_digest FROM requests "
                "WHERE scope_id=? AND actor=? AND command=? AND "
                "idempotency_key=?",
                (scope_id, actor, command, idempotency_key),
            ).fetchone()
            if old:
                if old[0] != request_digest:
                    raise CyranoError("IDEMPOTENCY_CONFLICT", idempotency_key)
                return Receipt(
                    revision=self._revision(stream_id),
                    event_id="",
                    idempotent_replay=True,
                )
            revision = self._revision(stream_id)
            if revision != expected_revision:
                raise CyranoError("STALE_REVISION", stream_id)
            if producer_seq is None:
                row = db.execute(
                    "SELECT COALESCE(MAX(producer_seq),-1) "
                    "FROM events WHERE producer=?",
                    (producer,),
                ).fetchone()
                producer_seq = int(row[0]) + 1
            event_id = digest(
                {
                    "stream": stream_id,
                    "payload": payload,
                    "key": idempotency_key,
                }
            )
            position = self._next_position(db, stream_id)
            response = canonical_bytes({"revision": revision + 1})
            artifact = self._artifact(db, scope_id, response)
            db.execute(
                "INSERT INTO events(event_id,stream_id,"
                "stream_revision,producer,producer_seq,kind,"
                "schema_version,payload_digest,observed_at,"
                "ingested_at,observation_kind) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    event_id,
                    stream_id,
                    position,
                    producer,
                    producer_seq,
                    command,
                    1,
                    artifact,
                    "now",
                    "now",
                    "control",
                ),
            )
            db.execute(
                "UPDATE streams SET revision=? WHERE stream_id=?",
                (revision + 1, stream_id),
            )
            db.execute(
                "INSERT INTO requests VALUES (?,?,?,?,?,?)",
                (
                    scope_id,
                    actor,
                    command,
                    idempotency_key,
                    request_digest,
                    artifact,
                ),
            )
            if enqueue:
                db.execute(
                    "INSERT INTO outbox(job_id,event_id,scope_id,"
                    "payload_digest,state,deadline,meta_depth) "
                    "VALUES (?,?,?,?, 'pending', ?, 0)",
                    (
                        event_id,
                        event_id,
                        scope_id,
                        artifact,
                        "0",
                    ),
                )
            return Receipt(
                revision=revision + 1,
                event_id=event_id,
                idempotent_replay=False,
            )

    def _revision(self, stream_id: str) -> int:
        row = self._db.execute(
            "SELECT revision FROM streams WHERE stream_id=?",
            (stream_id,),
        ).fetchone()
        return int(row[0]) if row else 0

    def _next_position(self, db, stream_id: str) -> int:
        row = db.execute(
            "SELECT COALESCE(MAX(stream_revision),0) FROM events "
            "WHERE stream_id=?",
            (stream_id,),
        ).fetchone()
        return int(row[0]) + 1

    def _artifact(self, db, scope_id: str, body: bytes) -> str:
        raw = raw_digest(body)
        db.execute(
            "INSERT OR IGNORE INTO artifacts VALUES (?,?,?,?,?,?,?,?)",
            (
                raw,
                scope_id,
                f"blobs/{raw[7:15]}",
                "application/json",
                len(body),
                "internal",
                "derived",
                0,
            ),
        )
        db.execute(
            "INSERT OR IGNORE INTO event_blobs VALUES (?,?,?)",
            (raw, scope_id, body),
        )
        return raw

    def read_artifact(self, scope_id: str, raw_digest_: str) -> bytes | None:
        """Return a stored blob owned by this scope, else None."""
        row = self._db.execute(
            "SELECT body,scope_id FROM event_blobs WHERE raw_digest=?",
            (raw_digest_,),
        ).fetchone()
        if row is None or row[1] != scope_id:
            return None
        return bytes(row[0])

    def record_observation(
        self,
        scope_id: str,
        stream_id: str,
        producer: str,
        producer_seq: int,
        payload: Mapping[str, object],
        *,
        kind: str = "metric",
        observation_kind: str = "telemetry",
    ) -> int:
        """Telemetry append: event_seq advances, control stays."""
        with self._tx() as db:
            return self.record_observation_in(
                db,
                scope_id,
                stream_id,
                producer,
                producer_seq,
                payload,
                kind=kind,
                observation_kind=observation_kind,
            )

    def record_observation_in(
        self,
        db,
        scope_id: str,
        stream_id: str,
        producer: str,
        producer_seq: int,
        payload: Mapping[str, object],
        *,
        kind: str = "metric",
        observation_kind: str = "telemetry",
    ) -> int:
        """Append one event inside an existing ``transaction()`` scope.

        Owner modules use this to commit a domain mutation and its
        observation events atomically; a failed write rolls both back.
        """
        data = canonical_bytes(payload)
        self._require_scope(scope_id, stream_id)
        old = db.execute(
            "SELECT event_id, payload_digest FROM events WHERE "
            "producer=? AND producer_seq=?",
            (producer, producer_seq),
        ).fetchone()
        if old:
            if old[1] != raw_digest(data):
                raise CyranoError(
                    "IDEMPOTENCY_CONFLICT",
                    "same producer_seq, different payload",
                )
            return int(
                db.execute(
                    "SELECT event_seq FROM events WHERE event_id=?",
                    (old[0],),
                ).fetchone()[0]
            )
        artifact = self._artifact(db, scope_id, data)
        position = self._next_position(db, stream_id)
        event_id = digest(
            {"producer": producer, "seq": producer_seq, "payload": payload}
        )
        db.execute(
            "INSERT INTO events(event_id,stream_id,"
            "stream_revision,producer,producer_seq,kind,"
            "schema_version,payload_digest,observed_at,"
            "ingested_at,observation_kind) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                event_id,
                stream_id,
                position,
                producer,
                producer_seq,
                kind,
                1,
                artifact,
                "now",
                "now",
                observation_kind,
            ),
        )
        return int(
            db.execute(
                "SELECT event_seq FROM events WHERE event_id=?",
                (event_id,),
            ).fetchone()[0]
        )

    def read_scoped_entity(self, scope_id: str, stream_id: str) -> int:
        """Read the control revision; cross-scope reads are denied."""
        self._require_scope(scope_id, stream_id)
        return self._revision(stream_id)

    def list_events(
        self, scope_id: str, stream_id: str
    ) -> list[dict[str, object]]:
        """Read scoped event payloads in stream order."""
        self._require_scope(scope_id, stream_id)
        rows = self._db.execute(
            "SELECT a.relative_blob_path FROM events e "
            "JOIN artifacts a ON a.raw_digest=e.payload_digest "
            "WHERE e.stream_id=? ORDER BY e.stream_revision",
            (stream_id,),
        ).fetchall()
        return [{"path": str(r[0])} for r in rows]

    # -- outbox, fencing, cancel ---------------------------------------

    def claim_outbox(
        self, scope_id: str, owner: str, now: int, ttl_seconds: int
    ) -> Lease | None:
        """Claim one pending job; cancelled and live leases excluded."""
        if ttl_seconds <= 0:
            raise CyranoError("INVALID_LEASE", "ttl must be positive")
        floor = self._monotonic_floor()
        base = max(now, floor)
        with self._tx() as db:
            row = db.execute(
                "SELECT job_id,fence,lease_until FROM outbox WHERE "
                "scope_id=? AND (state='pending' OR "
                "(state='leased' AND "
                "CAST(lease_until AS INTEGER)<=?)) "
                "ORDER BY job_id LIMIT 1",
                (scope_id, now),
            ).fetchone()
            if row is None:
                return None
            fence = int(row[1]) + 1
            until = base + ttl_seconds
            db.execute(
                "UPDATE outbox SET state='leased',lease_owner=?,"
                "lease_until=?,fence=fence+1 WHERE job_id=?",
                (owner, str(until), row[0]),
            )
            db.execute(
                "INSERT OR REPLACE INTO meta VALUES ('lease_floor',?)",
                (str(until),),
            )
            return Lease(str(row[0]), fence, str(until))

    def claim_job(
        self,
        scope_id: str,
        job_id: str,
        owner: str,
        now: int,
        ttl_seconds: int,
    ) -> Lease | None:
        """Claim one specific pending job; cancelled stays excluded."""
        if ttl_seconds <= 0:
            raise CyranoError("INVALID_LEASE", "ttl must be positive")
        floor = self._monotonic_floor()
        base = max(now, floor)
        with self._tx() as db:
            row = db.execute(
                "SELECT fence FROM outbox WHERE job_id=? AND "
                "scope_id=? AND state='pending'",
                (job_id, scope_id),
            ).fetchone()
            if row is None:
                return None
            fence = int(row[0]) + 1
            until = base + ttl_seconds
            db.execute(
                "UPDATE outbox SET state='leased',lease_owner=?,"
                "lease_until=?,fence=fence+1 WHERE job_id=?",
                (owner, str(until), job_id),
            )
            db.execute(
                "INSERT OR REPLACE INTO meta VALUES ('lease_floor',?)",
                (str(until),),
            )
            return Lease(job_id, fence, str(until))

    def _monotonic_floor(self) -> int:
        row = self._db.execute(
            "SELECT value FROM meta WHERE key='lease_floor'"
        ).fetchone()
        return int(row[0]) if row else 0

    def finish_outbox(
        self, job_id: str, owner: str, fence: int, now: int
    ) -> None:
        """Complete a lease; stale or expired fences are rejected."""
        row = self._db.execute(
            "UPDATE outbox SET state='completed' WHERE job_id=? AND "
            "lease_owner=? AND fence=? AND state='leased' AND "
            "CAST(lease_until AS INTEGER)>?",
            (job_id, owner, fence, now),
        )
        if row.rowcount != 1:
            raise CyranoError("STALE_LEASE", job_id)

    def submit_result(
        self,
        job_id: str,
        owner: str,
        fence: int,
        usage_units: int,
    ) -> str:
        """Apply a worker result; stale fences lose, usage bills."""
        with self._tx() as db:
            db.execute(
                "INSERT OR IGNORE INTO usage_log VALUES (?,?)",
                (job_id, usage_units),
            )
            row = db.execute(
                "SELECT fence,state,lease_owner FROM outbox WHERE job_id=?",
                (job_id,),
            ).fetchone()
            if row is None:
                raise CyranoError("MISSING_JOB", job_id)
            if int(row[0]) != fence or row[1] != "leased" or row[2] != owner:
                return "stale"
            db.execute(
                "UPDATE outbox SET state='completed' WHERE job_id=?",
                (job_id,),
            )
            return "applied"

    def record_usage(self, job_id: str, usage_units: int) -> None:
        """Bill observed usage even when the outcome stays unknown."""
        with self._tx() as db:
            db.execute(
                "INSERT OR IGNORE INTO usage_log VALUES (?,?)",
                (job_id, usage_units),
            )

    def fail_job(
        self,
        job_id: str,
        owner: str,
        fence: int,
        usage_units: int,
    ) -> str:
        """Record a failed attempt; stale fences lose, usage bills."""
        with self._tx() as db:
            db.execute(
                "INSERT OR IGNORE INTO usage_log VALUES (?,?)",
                (job_id, usage_units),
            )
            row = db.execute(
                "SELECT fence,state,lease_owner FROM outbox WHERE job_id=?",
                (job_id,),
            ).fetchone()
            if row is None:
                raise CyranoError("MISSING_JOB", job_id)
            if int(row[0]) != fence or row[1] != "leased" or row[2] != owner:
                return "stale"
            db.execute(
                "UPDATE outbox SET state='failed' WHERE job_id=?",
                (job_id,),
            )
            return "recorded"

    def cancel_job(self, scope_id: str, job_id: str) -> None:
        """Cancellation wins over any later dispatch attempt."""
        with self._tx() as db:
            db.execute(
                "UPDATE outbox SET state='cancelled' WHERE "
                "job_id=? AND scope_id=?",
                (job_id, scope_id),
            )

    def job_state(self, job_id: str) -> str:
        """Return the current outbox state for a job."""
        row = self._db.execute(
            "SELECT state FROM outbox WHERE job_id=?", (job_id,)
        ).fetchone()
        return str(row[0]) if row else "missing"

    def mark_job_unknown(self, job_id: str) -> None:
        """A write started but never settled is unknown, not failed."""
        with self._tx() as db:
            db.execute(
                "UPDATE outbox SET state='unknown' WHERE job_id=? "
                "AND state='leased'",
                (job_id,),
            )

    def reconcile_unknown(self, job_id: str, disposition: str) -> str:
        """Resolve an unknown-outcome job without a blind retry."""
        if disposition not in {"requeue", "discard", "kept_unknown"}:
            raise CyranoError("INVALID_DISPOSITION", disposition)
        with self._tx() as db:
            if disposition == "requeue":
                db.execute(
                    "UPDATE outbox SET state='pending',lease_owner=NULL "
                    "WHERE job_id=? AND state='unknown'",
                    (job_id,),
                )
            elif disposition == "discard":
                db.execute(
                    "UPDATE outbox SET state='failed' WHERE job_id=? "
                    "AND state='unknown'",
                    (job_id,),
                )
            return disposition

    def export_lag(self, scope_id: str) -> int:
        """Pending outbox count; local work continues offline."""
        row = self._db.execute(
            "SELECT COUNT(*) FROM outbox WHERE scope_id=? AND "
            "state IN('pending','leased','unknown')",
            (scope_id,),
        ).fetchone()
        return int(row[0])

    # -- effects, results, nodes ---------------------------------------

    def reserve_effect(
        self,
        scope_id: str,
        stream_id: str,
        effect_key: str,
        request: Mapping[str, object],
    ) -> bool:
        """Reserve an external effect; committed rows only send."""
        request_digest = digest(request)
        with self._tx() as db:
            self._require_scope(scope_id, stream_id)
            row = db.execute(
                "SELECT request_digest,status FROM "
                "effect_reservations WHERE effect_key=?",
                (effect_key,),
            ).fetchone()
            if row:
                if row[0] != request_digest:
                    raise CyranoError("IDEMPOTENCY_CONFLICT", effect_key)
                return False
            db.execute(
                "INSERT INTO effect_reservations VALUES (?,?,?,?,?)",
                (effect_key, scope_id, stream_id, "reserved", request_digest),
            )
            return True

    def dispatch_effect(self, effect_key: str) -> None:
        """Mark dispatch; only a committed reservation can dispatch."""
        with self._tx() as db:
            row = db.execute(
                "UPDATE effect_reservations SET status='dispatched' "
                "WHERE effect_key=? AND status='reserved'",
                (effect_key,),
            )
            if row.rowcount != 1:
                raise CyranoError("EFFECT_NOT_RESERVED", effect_key)

    def mark_effect_unknown(self, effect_key: str) -> None:
        """A dispatched-then-revoked effect is unknown, not applied."""
        with self._tx() as db:
            db.execute(
                "UPDATE effect_reservations SET status='unknown' "
                "WHERE effect_key=? AND status='dispatched'",
                (effect_key,),
            )

    def reserve_node(self, scope_id: str, stream_id: str, node_id: str) -> str:
        """Idempotent node resume: the same node keeps its decision."""
        with self._tx() as db:
            self._require_scope(scope_id, stream_id)
            row = db.execute(
                "SELECT decision_id FROM node_reservations WHERE "
                "stream_id=? AND node_id=?",
                (stream_id, node_id),
            ).fetchone()
            if row:
                return str(row[0])
            decision = digest({"stream": stream_id, "node": node_id})
            db.execute(
                "INSERT INTO node_reservations VALUES (?,?,?)",
                (stream_id, node_id, decision),
            )
            return decision

    def record_response(
        self,
        scope_id: str,
        stream_id: str,
        request_id: str,
        payload: Mapping[str, object],
    ) -> None:
        """Responses map to their request id regardless of order."""
        with self._tx() as db:
            self._require_scope(scope_id, stream_id)
            db.execute(
                "INSERT OR REPLACE INTO responses VALUES (?,?,?,?)",
                (stream_id, request_id, digest(payload), "now"),
            )

    def response_for(
        self, scope_id: str, stream_id: str, request_id: str
    ) -> str | None:
        """Fetch a recorded response digest by request id."""
        self._require_scope(scope_id, stream_id)
        row = self._db.execute(
            "SELECT payload_digest FROM responses WHERE "
            "stream_id=? AND request_id=?",
            (stream_id, request_id),
        ).fetchone()
        return str(row[0]) if row else None

    # -- approvals, checkpoints, audit ---------------------------------

    def record_approval(
        self,
        scope_id: str,
        approval_id: str,
        subject_digest: str,
        expires_at: int,
    ) -> None:
        """Register an approval bound to an existing subject digest."""
        with self._tx() as db:
            artifact = self._artifact(db, scope_id, b"{}")
            db.execute(
                "INSERT OR IGNORE INTO subjects VALUES (?,?,?,?,?)",
                (subject_digest, "generic", 1, scope_id, artifact),
            )
            db.execute(
                "INSERT INTO approvals(approval_id,subject_digest,"
                "scope_id,purpose,issuer,audience,nonce,issued_at,"
                "expires_at,signature_ref) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    approval_id,
                    subject_digest,
                    scope_id,
                    "execute",
                    "test",
                    "runner",
                    approval_id,
                    "0",
                    str(expires_at),
                    "sig",
                ),
            )

    def revoke_approval(self, approval_id: str, revision: int) -> None:
        """A committed revoke blocks every later dispatch."""
        with self._tx() as db:
            db.execute(
                "UPDATE approvals SET revoked_revision=? WHERE approval_id=?",
                (revision, approval_id),
            )

    def approval_usable(self, approval_id: str, now: int) -> bool:
        """Expired or revoked approvals cannot authorize dispatch."""
        row = self._db.execute(
            "SELECT expires_at,revoked_revision FROM approvals "
            "WHERE approval_id=?",
            (approval_id,),
        ).fetchone()
        if row is None:
            return False
        if row[1] is not None:
            return False
        return int(row[0]) > now

    def write_checkpoint(
        self,
        stream_id: str,
        format_version: int,
        body: Mapping[str, object],
    ) -> None:
        """Persist a versioned checkpoint blob."""
        data = canonical_bytes(body)
        with self._tx() as db:
            db.execute(
                "INSERT OR REPLACE INTO checkpoints VALUES (?,?,?,?)",
                (stream_id, format_version, raw_digest(data), data.decode()),
            )

    def read_checkpoint(
        self, stream_id: str, reader_version: int
    ) -> dict[str, object]:
        """An old reader refuses new checkpoints; no default init."""
        row = self._db.execute(
            "SELECT format_version,body_digest,body FROM "
            "checkpoints WHERE stream_id=?",
            (stream_id,),
        ).fetchone()
        if row is None:
            raise CyranoError("CORRUPT_CHECKPOINT", "no checkpoint recorded")
        if int(row[0]) > reader_version:
            raise CyranoError(
                "VERSION_CONFLICT",
                f"checkpoint v{row[0]} exceeds reader v{reader_version}",
            )
        body = str(row[2]).encode()
        if raw_digest(body) != row[1]:
            raise CyranoError(
                "CORRUPT_CHECKPOINT", "checkpoint digest mismatch"
            )
        return json.loads(body)

    def audit(self, stream_id: str, detail: str) -> None:
        """Audit writes fail closed when the database cannot write."""
        try:
            with self._tx() as db:
                db.execute(
                    "INSERT INTO audit_log(stream_id,detail,at) "
                    "VALUES (?,?,'now')",
                    (stream_id, detail),
                )
        except sqlite3.OperationalError as exc:
            if "full" in str(exc):
                raise CyranoError("AUDIT_UNAVAILABLE", str(exc)) from exc
            raise

    def mark_blocked(self, stream_id: str, reason: str) -> None:
        """A lost sandbox blocks the stream but preserves its data."""
        with self._tx() as db:
            db.execute(
                "UPDATE streams SET status='blocked' WHERE stream_id=?",
                (stream_id,),
            )
            db.execute(
                "INSERT INTO audit_log(stream_id,detail,at) "
                "VALUES (?,?,'now')",
                (stream_id, f"blocked:{reason}"),
            )

    # -- backup / restore / tombstones ---------------------------------

    def delete_stream(self, stream_id: str, at: str) -> None:
        """Deletion records a tombstone that wins over restores."""
        with self._tx() as db:
            db.execute(
                "INSERT OR REPLACE INTO tombstones VALUES (?,?)",
                (stream_id, at),
            )
            db.execute(
                "DELETE FROM outbox WHERE event_id IN "
                "(SELECT event_id FROM events WHERE stream_id=?)",
                (stream_id,),
            )
            db.execute(
                "DELETE FROM events WHERE stream_id=?",
                (stream_id,),
            )
            db.execute(
                "DELETE FROM streams WHERE stream_id=?",
                (stream_id,),
            )

    def backup(self, backup_path: Path) -> None:
        """Consistent online backup via the SQLite backup API."""
        dest = sqlite3.connect(str(backup_path))
        try:
            self._db.backup(dest)
        finally:
            dest.close()

    def restore(self, backup_path: Path) -> None:
        """Restore a backup while keeping recorded tombstones."""
        tombstoned = [
            str(row[0])
            for row in self._db.execute("SELECT stream_id FROM tombstones")
        ]
        source = sqlite3.connect(str(backup_path))
        try:
            source.backup(self._db)
        finally:
            source.close()
        self._db.executescript(EXTENSION_DDL)
        with self._tx() as db:
            for stream_id in tombstoned:
                db.execute(
                    "INSERT OR REPLACE INTO tombstones VALUES (?, 'restored')",
                    (stream_id,),
                )
                db.execute(
                    "DELETE FROM outbox WHERE event_id IN "
                    "(SELECT event_id FROM events WHERE "
                    "stream_id=?)",
                    (stream_id,),
                )
                db.execute(
                    "DELETE FROM events WHERE stream_id=?",
                    (stream_id,),
                )
                db.execute(
                    "DELETE FROM streams WHERE stream_id=?",
                    (stream_id,),
                )

    def verify_integrity(self) -> bool:
        """Return true only for a clean integrity_check."""
        row = self._db.execute("PRAGMA integrity_check").fetchone()
        return bool(row) and row[0] == "ok"
