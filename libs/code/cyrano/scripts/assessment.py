"""Inspect assessment design and prep status; no product scoring."""

import argparse
import ast
import hashlib
import json

from bootstrap import activate

ROOT = activate()
from deepagents_code.cyrano.evaluation.assessment import rubric_errors


def load(relative: str):
    """Read a local CYRANO JSON artifact."""
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def validate() -> dict:
    """Validate rubric, preservation, ownership, and test-dev DAG."""
    from graphlib import TopologicalSorter

    rubric = load("contracts/assessment/rubric.json")
    cases = load("tests/assessment/cases.json")["cases"]
    errors = rubric_errors(rubric, cases)
    packed = load("contracts/integration/r3-reference-packs.json")
    entries = packed["files"]
    for item in entries:
        path = ROOT / item["path"]
        if not path.is_file():
            errors.append("MISSING_REFERENCE:" + str(path))
            continue
        raw = path.read_bytes()
        if (
            hashlib.sha256(raw).hexdigest() != item["sha256"]
            or len(raw) != item["bytes"]
        ):
            errors.append("REFERENCE_CHANGED:" + item["path"])
    catalogue = load("tests/acceptance/catalog.json")["cases"]
    ids = {c["id"] for c in catalogue}
    py_cases = load("tests/assessment/python-pack-cases.json")["cases"]
    if len(ids) != len(catalogue):
        errors.append("DUPLICATE_CATALOGUE_ID")
    if not {c["id"] for c in cases + py_cases} <= ids:
        errors.append("UNREGISTERED_NEW_CASE")
    tasks = load("docs/development/test-work-plan.json")["tasks"]
    tids = {t["id"] for t in tasks}
    owners = {w["id"] for w in load(".agents/work/plan.json")["work_packages"]}
    try:
        graph = {t["id"]: t["depends_on"] for t in tasks}
        if not all(set(v) <= tids for v in graph.values()):
            errors.append("UNKNOWN_TS_DEPENDENCY")
        list(TopologicalSorter(graph).static_order())
    except ValueError:
        errors.append("TEST_PLAN_CYCLE")
    for task in tasks:
        if not set(task["execute_requires_wp"]) <= owners:
            errors.append("UNKNOWN_WP_PREREQUISITE")
        if not set(task["case_ids"]) <= ids:
            errors.append("UNKNOWN_TS_CASE")
    for case in cases:
        required = (
            "given",
            "when",
            "then",
            "steps",
            "assertions",
            "fixture_build_contract",
            "artifact_requirements",
        )
        if not all(case.get(k) for k in required):
            errors.append("INCOMPLETE_CASE:" + case["id"])
        if case["owner_wp"] not in owners:
            errors.append("UNKNOWN_CASE_OWNER")
    return {
        "kind": "assessment_preparation_not_product_evaluation",
        "success": not errors,
        "criteria": len(rubric["criteria"]),
        "point_atoms": sum(len(c["atoms"]) for c in rubric["criteria"]),
        "new_grading_cases": len(cases),
        "python_pack_cases": len(py_cases),
        "all_acceptance_specs": len(catalogue),
        "preserved_new_reference_files": len(entries),
        "test_development_tasks": len(tasks),
        "errors": errors,
    }


def inventory() -> dict:
    """Check planned test symbols; never executes or marks passed."""
    cases = load("tests/assessment/cases.json")["cases"]
    missing = []
    present = []
    for case in cases:
        target = ROOT / case["implementation_test_path"]
        found = set()
        if target.is_file():
            syntax = ast.parse(target.read_text(encoding="utf-8"))
            found = {
                n.name
                for n in ast.walk(syntax)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
        if case["implementation_test_symbol"] not in found:
            missing.append(
                {
                    "case_id": case["id"],
                    "path": case["implementation_test_path"],
                    "symbol": case["implementation_test_symbol"],
                }
            )
        else:
            present.append(case["id"])
    return {
        "status": "blocked" if missing else "collectable_not_executed",
        "code": "BLOCKED_PRODUCT_TESTS_NOT_IMPLEMENTED"
        if missing
        else "SYMBOLS_PRESENT_NOT_EXECUTED",
        "planned": len(cases),
        "present_symbols": len(present),
        "missing": missing,
        "executed": 0,
        "scored": False,
        "limitation": "AST presence is not pytest collection or "
        "runtime evidence.",
    }


def main() -> int:
    """Run one read-only assessment preparation operation."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("validate", "inventory", "report", "product")
    )
    parser.add_argument("--collect-only", action="store_true")
    args = parser.parse_args()
    if args.command == "validate":
        result = validate()
        output = ROOT / "evidence/assessment-preparation.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        )
        code = 0 if result["success"] else 1
    elif args.command == "report":
        result = load("evidence/product-scorecard.json")
        code = 0
    elif args.command == "inventory" or args.collect_only:
        result = inventory()
        code = 2 if result["missing"] else 0
    else:
        result = {
            "status": "blocked",
            "code": "PRODUCT_RUNNER_NOT_IMPLEMENTED",
            "remedy": "Implement the TS plan and trusted runtime "
            "runner first.",
        }
        code = 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
