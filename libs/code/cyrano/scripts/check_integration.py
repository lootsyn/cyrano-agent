"""Check integration artifacts, not product authority."""

import hashlib
import json
import sqlite3
import sys
from graphlib import TopologicalSorter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict | list:
    """Read trusted repository data, never remote references."""
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_reference(root: Path, ref: str) -> object:
    """Resolve a local schema pointer without network access."""
    filename, _, fragment = ref.partition("#")
    path = (root / filename).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("REFERENCE_ESCAPE")
    node = read_json(path)
    for token in fragment.lstrip("/").split("/") if fragment else []:
        token = token.replace("~1", "/").replace("~0", "~")
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def mapping_errors(source: list, target: list, mapping: list) -> list[str]:
    """Check source scenario preservation and intentional ID reuse."""
    errors = []
    sources = {c["case_id"]: c for c in source}
    targets = {c["id"]: c for c in target}
    if len(sources) != len(source) or len(targets) != len(target):
        errors.append("DUPLICATE_CASE_ID")
    seen = set()
    destinations = set()
    for entry in mapping:
        sid, tid = entry["source_id"], entry["target_id"]
        if sid in seen or tid in destinations:
            errors.append("DUPLICATE_CASE_MAPPING")
        seen.add(sid)
        destinations.add(tid)
        if sid not in sources or tid not in targets:
            errors.append("DANGLING_CASE_MAPPING")
            continue
        a, b = sources[sid], targets[tid]
        scenario = {k: a[k] for k in ("given", "when", "then")}
        raw = json.dumps(scenario, ensure_ascii=False, sort_keys=True).encode()
        if hashlib.sha256(raw).hexdigest() != entry["scenario_sha256"]:
            errors.append("SOURCE_SCENARIO_HASH_MISMATCH")
        if any(a[k] != b[k] for k in scenario):
            errors.append("SOURCE_SCENARIO_CHANGED")
        if entry["owner_wp"] != b["owner_wp"]:
            errors.append("CASE_OWNER_MISMATCH")
        if sid.startswith("R") and sid[1:].isdigit():
            if tid != "INT-" + sid:
                errors.append("INTERVIEW_DUPLICATE_INSTEAD_OF_REUSE")
        elif tid != "UH-" + sid:
            errors.append("SOURCE_CASE_NAMESPACE_LOST")
    if seen != set(sources):
        errors.append("MISSING_SOURCE_OBLIGATION")
    return errors


def projection_errors(schema: dict, projections: dict) -> list[str]:
    """Check complete and disjoint signing subjects, not signatures."""
    errors = []
    for name, rule in projections["types"].items():
        properties = set(schema["$defs"][name]["properties"])
        subject = set(rule["subject_fields"])
        envelope = set(rule["envelope_fields"])
        if subject & envelope or subject | envelope != properties:
            errors.append("INVALID_SUBJECT_PROJECTION:" + name)
        if {"attestation", "signature", "profile_digest"} & subject:
            errors.append("SELF_REFERENTIAL_SUBJECT:" + name)
    return errors


def scorecard_errors(scorecard: dict) -> list[str]:
    """Check 15-criterion metadata; never awards product credit."""
    weights = {
        "1-1": 3,
        "1-2": 3,
        "1-3": 4,
        "2-1": 2,
        "2-2": 3,
        "2-3": 3,
        "2-4": 2,
        "3-1": 2,
        "3-2": 3,
        "3-3": 3,
        "3-4": 2,
        "4-1": 3,
        "4-2": 3,
        "4-3": 2,
        "4-4": 2,
    }
    errors = []
    total = 0
    seen = set()
    for entry in scorecard["criteria"]:
        cid, points = entry["id"], entry["points"]
        if cid in seen or cid not in weights:
            errors.append("INVALID_CRITERION_SET")
        seen.add(cid)
        if type(points) is not int or not 0 <= points <= weights.get(cid, 0):
            errors.append("SCORE_OUT_OF_RANGE")
            continue
        total += points
        if points and (
            not entry["evidence_refs"]
            or not entry.get("review_ref")
            or entry["status"] == "not_evaluated"
        ):
            errors.append("UNSUPPORTED_PRODUCT_CREDIT")
    if seen != set(weights):
        errors.append("INVALID_CRITERION_SET")
    if total != scorecard["verified_points"]:
        errors.append("SCORE_TOTAL_MISMATCH")
    gates = scorecard.get("hard_gates", {})
    if scorecard.get("release_eligible") and (
        not gates
        or any(v != "passed" for v in gates.values())
        or scorecard.get("official_score") is None
    ):
        errors.append("HARD_GATE_BYPASS")
    return errors


def check(root: Path = ROOT) -> dict:
    """Inspect manifests and return preparation-only results."""
    errors = []
    counts = {}

    def load(rel):
        return read_json(root / rel)

    imported = load("references/universal-harness-import.json")
    for item in imported["files"]:
        path = root / item["project_path"]
        if not path.is_file():
            errors.append("MISSING_SOURCE:" + item["project_path"])
            continue
        raw = path.read_bytes()
        if (len(raw), hashlib.sha256(raw).hexdigest()) != (
            item["bytes"],
            item["sha256"],
        ):
            errors.append("SOURCE_BYTES_CHANGED:" + item["project_path"])
    counts["preserved_source_files"] = len(imported["files"])
    if len(imported["files"]) != imported["file_count"]:
        errors.append("SOURCE_INVENTORY_COUNT")
    registry = load("contracts/contract-registry.json")
    digest = hashlib.sha256(
        (root / "contracts/v1/cyrano.schema.json").read_bytes()
    ).hexdigest()
    if digest != registry["unchanged_v1_sha256"]:
        errors.append("FROZEN_V1_CHANGED")
    if registry["imported_approval_may_authorize"]:
        errors.append("LEGACY_AUTHORIZATION_UPLIFT")
    for item in registry["target_replacements"]:
        if item["automatic_conversion"]:
            errors.append("AUTOMATIC_AUTHORITY_CONVERSION")
    mapping = load("contracts/integration/acceptance-map.json")
    source = load(
        "references/universal-harness/fixtures/acceptance-cases.json"
    )["cases"]
    target = load("tests/acceptance/catalog.json")["cases"]
    errors += mapping_errors(source, target, mapping["mappings"])
    counts.update(
        mapped_source_cases=len(source),
        reused_interview_cases=sum(
            m["disposition"] == "reuse_exact_case" for m in mapping["mappings"]
        ),
        canonical_product_specifications=len(target),
    )
    section_map = load("contracts/integration/section-map.json")["sections"]
    if {s["source_section"] for s in section_map} != set(range(33)):
        errors.append("INCOMPLETE_SOURCE_SECTIONS")
    for item in section_map:
        for key in ("source_file", "target_note", "integration_owner"):
            if not (root / item[key]).is_file():
                errors.append("MISSING_SECTION_OWNER:" + item[key])
    counts["mapped_source_sections"] = len(section_map)
    source_contracts = load("contracts/integration/source-contract-map.json")[
        "mappings"
    ]
    for item in source_contracts:
        if not (root / item["source_path"]).is_file():
            errors.append("MISSING_SOURCE_SCHEMA")
        for ref in item["targets"]:
            try:
                resolve_reference(root, ref)
            except (OSError, KeyError, ValueError) as exc:
                errors.append("INVALID_TARGET_REFERENCE:" + ref + str(exc))
        if item["authorization_conversion"]:
            errors.append("SOURCE_AUTHORITY_CONVERSION")
    counts["mapped_source_schemas"] = len(source_contracts)
    work = load(".agents/work/plan.json")
    tasks = {w["id"]: w for w in work["work_packages"]}
    try:
        order = list(
            TopologicalSorter(
                {k: set(w["depends_on"]) for k, w in tasks.items()}
            ).static_order()
        )
        if set(order) != set(tasks):
            errors.append("DANGLING_WP_DEPENDENCY")
        declared = work["topological_order"]
        position = {name: i for i, name in enumerate(declared)}
        for name, task in tasks.items():
            for dep in task["depends_on"]:
                if position[dep] >= position[name]:
                    errors.append("INVALID_DECLARED_WP_ORDER")
    except (ValueError, KeyError) as exc:
        errors.append("INVALID_WP_GRAPH:" + str(exc))
    for case in target:
        wp = tasks.get(case["owner_wp"])
        if wp is None or case["id"] not in wp["acceptance_ids"]:
            errors.append("UNOWNED_ACCEPTANCE:" + case["id"])
    counts["work_packages"] = len(tasks)
    counts["integration_work_items"] = sum(
        len(w["integration_tasks"]) for w in tasks.values()
    )
    schema = load("contracts/v2/governance.schema.json")
    projections = load("contracts/v2/digest-projections.json")
    errors += projection_errors(schema, projections)
    state = load("contracts/v2/session-state-machine.json")
    guards = load("contracts/v2/session-guards.json")["guards"]
    names = {g["id"] for g in guards}
    used = set()
    pairs = set()
    for edge in state["transitions"] + state["global_transitions"]:
        used.add(edge["guard_id"])
        sources = edge.get("from_set", [edge.get("from")])
        if edge["to"] not in state["states"]:
            errors.append("INVALID_STATE_TARGET")
        for start in sources:
            key = (start, edge["event"])
            if key in pairs:
                errors.append("AMBIGUOUS_TRANSITION")
            pairs.add(key)
            if start not in state["states"]:
                errors.append("INVALID_STATE_SOURCE")
    if used != names:
        errors.append("UNRESOLVED_OR_ORPHAN_GUARD")
    if state["domain"] != "work_session_not_candidate":
        errors.append("STATE_DOMAIN_CONFLATION")
    for guard in guards:
        if not all(
            guard.get(k)
            for k in (
                "trusted_inputs",
                "algorithm",
                "error_code",
                "evidence_binding",
            )
        ):
            errors.append("INCOMPLETE_GUARD_SPEC")
    counts.update(session_states=len(state["states"]), guards=len(guards))
    event_schema = load("contracts/v2/event-payloads.schema.json")
    event_map = load("contracts/v2/event-catalog.json")["events"]
    declared_events = set(
        schema["$defs"]["GovernedEvent"]["properties"]["event_type"]["enum"]
    )
    if {e["event_type"] for e in event_map} != declared_events:
        errors.append("EVENT_CATALOG_COVERAGE")
    for entry in event_map:
        payload = resolve_reference(root, entry["payload_schema_ref"])
        if payload["properties"]["event_type"]["const"] != entry["event_type"]:
            errors.append("EVENT_PAYLOAD_DISCRIMINANT")
        if entry["agent_can_submit_as_authoritative"]:
            errors.append("MODEL_EVENT_AUTHORITY")
        if payload.get("additionalProperties") is not False:
            errors.append("UNTYPED_EVENT_PAYLOAD")
    counts["typed_event_payloads"] = len(event_schema["$defs"])
    for command in load("contracts/api/command-catalogue.json")["commands"]:
        resolve_reference(root, command["payload_schema_ref"])
    tools = load("configs/tool-catalogue.json")["tools"]
    for tool in tools:
        if tool.get("authority") in ("approve", "grant", "trusted_kernel"):
            errors.append("MODEL_TOOL_AUTHORITY")
    counts["model_tool_ports"] = len(tools)
    profile = load("configs/profiles/development.json")
    for key in (
        "network_enabled",
        "live_model_enabled",
        "learning_enabled",
        "auto_promotion_enabled",
        "remote_trace_export",
    ):
        if profile[key] is not False:
            errors.append("UNSAFE_DEFAULT:" + key)
    if profile["canary_percent"] != 0:
        errors.append("UNSAFE_CANARY_DEFAULT")
    if load("configs/learning-policy.json")["enabled"]:
        errors.append("UNAPPROVED_LEARNING_DEFAULT")
    task_profile = load("configs/task-profile-policy.json")
    reviews = task_profile["default_required_reviews"]
    if set(reviews["spec"]) != {"critic", "blind-handoff-reviewer"}:
        errors.append("SPEC_REVIEW_WEAKENED")
    if task_profile["model_name_branching"]:
        errors.append("MODEL_SPECIALIZATION")
    policy = load("configs/quality/native-policy.json")
    if policy["formatter"] != "ruff" or policy["code_line_length"] != 79:
        errors.append("QUALITY_POLICY_DRIFT")
    scorecard = load("evidence/product-scorecard.json")
    rubric = load("contracts/assessment/rubric.json")
    if sum(c["max_points"] for c in rubric["criteria"]) != 40:
        errors.append("RUBRIC_TOTAL")
    if {c["id"] for c in scorecard["criteria"]} != {
        c["id"] for c in rubric["criteria"]
    }:
        errors.append("RUBRIC_SCORECARD_COVERAGE")
    if scorecard["status"] == "not_evaluated" and (
        scorecard["verified_points"] != 0
        or scorecard["official_score"] is not None
        or scorecard["release_eligible"]
    ):
        errors.append("UNEVALUATED_PRODUCT_CREDIT")
    counts["product_rubric_criteria"] = len(rubric["criteria"])
    try:
        db = sqlite3.connect(":memory:")
        db.executescript(
            (root / "contracts/sql/target-schema.sql").read_text()
        )
        db.executescript(
            (root / "contracts/sql/governance-extension.sql").read_text()
        )
        violations = db.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            errors.append("TARGET_SQL_FOREIGN_KEYS")
        counts["target_sql_tables_including_governance"] = db.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
        db.close()
    except sqlite3.DatabaseError as exc:
        errors.append("TARGET_SQL_ERROR:" + str(exc))
    return {
        "kind": "executed_integration_artifact_validation",
        "revision": "2026-09-16-cyrano-r4",
        "success": not errors,
        "counts": counts,
        "errors": errors,
        "scope": "source preservation and design/config/plan consistency",
        "does_not_establish": [
            "signature_authenticity",
            "runtime_guards",
            "native_dcode",
            "OS_isolation",
            "live_evaluation",
            "full_PEP8_compliance",
            "production_schema_migration",
            "production_event_semantics",
        ],
    }


def main() -> int:
    """Write the results of this local preparation check."""
    report = check()
    path = ROOT / "evidence/integration-validation.json"
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(not report["success"])


if __name__ == "__main__":
    sys.exit(main())
