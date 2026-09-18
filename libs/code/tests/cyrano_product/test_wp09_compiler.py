"""WP09 compiler tests: restricted IR, DAG checks, identity binding."""

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.workflow.compiler import (
    WorkflowNode,
    compile_workflow,
    propose_expansion,
)


def _node(node_id, kind="agent_task", deps=(), **kw):
    kw.setdefault("cost_cap", 100)
    return WorkflowNode(
        node_id=node_id, kind=kind, dependencies=tuple(deps), **kw
    )


def test_con_wfl_01_normal_dag_preserves_order():
    nodes = (
        _node("read-1", kind="read", cost_cap=None),
        _node("task-1", deps=("read-1",)),
        _node("verify-1", kind="verify", deps=("task-1",)),
        _node(
            "human-1",
            kind="human_decision",
            deps=("verify-1",),
            cost_cap=None,
        ),
        _node("apply-1", kind="apply_candidate", deps=("human-1",)),
    )
    compiled = compile_workflow(nodes, revision=1)
    order = compiled.order
    assert order.index("read-1") < order.index("task-1")
    assert order.index("task-1") < order.index("verify-1")
    assert order.index("verify-1") < order.index("human-1")
    assert order.index("human-1") < order.index("apply-1")
    assert compiled.budget_total == 300


def test_con_wfl_02_self_cycle_rejected():
    with pytest.raises(CyranoError) as exc:
        compile_workflow((_node("A", deps=("A",)),))
    assert exc.value.code == "DAG_CYCLE"


def test_con_wfl_03_indirect_cycle_rejected():
    nodes = (
        _node("A", deps=("C",)),
        _node("B", deps=("A",)),
        _node("C", deps=("B",)),
    )
    with pytest.raises(CyranoError) as exc:
        compile_workflow(nodes)
    assert exc.value.code == "DAG_CYCLE"


def test_con_wfl_04_unbound_requirement():
    nodes = (_node("A", requirement_ids=("R9",)),)
    with pytest.raises(CyranoError) as exc:
        compile_workflow(nodes, known_requirements=frozenset({"R1", "R2"}))
    assert exc.value.code == "UNBOUND_REQUIREMENT"


def test_con_wfl_05_arbitrary_code_condition_rejected():
    for bad in (
        {"op": "eval", "args": ["__import__('os')"]},
        {"op": "call", "args": [{"op": "literal", "value": "rm -rf"}]},
        "os.system('id')",
        {"op": "eq", "args": [{"op": "field", "node": "X", "name": "f"}, 1]},
    ):
        node = _node("B", deps=("A",), condition=bad)
        with pytest.raises(CyranoError) as exc:
            compile_workflow((_node("A"), node))
        assert exc.value.code == "INPUT_INVALID"


def test_con_wfl_05b_valid_typed_condition_compiles():
    cond = {
        "op": "and",
        "args": [
            {
                "op": "eq",
                "args": [
                    {"op": "field", "node": "A", "name": "status"},
                    {"op": "literal", "value": "ok"},
                ],
            },
            {
                "op": "not",
                "args": [
                    {
                        "op": "eq",
                        "args": [
                            {"op": "field", "node": "A", "name": "skipped"},
                            {"op": "literal", "value": True},
                        ],
                    },
                ],
            },
        ],
    }
    node = _node("B", deps=("A",), condition=cond)
    compiled = compile_workflow((_node("A"), node))
    assert "B" in compiled.order


def test_con_wfl_07_expansion_mints_new_revision():
    base = compile_workflow((_node("A"),), revision=1)
    grown = propose_expansion(
        base,
        (_node("B", deps=("A",)),),
        policy_max_nodes=10,
        policy_max_cost=500,
    )
    assert grown.revision == 2
    assert grown.workflow_digest != base.workflow_digest


def test_con_wfl_07b_expansion_over_policy_rejected():
    base = compile_workflow((_node("A"),), revision=1)
    with pytest.raises(CyranoError) as exc:
        propose_expansion(
            base,
            (_node("B", cost_cap=900),),
            policy_max_nodes=10,
            policy_max_cost=200,
        )
    assert exc.value.code == "BUDGET_UNBOUND"


def test_con_wfl_09_duplicate_node_id():
    nodes = (
        _node("A", scope_ref="s1"),
        _node("A", scope_ref="s2"),
    )
    with pytest.raises(CyranoError) as exc:
        compile_workflow(nodes)
    assert exc.value.code == "INPUT_INVALID"


def test_con_wfl_10_uncapped_node_rejected():
    node = WorkflowNode(node_id="A", kind="agent_task", cost_cap=None)
    with pytest.raises(CyranoError) as exc:
        compile_workflow((node,))
    assert exc.value.code == "BUDGET_UNBOUND"


def test_con_wfl_11_unregistered_recipe():
    node = _node("A", recipe_id="pytest-missing")
    with pytest.raises(CyranoError) as exc:
        compile_workflow((node,), known_recipes=frozenset({"pytest-unit"}))
    assert exc.value.code == "CAPABILITY_UNAVAILABLE"


def test_plan_dag_static_rejections():
    # missing dependency
    with pytest.raises(CyranoError) as exc:
        compile_workflow((_node("A", deps=("ghost",)),))
    assert exc.value.code == "DAG_CYCLE"
    # duplicate task id
    with pytest.raises(CyranoError):
        compile_workflow((_node("A"), _node("A")))
    # cycle
    with pytest.raises(CyranoError):
        compile_workflow((_node("A", deps=("B",)), _node("B", deps=("A",))))
