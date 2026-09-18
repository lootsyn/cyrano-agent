"""Attempt runner: a durable started → settled job lifecycle.

``run_work`` enqueues a real outbox job, claims its fence, invokes the
worker port, and settles through the ledger — a timeout or crash leaves
the job ``unknown``, never ``failed`` or ``completed`` by guessing.
An unknown outcome is preserved until an explicit reconcile decision;
the runner never re-executes a side-effecting attempt blindly. A user
cancel durably blocks new dispatch on the stream while leased work is
reconciled, and partial observed results are still reported.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

OUTCOMES = frozenset({"completed", "failed", "unknown"})


@dataclass(frozen=True, slots=True)
class WorkOutcome:
    """What a worker port reports; ``unknown`` is a real outcome."""

    status: str
    result_ref: str = ""
    postimage_digest: str | None = None
    usage_units: int = 0
    detail: str = ""


@dataclass(frozen=True, slots=True)
class AttemptReceipt:
    """The runner's durable record of one attempt."""

    attempt_id: str
    job_id: str
    outcome: str
    result_ref: str
    postimage_digest: str | None
    usage_units: int
    detail: str = ""


@dataclass(frozen=True, slots=True)
class CancelReport:
    """What a user cancel actually did; unknowns stay unknown."""

    stream_id: str
    state: str
    cancelled: tuple[str, ...]
    unknown: tuple[str, ...]
    partial_results: tuple[str, ...]


class AttemptRunner:
    """Enqueue → lease → run → settle over the durable outbox."""

    def __init__(self, repo: ScopedRepository, scope_id: str) -> None:
        """Bind the runner to one scope's ledger."""
        self._repo: ScopedRepository = repo
        self._scope: str = scope_id
        self._attempts: dict[str, str] = {}
        self._seq: int = 0

    def run_work(
        self,
        stream_id: str,
        task_id: str,
        *,
        worker: Callable[[str], WorkOutcome],
        now: int,
        lease_ttl: int = 300,
    ) -> AttemptReceipt:
        """Run one attempt; a live ``unknown`` blocks blind retry.

        The job row is committed before the worker is invoked, so a
        crash between start and settle is recoverable evidence, not a
        lost side effect.
        """
        self._require_dispatchable(stream_id)
        prior = self._attempts.get(task_id)
        if prior is not None and self._repo.job_state(prior) == "unknown":
            raise CyranoError(
                "UNKNOWN_OUTCOME",
                f"{task_id} outcome unknown; reconcile before retry",
            )
        self._seq += 1
        attempt_id = f"{task_id}-a{self._seq}"
        revision = self._repo.read_scoped_entity(self._scope, stream_id)
        receipt = self._repo.execute_command(
            self._scope,
            "attempt_runner",
            "run_work",
            attempt_id,
            {"task_id": task_id, "attempt": attempt_id},
            stream_id,
            expected_revision=revision,
            enqueue=True,
        )
        job_id = receipt.event_id
        lease = self._repo.claim_job(
            self._scope, job_id, attempt_id, now, lease_ttl
        )
        if lease is None:
            raise CyranoError("LEASE_LOST", "job not claimable")
        self._attempts[task_id] = job_id
        self._repo.audit(stream_id, f"run_started task={task_id} job={job_id}")
        try:
            outcome = worker(task_id)
        except TimeoutError as exc:
            outcome = WorkOutcome("unknown", detail=str(exc))
        if outcome.status not in OUTCOMES:
            raise CyranoError("INVALID_OUTCOME", outcome.status)
        settled = self._settle(job_id, attempt_id, lease.fence, outcome)
        return AttemptReceipt(
            attempt_id=attempt_id,
            job_id=job_id,
            outcome=settled,
            result_ref=outcome.result_ref,
            postimage_digest=outcome.postimage_digest,
            usage_units=outcome.usage_units,
            detail=outcome.detail,
        )

    def _settle(
        self,
        job_id: str,
        owner: str,
        fence: int,
        outcome: WorkOutcome,
    ) -> str:
        if outcome.status == "unknown":
            self._repo.record_usage(job_id, outcome.usage_units)
            self._repo.mark_job_unknown(job_id)
            return "unknown"
        if outcome.status == "failed":
            state = self._repo.fail_job(
                job_id, owner, fence, outcome.usage_units
            )
            return "failed" if state == "recorded" else "stale"
        state = self._repo.submit_result(
            job_id, owner, fence, outcome.usage_units
        )
        return "completed" if state == "applied" else "stale"

    def recover_inflight(self, stream_id: str) -> tuple[str, ...]:
        """After a restart, leased-but-unsettled jobs become unknown.

        Recovery records the uncertainty; it never re-runs the work.
        """
        rows = self._repo.connection.execute(
            "SELECT o.job_id FROM outbox o JOIN events e ON "
            "e.event_id=o.job_id WHERE o.scope_id=? AND "
            "e.stream_id=? AND o.state='leased'",
            (self._scope, stream_id),
        ).fetchall()
        for (job_id,) in rows:
            self._repo.mark_job_unknown(str(job_id))
            self._repo.audit(
                stream_id,
                f"recover_unknown job={job_id} reason=restart",
            )
        return tuple(str(r[0]) for r in rows)

    def reconcile_attempt(self, job_id: str, disposition: str) -> str:
        """Resolve an unknown job; ``requeue`` is an explicit choice."""
        return self._repo.reconcile_unknown(job_id, disposition)

    def cancel_run(self, stream_id: str, *, generation: int) -> CancelReport:
        """Cancel durably: no new dispatch, unknowns stay reconciling.

        Pending jobs are cancelled outright; a leased job may already
        have run its side effect, so it is marked ``unknown`` rather
        than declared cancelled or completed.
        """
        cancelled: list[str] = []
        unknown: list[str] = []
        with self._repo.transaction() as db:
            _ = self._repo.read_scoped_entity(self._scope, stream_id)
            rows = db.execute(
                "SELECT o.job_id,o.state FROM outbox o JOIN events e "
                "ON e.event_id=o.job_id WHERE o.scope_id=? AND "
                "e.stream_id=? AND o.state IN('pending','leased')",
                (self._scope, stream_id),
            ).fetchall()
            for job_id, state in rows:
                if state == "pending":
                    _ = db.execute(
                        "UPDATE outbox SET state='cancelled' WHERE job_id=?",
                        (job_id,),
                    )
                    cancelled.append(str(job_id))
                else:
                    _ = db.execute(
                        "UPDATE outbox SET state='unknown' WHERE job_id=?",
                        (job_id,),
                    )
                    unknown.append(str(job_id))
            _ = db.execute(
                "INSERT INTO run_cancellations VALUES (?,?,?,?) "
                "ON CONFLICT(stream_id) DO UPDATE SET "
                "state='reconciling',generation=excluded.generation",
                (stream_id, generation, "reconciling", "now"),
            )
            partial = [
                str(r[0])
                for r in db.execute(
                    "SELECT o.job_id FROM outbox o JOIN events e ON "
                    "e.event_id=o.job_id WHERE o.scope_id=? AND "
                    "e.stream_id=? AND o.state='completed'",
                    (self._scope, stream_id),
                )
            ]
        self._repo.audit(
            stream_id,
            f"cancel_run cancelled={len(cancelled)} unknown={len(unknown)}",
        )
        return CancelReport(
            stream_id=stream_id,
            state="reconciling",
            cancelled=tuple(sorted(cancelled)),
            unknown=tuple(sorted(unknown)),
            partial_results=tuple(sorted(partial)),
        )

    def run_state(self, stream_id: str) -> str:
        """Return ``reconciling``/``reconciled`` after a cancel."""
        row = self._repo.connection.execute(
            "SELECT state FROM run_cancellations WHERE stream_id=?",
            (stream_id,),
        ).fetchone()
        return str(row[0]) if row else "active"

    def mark_reconciled(self, stream_id: str) -> None:
        """Close the reconciling state only after unknowns resolve."""
        rows = self._repo.connection.execute(
            "SELECT o.job_id FROM outbox o JOIN events e ON "
            "e.event_id=o.job_id WHERE o.scope_id=? AND "
            "e.stream_id=? AND o.state='unknown'",
            (self._scope, stream_id),
        ).fetchall()
        if rows:
            raise CyranoError(
                "UNKNOWN_OUTCOME",
                f"{len(rows)} jobs still unknown",
            )
        with self._repo.transaction() as db:
            _ = db.execute(
                "UPDATE run_cancellations SET state='reconciled' "
                "WHERE stream_id=?",
                (stream_id,),
            )

    def _require_dispatchable(self, stream_id: str) -> None:
        if self.run_state(stream_id) != "active":
            raise CyranoError(
                "RUN_CANCELLED",
                "stream is reconciling a cancel; no new dispatch",
            )


def job_row(repo: ScopedRepository, job_id: str) -> sqlite3.Row | None:
    """Read one outbox row for diagnostics; never mutates."""
    row: sqlite3.Row | None = repo.connection.execute(
        "SELECT job_id,state,fence FROM outbox WHERE job_id=?",
        (job_id,),
    ).fetchone()
    return row
