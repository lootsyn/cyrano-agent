"""Validate the integrated engineering package, not product runtime."""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

from build_routes import build
from doc_route import safe_file, select_readset

ROOT = Path(__file__).resolve().parents[1]


def pair_coverage(matrix: dict) -> dict:
    """Recompute pair coverage, ignoring the file's claimed counts."""
    factors = matrix["factors"]
    names = sorted(factors)
    required = set()
    for a, b in itertools.combinations(names, 2):
        required.update((a, x, b, y) for x in factors[a] for y in factors[b])
    observed = set()
    for row in matrix["rows"]:
        for name in names:
            if row.get(name) not in factors[name]:
                raise ValueError("UNKNOWN_FACTOR_VALUE:" + name)
        observed.update(
            (a, row[a], b, row[b]) for a, b in itertools.combinations(names, 2)
        )
    return {
        "required": len(required),
        "covered": len(required & observed),
        "missing": sorted(required - observed),
        "row_count": len(matrix["rows"]),
    }


def fixture_report(root: Path) -> dict:
    """Validate exact JSON definitions and fixtures; no remote refs."""
    import jsonschema

    fixtures = json.loads(
        safe_file(
            root,
            "tests/assessment/planning-schema-fixtures.json",
        ).read_text()
    )["fixtures"]
    failures = []
    ids = set()
    for case in fixtures:
        if case["id"] in ids:
            failures.append("DUPLICATE_SCHEMA_CASE:" + case["id"])
        ids.add(case["id"])
        name, pointer = case["schema"].split("#", 1)
        schema = json.loads(safe_file(root, name).read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        focused = {"$defs": schema["$defs"], "$ref": "#" + pointer}
        valid = jsonschema.Draft202012Validator(
            focused,
            format_checker=jsonschema.FormatChecker(),
        ).is_valid(case["value"])
        if valid != case["valid"]:
            failures.append("SCHEMA_EXPECTATION_MISMATCH:" + case["id"])
    return {"executed": len(fixtures), "failures": failures}


def inspect(root: Path = ROOT) -> dict:
    """Inspect every route, case binding and supplied-request owner."""
    errors, blocked = [], []
    counts = {}

    def load(name):
        return json.loads(safe_file(root, name).read_text())

    actual = load(".agents/document-routing.json")
    expected = build(root)
    if actual != expected:
        errors.append("GENERATED_ROUTER_STALE")
    total = 0
    maximum = 0
    for task in expected["tasks"]:
        for stage in ("plan", "implement", "test"):
            manifest, _ = select_readset(root, task, stage=stage)
            maximum = max(maximum, manifest["source_bytes"])
            total += 1
    counts.update(
        routed_tasks=len(expected["tasks"]),
        verified_stage_routes=total,
        max_readset_bytes=maximum,
    )
    plan = load(".agents/work/plan.json")
    owners = {w["id"]: w for w in plan["work_packages"]}
    cases = load("tests/acceptance/catalog.json")["cases"]
    seen = set()
    for case in cases:
        if case["id"] in seen:
            errors.append("DUPLICATE_ACCEPTANCE:" + case["id"])
        seen.add(case["id"])
        if case["id"] not in owners[case["owner_wp"]]["acceptance_ids"]:
            errors.append("UNOWNED_ACCEPTANCE:" + case["id"])
        if case["id"].startswith(
            (
                "CON-",
                "PLAN-0",
                "REVIEW-",
                "HUMAN-",
                "CHANGE-0",
                "RESUME-",
                "COMPLETE-",
                "ISOLATE-",
            )
        ):
            # All new cases are specifications; no fake test execution
            # evidence.
            if case.get("execution_status", "not_run") != "not_run":
                errors.append("UNSUPPORTED_TEST_EXECUTION:" + case["id"])
    counts["acceptance_specifications"] = len(cases)
    counts["integrated_implementation_units"] = sum(
        len(w.get("implementation_units", [])) for w in owners.values()
    )
    for w in owners.values():
        for unit in w.get("implementation_units", []):
            safe_file(root, unit["design_ref"])
            if (
                not unit["implementation_steps"]
                or not unit["acceptance_conditions"]
            ):
                errors.append("INCOMPLETE_WORK_UNIT:" + unit["id"])
            for use in unit.get("consumed_owned_interfaces", []):
                if use["path"] not in owners[use["owner_wp"]]["output_paths"]:
                    errors.append("UNKNOWN_INTERFACE_OWNER:" + use["path"])
    coverage = load("contracts/integration/request-coverage.json")["sections"]
    counts["request_sections"] = len(coverage)
    if len(coverage) != 44:
        errors.append("REQUEST_SECTIONS_INCOMPLETE")
    for section in coverage:
        for name in section["document_owners"]:
            safe_file(root, name)
    pairs = pair_coverage(load("tests/assessment/interaction-matrix.json"))
    counts.update(
        pairwise_rows=pairs["row_count"],
        required_pairs=pairs["required"],
        covered_pairs=pairs["covered"],
    )
    if pairs["missing"]:
        errors.append("PAIRWISE_COVERAGE_GAP")
    runtime = load("contracts/v2/runtime.schema.json")
    if "execution_permit_ref" in runtime["$defs"]["WorkflowIR"]["properties"]:
        errors.append("SELF_REFERENTIAL_WORKFLOW_AUTHORITY")
    counts["runtime_contract_definitions"] = len(runtime["$defs"])
    planning = load("contracts/v2/planning.schema.json")
    counts["planning_contract_definitions"] = len(planning["$defs"])
    forbidden = {
        "progress",
        "approval_ref",
        "execution_permit_ref",
        "signature",
    }
    if forbidden & set(planning["$defs"]["PlanReviewSubject"]["properties"]):
        errors.append("VOLATILE_OR_CYCLIC_SUBJECT")
    try:
        fixtures = fixture_report(root)
        errors.extend(fixtures["failures"])
        counts["planning_shape_cases_executed"] = fixtures["executed"]
    except ImportError:
        blocked.append("jsonschema_unavailable")
    docs = load("docs/document-catalog.json")["documents"]
    inventory = []
    for doc in docs:
        if doc["category"] in {
            "generated",
            "evidence",
            "reference",
            "historical",
        }:
            continue
        path = safe_file(root, doc["path"])
        raw = path.read_bytes()
        if b"NEXTGEN_20260917_" in raw:
            errors.append("UNINTEGRATED_ADDENDUM:" + doc["path"])
        inventory.append(
            {
                "path": doc["path"],
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    counts["current_documents_scanned"] = len(inventory)
    score = load("evidence/product-scorecard.json")
    if (
        score["status"] not in {"not_evaluated", "computed_from_wp_evidence"}
        or score["official_score"] is not None
    ):
        errors.append("UNSUPPORTED_PRODUCT_SCORE")
    return {
        "kind": "engineering_package_checks_not_product_evaluation",
        "success": not errors and not blocked,
        "counts": counts,
        "errors": errors,
        "blocked": blocked,
        "document_inventory": inventory,
        "semantic_review_scope": "key contracts and cross-component "
        "interfaces; inventory does not prove every "
        "sentence correct",
        "not_established": [
            "native_dcode",
            "real_authorization",
            "provider_calls",
            "product_memory_effect",
            "product_learning_effect",
            "UI_execution",
            "OS_isolation",
            "full_python_quality",
        ],
    }


def main() -> int:
    """Write only the latest check report, not a history tree."""
    try:
        result = inspect()
    except (OSError, ValueError, KeyError) as error:
        result = {"success": False, "errors": [str(error)], "blocked": []}
    target = ROOT / "evidence/integrated-check.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "document_inventory"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 2 if result.get("blocked") else int(not result["success"])


if __name__ == "__main__":
    raise SystemExit(main())
