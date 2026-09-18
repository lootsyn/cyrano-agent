"""Replay kernels: an atomic transition replay and a world-level runner.

The world runner binds a sealed ``WorldTape`` to an execution
signature. Results cross the barrier only when every step in a batch
is supported — a partially supported batch reveals nothing. Timeout is
an explicit step state, an incomplete world cannot be scored, and a
policy never sees hidden results at any point.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.improvement.worlds import (
    ExecutionSignature,
    WorldTape,
)


@dataclass(frozen=True, slots=True)
class RecordedTransition:
    """Private result, never included in a policy's initial view."""

    action_id: str
    input_digest: str
    dependencies: frozenset[str]
    public_result: str


class Replay:
    """Reveal only input-matching, dependency-supported batches."""

    def __init__(self, transitions: list[RecordedTransition]) -> None:
        """Index the tape; ambiguous duplicates are refused."""
        self._transitions: dict[str, RecordedTransition] = {
            item.action_id: item for item in transitions
        }
        if len(self._transitions) != len(transitions):
            raise CyranoError("DUPLICATE_ACTION", "ambiguous sample tape")
        self._visible: dict[str, str] = {}

    def view(self) -> dict[str, str]:
        """Copy observed results only; the result store stays hidden."""
        return dict(self._visible)

    def step(
        self,
        actions: dict[str, str],
        legal_ids: frozenset[str],
        *,
        worker_cap: int,
    ) -> str:
        """Return out_of_support without a partial reveal."""
        if not actions or len(actions) > worker_cap:
            raise CyranoError(
                "INVALID_BATCH", "nonempty batch must fit worker capacity"
            )
        prepared: list[RecordedTransition] = []
        for action, input_digest in actions.items():
            if action not in legal_ids or action in self._visible:
                raise CyranoError("ILLEGAL_ACTION", action)
            transition = self._transitions.get(action)
            if transition is None or transition.input_digest != input_digest:
                return "out_of_support"
            if not transition.dependencies.issubset(self._visible):
                return "out_of_support"
            prepared.append(transition)
        self._visible.update(
            {item.action_id: item.public_result for item in prepared}
        )
        return "supported"


# -- world-level replay ------------------------------------------------

SUPPORTED = "supported"
OUT_OF_SUPPORT = "out_of_support"
INPUT_MISMATCH = "input_mismatch"
SIGNATURE_MISMATCH = "signature_mismatch"
DEPENDENCY_NOT_OBSERVED = "dependency_not_observed"
INCOMPLETE = "incomplete"
TIMEOUT = "timeout"
PENDING = "pending"


@dataclass(frozen=True, slots=True)
class StepState:
    """One batch step; ``result`` is populated only past the barrier."""

    action_id: str
    status: str
    result: str | None


@dataclass(frozen=True, slots=True)
class BatchOutcome:
    """A settled batch; results never leak on partial support."""

    status: str
    steps: tuple[StepState, ...]
    data_collection_required: bool
    recorded_signature: str


def _signature_status(
    recorded: ExecutionSignature, current: ExecutionSignature
) -> str | None:
    """Classify signature drift.

    Model/endpoint/runtime/tool drift is a signature mismatch; a
    skill-only drift is an input mismatch needing a real re-run.
    """
    if (
        recorded.model_id,
        recorded.endpoint,
        recorded.runtime_digest,
        recorded.tool_inventory_digest,
    ) != (
        current.model_id,
        current.endpoint,
        current.runtime_digest,
        current.tool_inventory_digest,
    ):
        return SIGNATURE_MISMATCH
    if recorded.skill_digest != current.skill_digest:
        return INPUT_MISMATCH
    return None


class WorldReplay:
    """Replay one sealed world for one policy, starting from the root.

    Each instance owns an empty frontier, so two policies over the same
    world cannot contaminate each other's prefixes. Transitions match
    on ``(action_id, input_digest)`` only — external ids are never part
    of the key, and ids may break ties but never decide.
    """

    def __init__(
        self,
        world: WorldTape,
        signature: ExecutionSignature,
        *,
        legal_actions: frozenset[str],
        worker_cap: int = 4,
    ) -> None:
        """Bind a world to a signature; the frontier starts empty."""
        self._world: WorldTape = world
        self._signature: ExecutionSignature = signature
        self._legal: frozenset[str] = legal_actions
        self._cap: int = worker_cap
        self._visible: dict[str, str] = {}
        self._open: dict[str, StepState] | None = None
        self._committed: frozenset[str] = frozenset()

    def commit_slots(self, action_ids: list[str]) -> tuple[str, ...]:
        """Bind opaque slots before any result exists.

        The commitment precedes results, so no slot can be labelled by
        the outcome it later receives.
        """
        if self._open is not None:
            raise CyranoError("BATCH_INCOMPLETE", "slots bind between batches")
        self._committed = self._committed | frozenset(action_ids)
        return tuple(f"slot:{a}" for a in action_ids)

    def open_batch(self, actions: Mapping[str, str]) -> BatchOutcome:
        """Open a barrier batch; step status is set, results are not."""
        if self._open is not None:
            raise CyranoError(
                "BATCH_INCOMPLETE", "settle the open batch first"
            )
        if not actions or len(actions) > self._cap:
            raise CyranoError(
                "INVALID_BATCH", "nonempty batch must fit capacity"
            )
        uncommitted = set(actions) - self._committed
        if uncommitted:
            raise CyranoError("SLOTS_NOT_COMMITTED", sorted(uncommitted)[0])
        sig_status = (
            _signature_status(self._world.signature, self._signature)
            if self._world.complete
            else None
        )
        steps: list[StepState]
        if not self._world.complete:
            steps = [StepState(a, INCOMPLETE, None) for a in actions]
        elif sig_status is not None:
            steps = [StepState(a, sig_status, None) for a in actions]
        else:
            steps = []
            by_key = {
                (t.action_id, t.input_digest): t
                for t in self._world.transitions
            }
            for action, input_digest in actions.items():
                if action not in self._legal or action in self._visible:
                    raise CyranoError("ILLEGAL_ACTION", action)
                transition = by_key.get((action, input_digest))
                if transition is None:
                    known = any(
                        t.action_id == action for t in self._world.transitions
                    )
                    status = INPUT_MISMATCH if known else OUT_OF_SUPPORT
                    steps.append(StepState(action, status, None))
                elif not transition.dependencies.issubset(self._visible):
                    steps.append(
                        StepState(action, DEPENDENCY_NOT_OBSERVED, None)
                    )
                else:
                    steps.append(StepState(action, PENDING, None))
        self._open = {s.action_id: s for s in steps}
        return self._outcome()

    def settle_step(self, action_id: str, *, timed_out: bool = False) -> None:
        """Resolve a pending step; timeout is an explicit state.

        A non-timeout settle means the recorded result is ready for
        barrier release; the result itself stays hidden until
        ``close_batch``.
        """
        if self._open is None or action_id not in self._open:
            raise CyranoError("INPUT_INVALID", action_id)
        step = self._open[action_id]
        if step.status != PENDING:
            raise CyranoError("INPUT_INVALID", "step already terminal")
        status = TIMEOUT if timed_out else SUPPORTED
        self._open[action_id] = StepState(action_id, status, None)

    def close_batch(self) -> BatchOutcome:
        """Cross the barrier; results appear only if all supported."""
        if self._open is None:
            raise CyranoError("INPUT_INVALID", "no open batch")
        steps = tuple(self._open.values())
        if any(s.status == PENDING for s in steps):
            raise CyranoError("BATCH_INCOMPLETE", "unsettled steps remain")
        if all(s.status == SUPPORTED for s in steps):
            by_action = {t.action_id: t for t in self._world.transitions}
            revealed = tuple(
                StepState(
                    s.action_id,
                    SUPPORTED,
                    by_action[s.action_id].public_result,
                )
                for s in steps
            )
            for step in revealed:
                if step.result is not None:
                    self._visible[step.action_id] = step.result
            outcome = BatchOutcome(
                SUPPORTED,
                revealed,
                False,
                self._world.signature.signature_digest,
            )
        else:
            status = next(s.status for s in steps if s.status != SUPPORTED)
            outcome = BatchOutcome(
                status,
                steps,
                any(s.status == OUT_OF_SUPPORT for s in steps),
                self._world.signature.signature_digest,
            )
        self._open = None
        return outcome

    def select_next(self) -> Mapping[str, str]:
        """Next decision input; blocked until the batch settles."""
        if self._open is not None:
            pending = any(s.status == PENDING for s in self._open.values())
            if pending:
                raise CyranoError("BATCH_INCOMPLETE", "barrier not reached")
            raise CyranoError("BATCH_INCOMPLETE", "close the batch first")
        return dict(self._visible)

    def _outcome(self) -> BatchOutcome:
        steps = tuple(self._open.values()) if self._open else ()
        if not steps:
            status = SUPPORTED
        elif all(s.status == PENDING for s in steps):
            status = PENDING
        elif all(s.status == SUPPORTED for s in steps):
            status = SUPPORTED
        else:
            status = next(
                s.status for s in steps if s.status not in (PENDING, SUPPORTED)
            )
        return BatchOutcome(
            status=status,
            steps=steps,
            data_collection_required=any(
                s.status == OUT_OF_SUPPORT for s in steps
            ),
            recorded_signature=self._world.signature.signature_digest,
        )

    def world_score(self) -> float | None:
        """Score only a fully supported, complete replay.

        An unsettled or unsupported step, an incomplete tape, or a
        signature/input mismatch yields ``None`` — the score is never
        interpolated and a recorded result is never re-labelled as a
        new model's output.
        """
        if not self._world.complete:
            return None
        planned = {
            t.action_id for t in self._world.transitions if not t.is_terminal
        }
        if not planned.issubset(self._visible):
            return None
        scores = [
            t.hidden_score
            for t in self._world.transitions
            if not t.is_terminal and t.hidden_score is not None
        ]
        if not scores:
            return None
        return sum(scores) / len(scores)


def compare_report(
    world_results: Mapping[str, str],
) -> Mapping[str, object]:
    """Report support over the full planned denominator.

    Every planned world stays in the report; an unsupported or
    incomplete world is counted as such, never dropped to flatter a
    candidate and never scored by interpolation.
    """
    supported = sum(1 for s in world_results.values() if s == SUPPORTED)
    return {
        "planned": len(world_results),
        "supported": supported,
        "statuses": dict(world_results),
    }


def settle_stop(
    *,
    acceptance_granted: bool,
    review_granted: bool,
    reason: str,
) -> Mapping[str, object]:
    """Record ``stop_exploration``; it never substitutes for task gates.

    Stopping exploration ends candidate search only — final acceptance,
    independent review, and apply approval remain separate requirements.
    """
    if not (acceptance_granted and review_granted):
        raise CyranoError(
            "COMPLETION_GATES_REQUIRED",
            "stop_exploration does not skip acceptance or review",
        )
    return {"stopped": True, "reason": reason, "task_complete": False}
