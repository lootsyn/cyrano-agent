"""Recorded worlds: a sealed transition tape for counterfactual replay.

A world fixes input fingerprints, parent edges, and observed
dependencies at seal time. Results stay private to the tape; the
policy-facing frontier exposes only progress facts. A world whose
episode lacks a terminal event is ``incomplete`` and cannot back a
full replay evaluation — it is an honest gap, not a failed run.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.improvement.episodes import (
    TERMINAL_KINDS,
    Episode,
)


@dataclass(frozen=True, slots=True)
class ExecutionSignature:
    """Inputs that must match before a recorded result may stand in."""

    model_id: str
    endpoint: str
    runtime_digest: str
    tool_inventory_digest: str
    skill_digest: str

    @property
    def signature_digest(self) -> str:
        """Seal the signature fields into one comparable digest."""
        return digest(
            {
                "model": self.model_id,
                "endpoint": self.endpoint,
                "runtime": self.runtime_digest,
                "tools": self.tool_inventory_digest,
                "skill": self.skill_digest,
            }
        )


@dataclass(frozen=True, slots=True)
class TapeTransition:
    """One recorded action→result edge; the score stays hidden."""

    node_id: str
    action_id: str
    input_digest: str
    dependencies: frozenset[str]
    public_result: str
    hidden_score: float | None
    external_ref: str
    is_terminal: bool


@dataclass(frozen=True, slots=True)
class WorldTape:
    """A sealed tape; ``complete`` requires a terminal event."""

    world_id: str
    tape_digest: str
    signature: ExecutionSignature
    transitions: tuple[TapeTransition, ...]
    complete: bool


def build_world(
    episode: Episode,
    signature: ExecutionSignature,
    *,
    world_id: str | None = None,
    scores: Mapping[str, float] | None = None,
    external_refs: Mapping[str, str] | None = None,
) -> WorldTape:
    """Seal an episode into a tape bound to one execution signature.

    ``scores`` are recorded results kept private on the tape — they are
    never projected into a frontier. Order is the recorded order: a
    caller cannot rank samples by score at build time because scores
    are not selection input.
    """
    score_map = scores or {}
    external_refs = external_refs or {}
    transitions = tuple(
        TapeTransition(
            node_id=node.node_id,
            action_id=node.node_id,
            input_digest=node.input_digest,
            dependencies=node.observed_deps,
            public_result=f"{node.kind}:recorded",
            hidden_score=score_map.get(node.node_id),
            external_ref=external_refs.get(node.node_id, ""),
            is_terminal=node.kind in TERMINAL_KINDS,
        )
        for node in episode.nodes
    )
    tape_digest = digest(
        [
            [t.node_id, t.input_digest, sorted(t.dependencies)]
            for t in transitions
        ]
        + [signature.signature_digest]
    )
    return WorldTape(
        world_id=world_id or f"world:{episode.episode_id}",
        tape_digest=tape_digest,
        signature=signature,
        transitions=transitions,
        complete=episode.complete,
    )


def public_observation(
    world: WorldTape,
    *,
    attempts_used: int,
    error_kinds: Iterable[str],
    budget_remaining: int,
    legal_actions: Iterable[str],
) -> Mapping[str, object]:
    """Project the redacted frontier a policy may decide on.

    The view carries progress facts only: attempt count, observed error
    kinds, remaining budget, and the legal action list. Hidden scores,
    the best branch, result-revealing ids, and the tape itself never
    appear — the slot commitment precedes any result.
    """
    return {
        "world_id": world.world_id,
        "attempts_used": attempts_used,
        "error_kinds": sorted(set(error_kinds)),
        "budget_remaining": budget_remaining,
        "legal_actions": sorted(set(legal_actions)),
        "complete": world.complete,
    }
