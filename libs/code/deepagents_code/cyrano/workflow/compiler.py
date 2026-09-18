"""Compile a plan into the restricted WorkflowIR.

Allowed node kinds are ``read``, ``agent_task``, ``verify``,
``human_decision``, ``join``, and ``apply_candidate``. Conditions are a
typed AST — literals, field access on settled ancestor results, and
``eq/ne/and/or/not`` — never eval'd code. Compile validates structure
and produces a digest; it never grants approval or execution rights.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.planning.subject import WorkUnitSpec

NODE_KINDS = frozenset(
    {
        "read",
        "agent_task",
        "verify",
        "human_decision",
        "join",
        "apply_candidate",
    }
)
CONDITION_OPS = frozenset({"eq", "ne", "and", "or", "not"})
MAX_DEPTH = 32
MAX_NODES = 256


@dataclass(frozen=True, slots=True)
class WorkflowNode:
    """One IR node; human_decision requests but never grants."""

    node_id: str
    kind: str
    dependencies: tuple[str, ...] = ()
    requirement_ids: tuple[str, ...] = ()
    acceptance_ids: tuple[str, ...] = ()
    condition: Mapping[str, Any] | None = None
    scope_ref: str | None = None
    resource_claims: tuple[str, ...] = ()
    retry_class: str = "none"
    max_attempts: int = 1
    cost_cap: int | None = None
    recipe_id: str | None = None
    compensation_ref: str | None = None


@dataclass(frozen=True, slots=True)
class CompiledWorkflow:
    """Validated IR plus its digest; ordering is topological."""

    workflow_digest: str
    revision: int
    nodes: tuple[WorkflowNode, ...]
    order: tuple[str, ...]
    budget_total: int


def _validate_condition(
    node: WorkflowNode,
    settled: set[str],
) -> None:
    """A condition may only read settled ancestors via typed ops."""

    def walk(expr: Any, *, top: bool = False) -> None:
        if isinstance(expr, (str, int, float, bool)) or expr is None:
            if top:
                raise CyranoError(
                    "INPUT_INVALID",
                    "a condition is a typed AST node, not a scalar",
                )
            return
        if not isinstance(expr, Mapping):
            raise CyranoError("INPUT_INVALID", "condition not an AST")
        op = expr.get("op")
        if op == "field":
            ref = expr.get("node")
            field_name = expr.get("name")
            if (
                not isinstance(ref, str)
                or ref not in settled
                or not isinstance(field_name, str)
            ):
                raise CyranoError(
                    "INPUT_INVALID",
                    f"field ref must name a settled ancestor: {expr!r}",
                )
            return
        if op == "literal":
            if not isinstance(
                expr.get("value"), (str, int, float, bool, type(None))
            ):
                raise CyranoError("INPUT_INVALID", "literal must be a scalar")
            return
        if op in CONDITION_OPS:
            args = expr.get("args")
            if not isinstance(args, list) or not args:
                raise CyranoError("INPUT_INVALID", f"{op} needs args")
            if op == "not" and len(args) != 1:
                raise CyranoError("INPUT_INVALID", "not takes one arg")
            if op in {"eq", "ne"} and len(args) != 2:
                raise CyranoError("INPUT_INVALID", f"{op} takes two args")
            for arg in args:
                walk(arg)
            return
        raise CyranoError(
            "INPUT_INVALID", f"condition op {op!r} is not allowed"
        )

    walk(node.condition, top=True)


def compile_workflow(
    nodes: tuple[WorkflowNode, ...],
    *,
    revision: int = 0,
    known_recipes: frozenset[str] | None = None,
    known_requirements: frozenset[str] | None = None,
) -> CompiledWorkflow:
    """Validate the IR and return its digest + topological order."""
    if len(nodes) > MAX_NODES:
        raise CyranoError("INPUT_INVALID", "too many nodes")
    by_id: dict[str, WorkflowNode] = {}
    for node in nodes:
        if node.node_id in by_id:
            raise CyranoError(
                "INPUT_INVALID", f"duplicate node {node.node_id!r}"
            )
        if node.kind not in NODE_KINDS:
            raise CyranoError(
                "INPUT_INVALID", f"unknown node kind {node.kind!r}"
            )
        if node.max_attempts < 1:
            raise CyranoError(
                "INPUT_INVALID", f"{node.node_id} max_attempts < 1"
            )
        if node.kind in {"agent_task", "verify", "apply_candidate"}:
            if node.cost_cap is None:
                raise CyranoError(
                    "BUDGET_UNBOUND", f"{node.node_id} has no cost cap"
                )
        if known_requirements is not None:
            unbound = set(node.requirement_ids) - known_requirements
            if unbound:
                raise CyranoError(
                    "UNBOUND_REQUIREMENT",
                    f"{node.node_id} binds unknown {sorted(unbound)}",
                )
        by_id[node.node_id] = node
    settled: set[str] = set()
    order: list[str] = []
    depth = 0
    while len(order) < len(nodes):
        ready = sorted(
            nid
            for nid, node in by_id.items()
            if nid not in settled and set(node.dependencies) <= settled
        )
        if not ready:
            remaining = set(by_id) - settled
            raise CyranoError(
                "DAG_CYCLE",
                f"unresolvable dependencies: {sorted(remaining)}",
            )
        depth += 1
        if depth > MAX_DEPTH:
            raise CyranoError("DAG_CYCLE", "dependency depth exceeded")
        for nid in ready:
            node = by_id[nid]
            missing = set(node.dependencies) - set(by_id)
            if missing or nid in node.dependencies:
                raise CyranoError(
                    "DAG_CYCLE",
                    f"{nid} depends on {sorted(missing) or 'itself'}",
                )
            if node.condition is not None:
                _validate_condition(node, settled)
            if (
                node.recipe_id is not None
                and known_recipes is not None
                and node.recipe_id not in known_recipes
            ):
                raise CyranoError(
                    "CAPABILITY_UNAVAILABLE",
                    f"unregistered recipe {node.recipe_id!r}",
                )
            settled.add(nid)
            order.append(nid)
    projection = [
        {
            "id": n.node_id,
            "kind": n.kind,
            "deps": sorted(n.dependencies),
            "req": sorted(n.requirement_ids),
            "acc": sorted(n.acceptance_ids),
            "cond": n.condition,
            "scope": n.scope_ref,
            "res": sorted(n.resource_claims),
            "cap": n.cost_cap,
            "recipe": n.recipe_id,
        }
        for n in sorted(nodes, key=lambda n: n.node_id)
    ]
    return CompiledWorkflow(
        workflow_digest=digest({"revision": revision, "nodes": projection}),
        revision=revision,
        nodes=nodes,
        order=tuple(order),
        budget_total=sum(n.cost_cap or 0 for n in nodes),
    )


def propose_expansion(
    base: CompiledWorkflow,
    additions: tuple[WorkflowNode, ...],
    *,
    policy_max_nodes: int,
    policy_max_cost: int,
) -> CompiledWorkflow:
    """Propose new nodes as a new revision; never overwrite the base.

    Widening scope, budget, or verification surfaces in the proposal
    still needs fresh review — the compiler only stamps a new digest.
    """
    merged = {n.node_id: n for n in base.nodes}
    for node in additions:
        if node.node_id in merged:
            raise CyranoError(
                "IDEMPOTENCY_CONFLICT",
                f"expansion may not redefine {node.node_id!r}",
            )
        merged[node.node_id] = node
    if len(merged) > policy_max_nodes:
        raise CyranoError("INPUT_INVALID", "expansion exceeds node cap")
    total = sum(n.cost_cap or 0 for n in merged.values())
    if total > policy_max_cost:
        raise CyranoError(
            "BUDGET_UNBOUND", "expansion exceeds the cost policy"
        )
    return compile_workflow(tuple(merged.values()), revision=base.revision + 1)


def units_to_nodes(
    units: tuple[WorkUnitSpec, ...],
) -> tuple[WorkflowNode, ...]:
    """Normalize WorkUnitSpecs into agent_task IR nodes."""
    return tuple(
        WorkflowNode(
            node_id=u.unit_id,
            kind="agent_task",
            dependencies=u.dependencies,
            requirement_ids=u.requirement_ids,
            acceptance_ids=u.acceptance_ids,
            resource_claims=u.write_paths,
            cost_cap=u.cost_cap,
            recipe_id=u.test_recipe,
        )
        for u in units
    )
