"""Check schema fixtures without asserting runtime authority."""

import json
from pathlib import Path

from check_integration import resolve_reference

ROOT = Path(__file__).resolve().parents[1]


def load(relative: str) -> dict | list:
    """Read a repository fixture or schema."""
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def references(value: object) -> list[str]:
    """Collect local JSON references without network resolution."""
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref" and isinstance(item, str):
                found.append(item)
            found.extend(references(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(references(item))
    return found


def main() -> int:
    """Run explicit current and imported shape tests."""
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError:
        print("SCHEMA_VALIDATION_BLOCKED: jsonschema is not installed")
        return 2
    failures = []
    schema_files = sorted(ROOT.glob("contracts/v*/*.schema.json"))
    definitions = 0
    for path in schema_files:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        definitions += len(schema.get("$defs", {}))
        for ref in references(schema):
            if ref.startswith("#/"):
                resolve_reference(ROOT, str(path.relative_to(ROOT)) + ref)
    case_count = 0
    for sf, cf in [
        (
            "contracts/v1/cyrano.schema.json",
            "tests/fixtures/schema-cases.json",
        ),
        (
            "contracts/v2/governance.schema.json",
            "tests/fixtures/governance-schema-cases.json",
        ),
        (
            "contracts/v2/event-payloads.schema.json",
            "tests/fixtures/event-schema-cases.json",
        ),
    ]:
        schema = load(sf)
        cases = load(cf)["cases"]
        seen = set()
        for case in cases:
            if case["id"] in seen:
                failures.append("DUPLICATE_FIXTURE:" + case["id"])
            seen.add(case["id"])
            focused = {
                "$defs": schema["$defs"],
                "$ref": "#/$defs/" + case["schema_type"],
            }
            errors = list(
                Draft202012Validator(
                    focused, format_checker=FormatChecker()
                ).iter_errors(case["payload"])
            )
            case_count += 1
            if (not errors) != case["valid"]:
                detail = errors[0].message if errors else "accepted invalid"
                failures.append(case["id"] + ": " + detail)
    templates = 0
    schema = load("contracts/v1/cyrano.schema.json")
    for folder, typ in [
        ("configs/agents", "AgentRole"),
        ("configs/skills", "SkillManifest"),
    ]:
        focused = {"$defs": schema["$defs"], "$ref": "#/$defs/" + typ}
        validator = Draft202012Validator(
            focused, format_checker=FormatChecker()
        )
        for path in (ROOT / folder).glob("*.json"):
            templates += 1
            errors = list(
                validator.iter_errors(
                    json.loads(path.read_text(encoding="utf-8"))
                )
            )
            if errors:
                failures.append(
                    str(path.relative_to(ROOT)) + ": " + errors[0].message
                )
    source_base = "references/universal-harness/"
    source_schemas = {}
    for path in (ROOT / source_base / "contracts").glob("*.schema.json"):
        source = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(source)
        source_schemas[path.name.removesuffix(".schema.json")] = source
    source_cases = 0
    for path in (ROOT / source_base / "fixtures/valid").glob("*.json"):
        source_cases += 1
        valid = Draft202012Validator(
            source_schemas[path.stem], format_checker=FormatChecker()
        ).is_valid(json.loads(path.read_text(encoding="utf-8")))
        if not valid:
            failures.append("IMPORTED_VALID_FIXTURE:" + path.name)
    for case in load(source_base + "fixtures/negative-index.json"):
        source_cases += 1
        valid = Draft202012Validator(
            source_schemas[case["schema"]],
            format_checker=FormatChecker(),
        ).is_valid(load(source_base + case["file"]))
        if valid:
            failures.append("IMPORTED_INVALID_ACCEPTED:" + case["case_id"])
    api = load("contracts/api/openapi.json")
    for ref in references(api):
        if ref.startswith("#/components/schemas/"):
            if ref.split("/")[-1] not in api["components"]["schemas"]:
                failures.append("DANGLING_OPENAPI_REF:" + ref)
        elif not ref.startswith("#"):
            filename, marker, fragment = ref.partition("#")
            path = (ROOT / "contracts/api" / filename).resolve()
            try:
                resolve_reference(
                    ROOT, str(path.relative_to(ROOT)) + marker + fragment
                )
            except (ValueError, KeyError, OSError):
                failures.append("INVALID_OPENAPI_REF:" + ref)
    for command in load("contracts/api/command-catalogue.json")["commands"]:
        try:
            node = resolve_reference(ROOT, command["payload_schema_ref"])
            if not isinstance(node, dict):
                failures.append("INVALID_COMMAND_SCHEMA:" + command["name"])
        except (ValueError, KeyError, OSError):
            failures.append("UNDEFINED_COMMAND:" + command["name"])
    report = {
        "kind": "executed_versioned_schema_validation",
        "schemas_checked": len(schema_files),
        "schema_definitions": definitions,
        "cases_checked": case_count,
        "role_skill_templates_checked": templates,
        "imported_schemas_checked": len(source_schemas),
        "imported_shape_cases_checked": source_cases,
        "failed_cases": failures,
        "success": not failures,
        "api_check_scope": "local refs, not a running OpenAPI server",
        "authority_checks": "not_implied_by_JSON_schema",
        "source_code_executed": False,
    }
    (ROOT / "evidence/schema-validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
