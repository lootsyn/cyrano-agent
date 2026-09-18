"""Session state machine bound to the v2 contract catalog.

The 29-state catalog, explicit transitions, and global transitions are
loaded from the contract document, never re-authored here. Candidate
lookup is deterministic: an explicit transition wins, then a unique
global event match, otherwise INVALID_TRANSITION. Resume targets come
only from the persisted checkpoint; a caller-supplied target and a
terminal checkpoint are both refused.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from deepagents_code.cyrano.contracts.types import CyranoError

TERMINAL_STATES = frozenset({"COMPLETED", "CANCELLED", "FAILED"})

CANDIDATE_STATES = frozenset(
    {
        "proposed",
        "static_validated",
        "evaluating",
        "inconclusive",
        "evaluated",
        "reviewed",
        "promoted",
        "rejected",
        "revoked",
    }
)


@dataclass(frozen=True, slots=True)
class Transition:
    """One contract transition row."""

    from_state: str
    event: str
    to_state: str
    guard_id: str


@dataclass(frozen=True, slots=True)
class Session:
    """Work-machine state plus the separate candidate domain.

    The candidate promotion state is a different domain: completing or
    cancelling work never mutates it, and candidate changes never move
    the work machine.
    """

    work_state: str
    candidate_state: str = "proposed"
    checkpoint: str | None = None


class SessionMachine:
    """Deterministic catalog lookup; guards are evaluated elsewhere."""

    def __init__(
        self,
        states: frozenset[str],
        transitions: tuple[Transition, ...],
        global_transitions: tuple[Transition, ...],
    ) -> None:
        """Store the catalog; duplicate (state, event) is illegal."""
        self._states: frozenset[str] = states
        self._transitions: tuple[Transition, ...] = transitions
        self._global: tuple[Transition, ...] = global_transitions
        self._explicit: dict[tuple[str, str], Transition] = {}
        for t in transitions:
            key = (t.from_state, t.event)
            if key in self._explicit:
                raise CyranoError("INVALID_CONTRACT", f"dup {key}")
            self._explicit[key] = t

    @classmethod
    def from_contract(cls, doc: Mapping[str, object]) -> "SessionMachine":
        """Build from the parsed session-state-machine contract."""
        states = frozenset(cast(list[str], doc["states"]))

        def rows(key: str) -> tuple[Transition, ...]:
            out: list[Transition] = []
            for raw in cast(list[Mapping[str, object]], doc[key]):
                guard = cast(str, raw["guard_id"])
                to = cast(str, raw["to"])
                event = cast(str, raw["event"])
                sources = raw.get("from_set")
                if isinstance(sources, list):
                    for src in cast(list[str], sources):
                        out.append(Transition(src, event, to, guard))
                else:
                    out.append(
                        Transition(cast(str, raw["from"]), event, to, guard)
                    )
            return tuple(out)

        return cls(states, rows("transitions"), rows("global_transitions"))

    def candidate(self, state: str, event: str) -> Transition:
        """Resolve (state, event); unknown input is refused."""
        if state not in self._states:
            raise CyranoError("INVALID_TRANSITION", state)
        explicit = self._explicit.get((state, event))
        if explicit is not None:
            return explicit
        matches = [
            t
            for t in self._global
            if t.from_state == state and t.event == event
        ]
        if len(matches) == 1:
            return matches[0]
        raise CyranoError("INVALID_TRANSITION", f"{state}:{event}")

    def is_terminal(self, state: str) -> bool:
        """Terminal states never resume and never transition."""
        return state in TERMINAL_STATES

    def resume_target(self, checkpoint: str) -> str:
        """Resume goes to the persisted checkpoint, never a request."""
        if checkpoint in TERMINAL_STATES:
            raise CyranoError("TERMINAL_RESUME", checkpoint)
        if checkpoint not in self._states:
            raise CyranoError("INVALID_TRANSITION", checkpoint)
        return checkpoint
