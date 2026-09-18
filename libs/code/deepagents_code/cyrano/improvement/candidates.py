"""Candidate changes: immutable diffs, delta validation, review queue.

A candidate is a frozen artifact bound to a base revision and digest —
proposing one changes nothing active. ``validate_delta`` checks the
expected revision, scope containment, grounds, protected fields, and
size before a candidate exists. ``enqueue_review`` writes the terminal
event and the outbox job in one transaction keyed by the candidate id,
so a repeated call coalesces to the same logical job. ``run_review``
executes foreground-first inside the job's fence; failures dead-letter
durably, and a reviewer who authored the candidate is refused.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

MAX_DELTA_BYTES = 256 * 1024
MAX_META_DEPTH = 0


@dataclass(frozen=True, slots=True)
class Candidate:
    """An immutable proposed delta; proposing changes nothing active."""

    candidate_id: str
    base_revision: int
    diff_digest: str
    scope: str
    author: str
    grounds: str
    paths: tuple[str, ...]
    claims: Mapping[str, str] = field(default_factory=dict)
    state: str = "candidate"


def propose_candidate(
    *,
    base_revision: int,
    diff: str,
    scope: str,
    author: str,
    grounds: str,
    paths: Iterable[str] = (),
    claims: Mapping[str, str] | None = None,
) -> Candidate:
    """Freeze a proposed diff into a digest-bound candidate."""
    if not grounds:
        raise CyranoError("INPUT_INVALID", "grounds required")
    if not diff:
        raise CyranoError("EMPTY_CANDIDATE", "a candidate needs a diff")
    candidate_id = digest([diff, scope, author, str(base_revision)])
    return Candidate(
        candidate_id=candidate_id,
        base_revision=base_revision,
        diff_digest=digest(diff),
        scope=scope,
        author=author,
        grounds=grounds,
        paths=tuple(str(p) for p in paths),
        claims=dict(claims) if claims else {},
    )


def validate_delta(
    base: Mapping[str, object],
    delta: Mapping[str, object],
    *,
    author: str,
) -> Candidate:
    """Validate a delta against its base and return a candidate.

    Checks expected revision, scope containment, required grounds,
    protected fields, and the size cap — a failure anywhere means no
    candidate exists.
    """
    expected = delta.get("expected_revision")
    base_rev = base.get("revision")
    if (
        not isinstance(expected, int)
        or not isinstance(base_rev, int)
        or expected != base_rev
    ):
        raise CyranoError(
            "STALE_REVISION", f"expected {base_rev}, got {expected}"
        )
    base_scope = str(base.get("scope", ""))
    delta_scope = str(delta.get("scope", ""))
    if not delta_scope or not base_scope.startswith(delta_scope):
        if not (delta_scope.startswith(base_scope) or base_scope == ""):
            raise CyranoError("SCOPE_DENIED", "delta outside base scope")
    protected = base.get("protected_fields", ())
    fields_raw = delta.get("fields", ())
    fields = (
        {str(f) for f in fields_raw}
        if isinstance(fields_raw, (list, tuple, frozenset))
        else set()
    )
    if isinstance(protected, (list, tuple, frozenset)):
        touched = fields & {str(p) for p in protected}
        if touched:
            first = sorted(map(str, touched))[0]
            code = (
                "EVAL_CRITERIA_TAMPER"
                if "eval_criteria" in touched
                else "PROTECTED_FIELD"
            )
            raise CyranoError(code, first)
    diff = str(delta.get("diff", ""))
    if len(diff.encode()) > MAX_DELTA_BYTES:
        raise CyranoError("DELTA_TOO_LARGE", str(len(diff.encode())))
    grounds = str(delta.get("grounds", ""))
    paths_raw = delta.get("paths", ())
    paths = (
        [str(p) for p in paths_raw]
        if isinstance(paths_raw, (list, tuple))
        else []
    )
    return propose_candidate(
        base_revision=base_rev,
        diff=diff,
        scope=delta_scope,
        author=author,
        grounds=grounds,
        paths=paths,
    )


def enqueue_review(
    repo: ScopedRepository,
    scope_id: str,
    stream_id: str,
    candidate: Candidate,
    *,
    meta_depth: int = 0,
) -> str:
    """Atomically record the review request and enqueue one job.

    The idempotency key is bound to the candidate id, so re-submitting
    the same candidate returns the existing job — duplicates coalesce
    instead of double-billing. ``meta_depth`` above zero refuses the
    learning-of-learning enqueue entirely.
    """
    if meta_depth > MAX_META_DEPTH:
        raise CyranoError(
            "META_DEPTH_EXCEEDED", "learning recursion is not permitted"
        )
    revision = repo.read_scoped_entity(scope_id, stream_id)
    key = f"review:{candidate.candidate_id}"
    payload = {
        "candidate_id": candidate.candidate_id,
        "kind": "candidate_review",
    }
    job_id = digest({"stream": stream_id, "payload": payload, "key": key})
    try:
        _ = repo.execute_command(
            scope_id,
            "learning",
            "enqueue_review",
            key,
            payload,
            stream_id,
            expected_revision=revision,
            enqueue=True,
            producer="learning",
            producer_seq=None,
        )
    except CyranoError as exc:
        # The same logical request under a moved revision conflicts —
        # the key is bound to the candidate id, so the coalesced job
        # already exists and no second side effect was written. A
        # STALE_REVISION without a prior request means no job exists,
        # so it must propagate rather than report a phantom enqueue.
        if exc.code != "IDEMPOTENCY_CONFLICT":
            raise
    return job_id


@dataclass(frozen=True, slots=True)
class ReviewOutcome:
    """A review attempt's terminal disposition."""

    job_id: str
    verdict: str
    reviewer: str
    dead_lettered: bool


def run_review(
    repo: ScopedRepository,
    scope_id: str,
    job_id: str,
    candidate: Candidate,
    *,
    reviewer: str,
    budget: int,
    work: Callable[[], str] | None = None,
) -> ReviewOutcome:
    """Run a review foreground-first inside the job's fence.

    The reviewer must differ from the candidate author. A review that
    fails inside ``work`` is dead-lettered via the fenced fail path;
    a result submitted under a lost fence is never applied, and the
    attempt is never silently retried.
    """
    if reviewer == candidate.author:
        raise CyranoError(
            "REVIEW_INDEPENDENCE", "author cannot review own candidate"
        )
    if budget <= 0:
        raise CyranoError("RESOURCE_LIMIT_REQUIRED", "budget required")
    lease = repo.claim_job(scope_id, job_id, "reviewer", 0, 60)
    if lease is None:
        raise CyranoError("JOB_NOT_PENDING", job_id)
    try:
        verdict = work() if work is not None else "approved"
    except Exception:
        _ = repo.fail_job(job_id, "reviewer", lease.fence, 0)
        return ReviewOutcome(job_id, "dead_letter", reviewer, True)
    if repo.submit_result(job_id, "reviewer", lease.fence, 0) != "applied":
        return ReviewOutcome(job_id, "dead_letter", reviewer, True)
    return ReviewOutcome(job_id, verdict, reviewer, False)
