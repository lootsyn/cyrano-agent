"""Learning-plan compilation: a restricted IR with static validation.

A learning plan may observe, analyze, propose, evaluate, and report —
never apply, publish, or mutate source. Static validation checks step
types, reference resolution, nesting depth, and operation membership;
dependency cycles are refused. Every plan carries budget, deadline,
and resource bounds, starts in ``pending_review``, and a reviewer's
approval moves it to ``reviewed`` — the author may not self-approve.
Stopping a plan halts exploration only; it grants no write or
completion authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError

LEARNING_OPS = frozenset(
    {"observe", "analyze", "propose", "evaluate", "report"}
)
MAX_PLAN_DEPTH = 3

_FORBIDDEN_FLAGS = frozenset(
    {
        "skip_verification",
        "skip_review",
        "skip_approval",
        "auto_apply",
        "bypass_gate",
    }
)


@dataclass(frozen=True, slots=True)
class PlanStep:
    """One typed step; refs and deps must resolve inside the plan."""

    step_id: str
    operation: str
    inputs: tuple[str, ...]
    deps: tuple[str, ...]
    depth: int


@dataclass(frozen=True, slots=True)
class LearningPlan:
    """A compiled plan; ``state`` is pending_review until approved."""

    plan_id: str
    author: str
    steps: tuple[PlanStep, ...]
    budget: int
    deadline: int
    resource_caps: Mapping[str, int]
    state: str


def _step(spec: object) -> PlanStep:
    if not isinstance(spec, Mapping):
        raise CyranoError("PLAN_SHAPE", "step must be a mapping")
    step_id = spec.get("id")
    operation = spec.get("op")
    if not isinstance(step_id, str) or not step_id:
        raise CyranoError("PLAN_SHAPE", "step id required")
    if not isinstance(operation, str) or operation not in LEARNING_OPS:
        raise CyranoError(
            "OPERATION_NOT_ALLOWED", f"{operation!r} not in learning ops"
        )
    inputs_raw = spec.get("inputs", ())
    deps_raw = spec.get("deps", ())
    flags = spec.get("flags", ())
    if isinstance(flags, (list, tuple)) and (
        set(map(str, flags)) & _FORBIDDEN_FLAGS
    ):
        raise CyranoError(
            "GEN01_VIOLATION", "plan step would skip a mandatory gate"
        )
    inputs = (
        tuple(str(i) for i in inputs_raw)
        if isinstance(inputs_raw, (list, tuple))
        else ()
    )
    deps = (
        tuple(str(d) for d in deps_raw)
        if isinstance(deps_raw, (list, tuple))
        else ()
    )
    depth = spec.get("depth", 0)
    if not isinstance(depth, int) or depth < 0 or depth > MAX_PLAN_DEPTH:
        raise CyranoError("PLAN_DEPTH_EXCEEDED", str(depth))
    return PlanStep(step_id, operation, inputs, deps, depth)


def compile_learning_plan(
    spec: Mapping[str, object],
    *,
    author: str,
    learning_enabled: bool = False,
) -> LearningPlan:
    """Statically validate and compile a learning plan.

    Refuses unknown operations, unresolvable refs, dependency cycles,
    depth beyond the cap, missing budget/deadline bounds, and any step
    that would skip a mandatory gate.
    """
    if not learning_enabled:
        raise CyranoError("LEARNING_DISABLED", "explicit enable required")
    raw_steps = spec.get("steps")
    if not isinstance(raw_steps, (list, tuple)) or not raw_steps:
        raise CyranoError("PLAN_SHAPE", "a plan needs at least one step")
    budget = spec.get("budget")
    deadline = spec.get("deadline")
    if (
        not isinstance(budget, int)
        or budget <= 0
        or not isinstance(deadline, int)
        or deadline <= 0
    ):
        raise CyranoError(
            "RESOURCE_LIMIT_REQUIRED", "budget and deadline are required"
        )
    caps = spec.get("resource_caps", {})
    resource_caps: dict[str, int] = {}
    if isinstance(caps, Mapping):
        for key, value in caps.items():
            if not isinstance(value, int):
                raise CyranoError(
                    "PLAN_SHAPE", "resource cap values must be ints"
                )
            resource_caps[str(key)] = value
    steps = tuple(_step(s) for s in raw_steps)
    ids = {s.step_id for s in steps}
    if len(ids) != len(steps):
        raise CyranoError("PLAN_SHAPE", "duplicate step id")
    refs_raw = spec.get("refs", ())
    refs = (
        {str(r) for r in refs_raw}
        if isinstance(refs_raw, (list, tuple, set, frozenset))
        else set()
    )
    known = ids | refs
    for step in steps:
        unresolved = set(step.inputs) - known
        if unresolved:
            raise CyranoError("PLAN_REF_UNRESOLVED", sorted(unresolved)[0])
        if set(step.deps) - ids:
            raise CyranoError("PLAN_REF_UNRESOLVED", "dep not in plan")
    _check_acyclic(steps)
    return LearningPlan(
        plan_id=digest([[s.step_id, s.operation] for s in steps] + [author]),
        author=author,
        steps=steps,
        budget=budget,
        deadline=deadline,
        resource_caps=resource_caps,
        state="pending_review",
    )


def _check_acyclic(steps: tuple[PlanStep, ...]) -> None:
    deps = {s.step_id: s.deps for s in steps}
    visiting: set[str] = set()
    done: set[str] = set()

    def visit(node: str) -> None:
        if node in done:
            return
        if node in visiting:
            raise CyranoError("PLAN_CYCLE", node)
        visiting.add(node)
        for dep in deps.get(node, ()):
            visit(dep)
        visiting.discard(node)
        done.add(node)

    for step_id in deps:
        visit(step_id)


def approve_plan(plan: LearningPlan, *, reviewer: str) -> LearningPlan:
    """Move a plan to reviewed; the author may not self-approve."""
    if reviewer == plan.author:
        raise CyranoError(
            "REVIEW_INDEPENDENCE", "author cannot review own plan"
        )
    return LearningPlan(
        plan_id=plan.plan_id,
        author=plan.author,
        steps=plan.steps,
        budget=plan.budget,
        deadline=plan.deadline,
        resource_caps=plan.resource_caps,
        state="reviewed",
    )


def run_step(step: PlanStep, *, permission: str | None = None) -> str:
    """Execute a step in isolation; permissions are never ambient."""
    if permission is not None:
        raise CyranoError(
            "PERMISSION_DENIED", "isolated steps hold no permissions"
        )
    return f"{step.operation}:done"


def request_stop(plan: LearningPlan) -> Mapping[str, object]:
    """Stop exploration only; no write or completion authority."""
    return {
        "plan_id": plan.plan_id,
        "exploration_stopped": True,
        "source_write_allowed": False,
        "completion_allowed": False,
    }
