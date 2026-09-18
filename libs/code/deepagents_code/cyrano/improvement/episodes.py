"""Episode graphs and failure-trace navigation over the ledger.

An episode is the immutable record of one run: every node carries its
input fingerprint and observed dependencies, and a missing terminal
event means the episode never seals as complete. Trace navigation is
scope-checked — a foreign stream is indistinguishable from absent —
and a deleted payload is reported as unavailable evidence, never
summarized into fact. A run whose last record is a worker heartbeat
has ``root_cause=unknown``; hypotheses stay separated from observed
evidence.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

TERMINAL_KINDS = frozenset(
    {
        "run.finished",
        "run.failed",
        "run.cancelled",
        "attempt.completed",
        "attempt.failed",
    }
)


@dataclass(frozen=True, slots=True)
class EpisodeNode:
    """One recorded step; deps are observed inputs, not claims."""

    node_id: str
    kind: str
    input_digest: str
    parents: tuple[str, ...]
    observed_deps: frozenset[str]


@dataclass(frozen=True, slots=True)
class Episode:
    """An immutable run graph; ``complete`` requires a terminal node."""

    episode_id: str
    nodes: tuple[EpisodeNode, ...]
    input_signature: str
    complete: bool


def build_episode(
    episode_id: str,
    events: Iterable[Mapping[str, object]],
    *,
    input_signature: str = "",
) -> Episode:
    """Freeze recorded events into a dependency DAG.

    A node id may appear once — duplicates make the record ambiguous.
    ``complete`` is true only when a terminal event was recorded.
    """
    nodes: list[EpisodeNode] = []
    seen: set[str] = set()
    terminal = False
    for event in events:
        node_id = str(event.get("node_id") or event.get("event_id") or "")
        if not node_id:
            raise CyranoError("INPUT_INVALID", "event without id")
        if node_id in seen:
            raise CyranoError("DUPLICATE_ACTION", node_id)
        seen.add(node_id)
        kind = str(event.get("kind", "step"))
        if kind in TERMINAL_KINDS:
            terminal = True
        parents_raw = event.get("parents", ())
        deps_raw = event.get("observed_deps", ())
        parents = (
            tuple(str(p) for p in parents_raw)
            if isinstance(parents_raw, (list, tuple))
            else ()
        )
        deps = (
            frozenset(str(d) for d in deps_raw)
            if isinstance(deps_raw, (list, tuple, set, frozenset))
            else frozenset()
        )
        nodes.append(
            EpisodeNode(
                node_id=node_id,
                kind=kind,
                input_digest=str(event.get("input_digest", "")),
                parents=parents,
                observed_deps=deps,
            )
        )
    return Episode(
        episode_id=episode_id,
        nodes=tuple(nodes),
        input_signature=input_signature
        or digest([n.input_digest for n in nodes]),
        complete=terminal,
    )


# -- trace navigation (R3-44) -----------------------------------------


@dataclass(frozen=True, slots=True)
class TraceSpan:
    """One event on a run's timeline; payload absence is explicit."""

    event_id: str
    seq: int
    kind: str
    observed_at: str
    evidence: str
    payload_digest: str


@dataclass(frozen=True, slots=True)
class TracePage:
    """A stable cursor page; ordering is by commit sequence."""

    spans: tuple[TraceSpan, ...]
    next_cursor: int | None
    truncated: bool


@dataclass(frozen=True, slots=True)
class FailureTrace:
    """What the trace proves; hypotheses are not causes."""

    stream_id: str
    root_cause: str
    remediation_owner: str
    observed: tuple[str, ...]
    hypotheses: tuple[str, ...]


_FAILURE_RULES: tuple[tuple[str, str, str], ...] = (
    ("tool.denied", "approval_missing", "requester"),
    ("model.failed", "provider_timeout", "platform"),
    ("tool.failed", "tool_failure", "implementer"),
)


def _cause_for(
    repo: ScopedRepository, scope_id: str, span: TraceSpan
) -> tuple[str, str] | None:
    """Map a span to a cause when its payload proves a failure.

    A ``test.finished`` event only attributes a failure when its
    recorded outcome says ``failed`` — a passing test at the end of a
    lost run is not a cause.
    """
    if span.evidence != "available":
        if span.kind in {k for k, _, _ in _FAILURE_RULES} or (
            span.kind == "test.finished"
        ):
            return ("evidence_unavailable", "platform")
        return None
    if span.kind == "test.finished":
        body = repo.read_artifact(scope_id, span.payload_digest)
        outcome = None
        if body is not None:
            try:
                decoded = json.loads(body)
            except json.JSONDecodeError:
                decoded = None
            if isinstance(decoded, Mapping):
                outcome = decoded.get("outcome")
        if outcome == "failed":
            return ("test_failure", "implementer")
        return None
    for kind, cause, who in _FAILURE_RULES:
        if span.kind == kind:
            return (cause, who)
    return None


def trace_run(
    repo: ScopedRepository,
    scope_id: str,
    stream_id: str,
    *,
    cursor: int = 0,
    limit: int = 50,
) -> TracePage:
    """Page a run's timeline by commit sequence; scope-checked.

    A foreign scope raises ``SCOPE_DENIED`` without revealing whether
    the stream exists. A cursor inside the stream but beyond any
    recorded event returns an empty page rather than replaying rows.
    """
    _ = repo.read_scoped_entity(scope_id, stream_id)
    if cursor < 0 or limit <= 0:
        raise CyranoError("INPUT_INVALID", "bad cursor or limit")
    rows = repo.connection.execute(
        "SELECT e.event_id,e.event_seq,e.kind,e.observed_at,"
        "e.payload_digest FROM events e WHERE e.stream_id=? AND "
        "e.event_seq>? ORDER BY e.event_seq LIMIT ?",
        (stream_id, cursor, limit + 1),
    ).fetchall()
    truncated = len(rows) > limit
    rows = rows[:limit]
    spans: list[TraceSpan] = []
    for event_id, seq, kind, observed_at, payload_digest in rows:
        blob = repo.connection.execute(
            "SELECT raw_digest FROM event_blobs WHERE raw_digest=?",
            (payload_digest,),
        ).fetchone()
        evidence = "available" if blob else "unavailable"
        spans.append(
            TraceSpan(
                str(event_id),
                int(seq),
                str(kind),
                str(observed_at),
                evidence,
                str(payload_digest),
            )
        )
    next_cursor = spans[-1].seq if truncated and spans else None
    return TracePage(tuple(spans), next_cursor, truncated)


def failure_attribution(
    repo: ScopedRepository,
    scope_id: str,
    stream_id: str,
) -> FailureTrace:
    """Attribute a failure from observed events only.

    ``root_cause=unknown`` when no terminal failure event explains the
    stop — a plausible guess is never presented as the cause.
    """
    spans: list[TraceSpan] = []
    cursor = 0
    while True:
        page = trace_run(repo, scope_id, stream_id, cursor=cursor)
        spans.extend(page.spans)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    observed: list[str] = []
    root = "unknown"
    owner = "unassigned"
    hypotheses: list[str] = []
    for span in spans:
        observed.append(f"{span.seq}:{span.kind}")
        cause = _cause_for(repo, scope_id, span)
        if cause is not None:
            root, owner = cause
    if root == "unknown" and spans:
        hypotheses.append(
            "last record is not a failure event; worker may be lost"
        )
    return FailureTrace(
        stream_id=stream_id,
        root_cause=root,
        remediation_owner=owner,
        observed=tuple(observed),
        hypotheses=tuple(hypotheses),
    )
