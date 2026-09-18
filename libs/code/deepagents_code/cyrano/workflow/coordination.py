"""Durable task board, mailbox, budget reservation, and worktree lease.

Every mutation runs inside one ledger transaction: the ready check,
dependency check, write-set conflict check, fence increment, and lease
record commit together — a crash between them cannot produce a half
leased task. A late or unfenced result is stored as stale evidence and
changes nothing. A heartbeat extends a lease but is not progress;
heartbeats without a progress mark hit the time bound and pause.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.sqlite.repository import ScopedRepository


@dataclass(frozen=True, slots=True)
class TaskLease:
    """A fenced claim on one task."""

    task_id: str
    worker_id: str
    fence: int
    lease_until: int


@dataclass(frozen=True, slots=True)
class MailboxMessage:
    """Work data between peers; a body is never an instruction."""

    message_id: str
    sender: str
    payload_digest: str


class TeamCoordinator:
    """Lease tasks, deliver mailbox items, reserve scope budget."""

    def __init__(self, repo: ScopedRepository, scope_id: str) -> None:
        """Bind the coordinator to one scope's ledger."""
        self._repo: ScopedRepository = repo
        self._scope: str = scope_id

    # -- task board ----------------------------------------------------

    def register_task(
        self,
        stream_id: str,
        task_id: str,
        *,
        write_paths: tuple[str, ...],
        depends_on: tuple[str, ...] = (),
        parent_task: str | None = None,
        revision: int = 0,
    ) -> None:
        """Register a ready task; ids are unique inside a stream."""
        with self._repo.transaction() as db:
            self._repo.read_scoped_entity(self._scope, stream_id)
            try:
                _ = db.execute(
                    "INSERT INTO coord_tasks(stream_id,task_id,"
                    "revision,state,write_paths,depends_on,"
                    "parent_task) VALUES (?,?,?,?,?,?,?)",
                    (
                        stream_id,
                        task_id,
                        revision,
                        "ready",
                        json.dumps(sorted(write_paths)),
                        json.dumps(sorted(depends_on)),
                        parent_task,
                    ),
                )
            except Exception as error:
                raise CyranoError(
                    "INPUT_INVALID", f"task {task_id}: {error}"
                ) from error

    def claim_task(
        self,
        stream_id: str,
        task_id: str,
        expected_revision: int,
        worker_id: str,
        *,
        now: int,
        ttl: int = 300,
    ) -> TaskLease:
        """Atomically check readiness+conflicts and mint a fence."""
        with self._repo.transaction() as db:
            self._repo.read_scoped_entity(self._scope, stream_id)
            row = db.execute(
                "SELECT revision,state,write_paths,depends_on,fence "
                "FROM coord_tasks WHERE stream_id=? AND task_id=?",
                (stream_id, task_id),
            ).fetchone()
            if row is None:
                raise CyranoError("TASK_UNKNOWN", task_id)
            revision, state, write_json, deps_json, fence = row
            if revision != expected_revision:
                raise CyranoError(
                    "PERMIT_STALE",
                    f"expected revision {expected_revision}, have {revision}",
                )
            if state != "ready":
                raise CyranoError("LEASE_LOST", f"task is {state}, not ready")
            deps = set(json.loads(deps_json))
            if deps:
                done = {
                    r[0]
                    for r in db.execute(
                        "SELECT task_id FROM coord_tasks WHERE "
                        "stream_id=? AND state='completed'",
                        (stream_id,),
                    )
                }
                if not deps <= done:
                    raise CyranoError(
                        "TASK_NOT_READY",
                        f"dependencies pending: {sorted(deps - done)}",
                    )
            mine = set(json.loads(write_json))
            if mine:
                holders = db.execute(
                    "SELECT task_id,write_paths FROM coord_tasks "
                    "WHERE stream_id=? AND state='leased' AND "
                    "lease_until>?",
                    (stream_id, now),
                ).fetchall()
                for holder_id, holder_paths in holders:
                    if mine & set(json.loads(holder_paths)):
                        raise CyranoError(
                            "RESOURCE_CONFLICT",
                            f"{task_id} write-set overlaps {holder_id}",
                        )
            _ = db.execute(
                "UPDATE coord_tasks SET state='leased',worker_id=?,"
                "fence=fence+1,last_heartbeat=?,lease_until=? "
                "WHERE stream_id=? AND task_id=? AND revision=?",
                (worker_id, now, now + ttl, stream_id, task_id, revision),
            )
            return TaskLease(task_id, worker_id, int(fence) + 1, now + ttl)

    def heartbeat(
        self,
        stream_id: str,
        lease: TaskLease,
        *,
        now: int,
        ttl: int = 300,
        progress: bool = False,
        progress_deadline: int | None = None,
    ) -> TaskLease:
        """Extend a lease; heartbeat alone is not progress.

        When ``progress_deadline`` passed with no progress mark the
        task pauses for review instead of silently running on.
        """
        paused = False
        with self._repo.transaction() as db:
            row = self._lease_row(db, stream_id, lease)
            mark = row[6]
            if (
                progress_deadline is not None
                and not mark
                and not progress
                and now > progress_deadline
            ):
                paused = True
                _ = db.execute(
                    "UPDATE coord_tasks SET state='recovery_check' "
                    "WHERE stream_id=? AND task_id=?",
                    (stream_id, lease.task_id),
                )
            else:
                _ = db.execute(
                    "UPDATE coord_tasks SET last_heartbeat=?,"
                    "lease_until=?,progress_mark=? "
                    "WHERE stream_id=? AND task_id=?",
                    (
                        now,
                        now + ttl,
                        1 if (mark or progress) else 0,
                        stream_id,
                        lease.task_id,
                    ),
                )
        # The pause commits before the error surfaces — a rolled-back
        # recovery_check would silently leave the task leased.
        if paused:
            raise CyranoError(
                "NO_PROGRESS",
                "heartbeat without progress past the bound",
            )
        return TaskLease(
            lease.task_id, lease.worker_id, lease.fence, now + ttl
        )

    def settle(
        self,
        stream_id: str,
        lease: TaskLease,
        result_digest: str,
        *,
        outcome: str = "completed",
    ) -> None:
        """Commit a result only for the fenced live owner.

        A stale or expired lease keeps the result in the audit row but
        the task state does not move.
        """
        if outcome not in {"completed", "failed"}:
            raise CyranoError("INVALID_OUTCOME", outcome)
        stale_reason: str | None = None
        with self._repo.transaction() as db:
            try:
                self._lease_row(db, stream_id, lease)
            except CyranoError:
                stale_reason = "lease lost before result arrived"
            if stale_reason is None:
                parent = db.execute(
                    "SELECT parent_task FROM coord_tasks WHERE "
                    "stream_id=? AND task_id=?",
                    (stream_id, lease.task_id),
                ).fetchone()
                if parent is not None and parent[0]:
                    state = db.execute(
                        "SELECT state FROM coord_tasks WHERE "
                        "stream_id=? AND task_id=?",
                        (stream_id, parent[0]),
                    ).fetchone()
                    if state is not None and state[0] == "cancelled":
                        stale_reason = "parent cancelled; result is audit-only"
            if stale_reason is None:
                _ = db.execute(
                    "UPDATE coord_tasks SET state=?,result_digest=? "
                    "WHERE stream_id=? AND task_id=? AND fence=?",
                    (
                        outcome,
                        result_digest,
                        stream_id,
                        lease.task_id,
                        lease.fence,
                    ),
                )
        if stale_reason is not None:
            # Durable evidence of the late result; state never moved.
            self._repo.audit(
                stream_id,
                f"stale_result task={lease.task_id} "
                f"digest={result_digest} reason={stale_reason}",
            )
            raise CyranoError("RESULT_STALE", stale_reason)
        return

    def reclaim_expired(self, stream_id: str, *, now: int) -> tuple[str, ...]:
        """Recover expired leases into ``recovery_check``.

        A recovered task is not blindly re-run: it needs the external
        side-effect check before any dispatch.
        """
        with self._repo.transaction() as db:
            rows = db.execute(
                "SELECT task_id FROM coord_tasks WHERE stream_id=? "
                "AND state='leased' AND lease_until<=?",
                (stream_id, now),
            ).fetchall()
            for (task_id,) in rows:
                _ = db.execute(
                    "UPDATE coord_tasks SET state='recovery_check',"
                    "worker_id=NULL WHERE stream_id=? AND task_id=?",
                    (stream_id, task_id),
                )
            return tuple(str(r[0]) for r in rows)

    def cancel_task(self, stream_id: str, task_id: str) -> None:
        """Cancel a task; a completed child keeps its cost record."""
        with self._repo.transaction() as db:
            row = db.execute(
                "SELECT state FROM coord_tasks WHERE stream_id=? "
                "AND task_id=?",
                (stream_id, task_id),
            ).fetchone()
            if row is None:
                raise CyranoError("TASK_UNKNOWN", task_id)
            if row[0] == "completed":
                return  # recorded cost stays; nothing to cancel
            _ = db.execute(
                "UPDATE coord_tasks SET state='cancelled' WHERE "
                "stream_id=? AND task_id=?",
                (stream_id, task_id),
            )

    def _lease_row(
        self, db: sqlite3.Connection, stream_id: str, lease: TaskLease
    ):
        row = db.execute(
            "SELECT state,worker_id,fence,write_paths,depends_on,"
            "last_heartbeat,progress_mark,lease_until FROM coord_tasks "
            "WHERE stream_id=? AND task_id=?",
            (stream_id, lease.task_id),
        ).fetchone()
        if row is None:
            raise CyranoError("TASK_UNKNOWN", lease.task_id)
        state, worker, fence = row[0], row[1], row[2]
        if (
            state != "leased"
            or worker != lease.worker_id
            or int(fence) != lease.fence
        ):
            raise CyranoError("LEASE_LOST", lease.task_id)
        return row

    # -- scope budget --------------------------------------------------

    def set_budget(self, cap: int) -> None:
        """Set the scope budget cap; reservations never exceed it."""
        if cap < 0:
            raise CyranoError("INVALID_BUDGET", "negative cap")
        with self._repo.transaction() as db:
            _ = db.execute(
                "INSERT INTO scope_budgets(scope_id,cap) VALUES (?,?) "
                "ON CONFLICT(scope_id) DO UPDATE SET cap=?",
                (self._scope, cap, cap),
            )

    def reserve_budget(self, amount: int) -> None:
        """Atomically reserve budget; headroom never goes negative."""
        if amount <= 0:
            raise CyranoError("INVALID_BUDGET", "reservation <= 0")
        with self._repo.transaction() as db:
            row = db.execute(
                "SELECT cap,reserved,unknown_liability FROM "
                "scope_budgets WHERE scope_id=?",
                (self._scope,),
            ).fetchone()
            if row is None:
                raise CyranoError("BUDGET_UNBOUND", "no budget cap set")
            cap, reserved, unknown = row
            if unknown:
                raise CyranoError(
                    "BUDGET_BLOCKED",
                    "unknown cost liability blocks new reservations",
                )
            if reserved + amount > cap:
                raise CyranoError(
                    "BUDGET_UNBOUND", "reservation exceeds the cap"
                )
            _ = db.execute(
                "UPDATE scope_budgets SET reserved=reserved+? WHERE "
                "scope_id=?",
                (amount, self._scope),
            )

    def settle_budget(
        self, amount: int, *, usage_observed: int | None
    ) -> None:
        """Settle one reservation against observed usage.

        When the billable operation returned no usage the reservation
        is kept as ``unknown_liability`` — it is never auto-refunded,
        and it blocks new cost-incurring actions until reconciled.
        """
        with self._repo.transaction() as db:
            row = db.execute(
                "SELECT reserved FROM scope_budgets WHERE scope_id=?",
                (self._scope,),
            ).fetchone()
            if row is None:
                raise CyranoError("BUDGET_UNBOUND", "no budget cap set")
            if usage_observed is None:
                _ = db.execute(
                    "UPDATE scope_budgets SET reserved=reserved-?,"
                    "unknown_liability=unknown_liability+? WHERE "
                    "scope_id=?",
                    (amount, amount, self._scope),
                )
            else:
                _ = db.execute(
                    "UPDATE scope_budgets SET reserved=reserved-?,"
                    "spent=spent+? WHERE scope_id=?",
                    (amount, usage_observed, self._scope),
                )

    # -- mailbox -------------------------------------------------------

    def send(
        self,
        stream_id: str,
        message_id: str,
        sender: str,
        recipient: str,
        payload_digest: str,
        *,
        generation: int,
        expires_at: int,
    ) -> MailboxMessage:
        """Deliver at-least-once; message ids are unique forever."""
        with self._repo.transaction() as db:
            try:
                _ = db.execute(
                    "INSERT INTO mailbox VALUES (?,?,?,?,?,?,?,?,0)",
                    (
                        message_id,
                        self._scope,
                        stream_id,
                        sender,
                        recipient,
                        generation,
                        payload_digest,
                        expires_at,
                    ),
                )
            except Exception as error:
                raise CyranoError(
                    "IDEMPOTENCY_CONFLICT", str(error)
                ) from error
        return MailboxMessage(message_id, sender, payload_digest)

    def consume(
        self, stream_id: str, recipient: str, *, now: int
    ) -> MailboxMessage | None:
        """Take one pending message once; expiry is recorded."""
        expired: str | None = None
        with self._repo.transaction() as db:
            row = db.execute(
                "SELECT message_id,sender,payload_digest,expires_at,"
                "scope_id FROM mailbox WHERE stream_id=? AND "
                "recipient=? AND consumed=0 ORDER BY message_id "
                "LIMIT 1",
                (stream_id, recipient),
            ).fetchone()
            if row is None:
                return None
            mid, sender, dig, expires, scope = row
            if scope != self._scope:
                raise CyranoError("ACL_DENIED", "message scope does not match")
            # Mark consumed inside the transaction; the raise happens
            # after commit so the expiry record persists.
            _ = db.execute(
                "UPDATE mailbox SET consumed=1 WHERE message_id=? AND "
                "consumed=0",
                (mid,),
            )
            if now > expires:
                expired = str(mid)
        if expired is not None:
            raise CyranoError("MESSAGE_EXPIRED", expired)
        return MailboxMessage(str(mid), str(sender), str(dig))

    # -- result journal ----------------------------------------------

    def journal_store(
        self,
        stream_id: str,
        node_id: str,
        *,
        snapshot_digest: str,
        input_digest: str,
        result_digest: str,
        status: str,
        now: int,
    ) -> None:
        """Record a result keyed by node+snapshot+input identity."""
        with self._repo.transaction() as db:
            _ = db.execute(
                "INSERT OR REPLACE INTO result_journal VALUES (?,?,?,?,?,?,?)",
                (
                    stream_id,
                    node_id,
                    snapshot_digest,
                    input_digest,
                    result_digest,
                    status,
                    now,
                ),
            )

    def journal_lookup(
        self,
        stream_id: str,
        node_id: str,
        *,
        snapshot_digest: str,
        input_digest: str,
    ) -> str | None:
        """Reuse a result only when snapshot and inputs still match.

        A changed workspace snapshot or input digest is a cache miss —
        the node revalidates instead of reusing a stale result.
        """
        row = self._repo.connection.execute(
            "SELECT result_digest,status FROM result_journal WHERE "
            "stream_id=? AND node_id=? AND snapshot_digest=? AND "
            "input_digest=?",
            (stream_id, node_id, snapshot_digest, input_digest),
        ).fetchone()
        if row is None:
            return None
        return str(row[0])

    # -- worktree lease ------------------------------------------------

    def claim_worktree(
        self,
        stream_id: str,
        task_id: str,
        lease_id: str,
        path: str,
        baseline_digest: str,
        *,
        generation: int,
    ) -> None:
        """Bind a worktree to a run/task/generation with a baseline."""
        with self._repo.transaction() as db:
            self._repo.read_scoped_entity(self._scope, stream_id)
            _ = db.execute(
                "INSERT INTO worktree_leases VALUES (?,?,?,?,?,?,1)",
                (
                    lease_id,
                    stream_id,
                    task_id,
                    generation,
                    path,
                    baseline_digest,
                ),
            )

    def check_worktree_access(self, lease_id: str, path: str) -> None:
        """A lease may only touch paths under its own tree root.

        A worktree is not an OS sandbox — this is the governed boundary
        check. ``.git`` internals and any path escaping the leased root
        are denied, and governed isolation tests must refuse rather
        than pretend containment.
        """
        row = self._repo.connection.execute(
            "SELECT path,active FROM worktree_leases WHERE lease_id=?",
            (lease_id,),
        ).fetchone()
        if row is None or not row[1]:
            raise CyranoError("LEASE_LOST", lease_id)
        root = os.path.normpath(row[0])
        target = os.path.normpath(path)
        if not target.startswith(root + os.sep) and target != root:
            raise CyranoError(
                "ACL_DENIED", f"{path} escapes lease root {root}"
            )
        parts = os.path.relpath(target, root).split(os.sep)
        if ".git" in parts:
            raise CyranoError(
                "ACL_DENIED", "lease may not touch .git internals"
            )

    def cleanup_worktree(self, lease_id: str, current_digest: str) -> str:
        """Cleanup only when the tree still matches its baseline.

        A digest mismatch means the user (or another writer) touched
        the tree — the lease closes but every file is preserved and a
        conflict is reported, never deleted.
        """
        with self._repo.transaction() as db:
            row = db.execute(
                "SELECT baseline_digest,active FROM worktree_leases "
                "WHERE lease_id=?",
                (lease_id,),
            ).fetchone()
            if row is None:
                raise CyranoError("TASK_UNKNOWN", lease_id)
            baseline, active = row
            if not active:
                raise CyranoError("LEASE_LOST", lease_id)
            _ = db.execute(
                "UPDATE worktree_leases SET active=0 WHERE lease_id=?",
                (lease_id,),
            )
            if baseline != current_digest:
                return "conflict_preserved"
            return "cleaned"
