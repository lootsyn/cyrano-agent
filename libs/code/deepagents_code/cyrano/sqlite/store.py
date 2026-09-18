"""Transactional event/outbox foundation; no model or network access."""

import json
import sqlite3
from pathlib import Path

from deepagents_code.cyrano.contracts.canonical import canonical_bytes, digest
from deepagents_code.cyrano.contracts.types import CyranoError

DDL = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS streams (
    stream TEXT PRIMARY KEY, revision INTEGER NOT NULL CHECK(revision >= 0)
);
CREATE TABLE IF NOT EXISTS events (
    stream TEXT NOT NULL REFERENCES streams(stream), revision INTEGER NOT NULL,
    payload TEXT NOT NULL, payload_digest TEXT NOT NULL,
    PRIMARY KEY(stream, revision)
);
CREATE TABLE IF NOT EXISTS requests (
    stream TEXT NOT NULL, request_key TEXT NOT NULL,
    request_digest TEXT NOT NULL, revision INTEGER NOT NULL,
    PRIMARY KEY(stream, request_key)
);
CREATE TABLE IF NOT EXISTS outbox (
    job_key TEXT PRIMARY KEY, stream TEXT NOT NULL, revision INTEGER NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending', owner TEXT,
    lease_until INTEGER NOT NULL DEFAULT 0, fence INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(stream, revision) REFERENCES events(stream, revision)
);
"""


class EventStore:
    """Own a local SQLite connection; each worker opens its own."""

    def __init__(self, path: str | Path) -> None:
        """Open an autocommit connection with a busy timeout."""
        self.connection = sqlite3.connect(
            str(path), isolation_level=None, timeout=5
        )
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript(DDL)

    def close(self) -> None:
        """Close this connection after callers finish all operations."""
        self.connection.close()

    def append(
        self,
        stream: str,
        expected_revision: int,
        key: str,
        payload: dict[str, object],
        *,
        enqueue: bool = False,
    ) -> int:
        """Append an event and optional outbox row atomically."""
        request_digest = digest(
            {
                "payload": payload,
                "enqueue": enqueue,
                "expected": expected_revision,
            }
        )
        data = canonical_bytes(payload).decode("utf-8")
        db = self.connection
        db.execute("BEGIN IMMEDIATE")
        try:
            old = db.execute(
                "SELECT request_digest, revision FROM requests "
                "WHERE stream=? AND request_key=?",
                (stream, key),
            ).fetchone()
            if old:
                if old[0] != request_digest:
                    raise CyranoError("IDEMPOTENCY_CONFLICT", key)
                db.execute("COMMIT")
                return int(old[1])
            db.execute("INSERT OR IGNORE INTO streams VALUES (?,0)", (stream,))
            revision = int(
                db.execute(
                    "SELECT revision FROM streams WHERE stream=?",
                    (stream,),
                ).fetchone()[0]
            )
            if revision != expected_revision:
                raise CyranoError("STALE_REVISION", stream)
            new = revision + 1
            db.execute(
                "INSERT INTO events VALUES (?,?,?,?)",
                (stream, new, data, digest(payload)),
            )
            db.execute(
                "UPDATE streams SET revision=? WHERE stream=?", (new, stream)
            )
            db.execute(
                "INSERT INTO requests VALUES (?,?,?,?)",
                (stream, key, request_digest, new),
            )
            if enqueue:
                job = digest({"stream": stream, "revision": new})
                db.execute(
                    "INSERT INTO outbox(job_key,stream,revision) "
                    "VALUES (?,?,?)",
                    (job, stream, new),
                )
            db.execute("COMMIT")
            return new
        except BaseException:
            # Cancellation and control-flow exceptions must also release
            # the transaction.
            db.execute("ROLLBACK")
            raise

    def events(self, stream: str) -> list[dict[str, object]]:
        """Read event payloads in order; never calls a model."""
        rows = self.connection.execute(
            "SELECT payload FROM events WHERE stream=? ORDER BY revision",
            (stream,),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def claim(self, owner: str, now: int, ttl: int) -> tuple[str, int] | None:
        """Claim a pending/expired outbox job with a fence token."""
        if ttl <= 0:
            raise CyranoError("INVALID_LEASE", "ttl must be positive")
        db = self.connection
        db.execute("BEGIN IMMEDIATE")
        try:
            row = db.execute(
                "SELECT job_key,fence FROM outbox WHERE state='pending' OR "
                "(state='leased' AND lease_until<=?) ORDER BY rowid LIMIT 1",
                (now,),
            ).fetchone()
            if row is None:
                db.execute("COMMIT")
                return None
            key, fence = str(row[0]), int(row[1]) + 1
            db.execute(
                "UPDATE outbox SET state='leased',owner=?,lease_until=?,"
                "fence=? WHERE job_key=?",
                (owner, now + ttl, fence, key),
            )
            db.execute("COMMIT")
            return key, fence
        except BaseException:
            db.execute("ROLLBACK")
            raise

    def finish(self, key: str, owner: str, fence: int, now: int) -> None:
        """Reject stale workers, including expired leases."""
        row = self.connection.execute(
            "UPDATE outbox SET state='done' WHERE job_key=? AND owner=? "
            "AND fence=? AND state='leased' AND lease_until>?",
            (key, owner, fence, now),
        )
        if row.rowcount != 1:
            raise CyranoError("STALE_LEASE", key)
