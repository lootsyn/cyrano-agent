"""Validate R5 prep artifacts; never award product success."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from graphlib import TopologicalSorter
from pathlib import Path

from doc_route import select_readset

ROOT = Path(__file__).resolve().parents[1]


def inspect(root: Path = ROOT) -> dict:
    """Check referential consistency, schemas and target SQL."""
    errors, blocked, counts = [], [], {}
    data = json.loads(
        (root / "docs/development/r5-work-plan.json").read_text()
    )
    rows = data["refinements"]
    graph = {row["id"]: set(row["depends_on"]) for row in rows}
    try:
        order = list(TopologicalSorter(graph).static_order())
        if set(order) != set(graph):
            errors.append("UNKNOWN_RF_DEPENDENCY")
    except ValueError:
        errors.append("RF_CYCLE")
    owners = {
        row["id"]: row
        for row in json.loads((root / ".agents/work/plan.json").read_text())[
            "work_packages"
        ]
    }

    def ancestors(ident, seen=None):
        seen = set() if seen is None else set(seen)
        if ident in seen:
            return set()
        seen.add(ident)
        deps = set(owners[ident]["depends_on"])
        return deps | set().union(*(ancestors(d, seen) for d in deps))

    cases = json.loads((root / "tests/r5/cases.json").read_text())["cases"]
    catalog = json.loads((root / "tests/acceptance/catalog.json").read_text())[
        "cases"
    ]
    case_ids = {c["id"] for c in cases}
    if len(case_ids) != len(cases):
        errors.append("DUPLICATE_R5_CASE")
    if len({c["id"] for c in catalog}) != len(catalog):
        errors.append("DUPLICATE_CATALOG_CASE")
    if not case_ids <= {c["id"] for c in catalog}:
        errors.append("R5_CASE_NOT_CATALOGUED")
    for row in rows:
        owner = row["owner_wp"]
        if owner not in owners:
            errors.append("UNKNOWN_OWNER:" + owner)
            continue
        if row["id"] not in owners[owner].get("r5_refinements", []):
            errors.append("RF_OWNER_DRIFT:" + row["id"])
        for required in row["requires_verified_wp_interfaces"]:
            if required not in owners or required == owner:
                errors.append("SELF_OR_UNKNOWN_INTERFACE:" + row["id"])
            elif owner in ancestors(required):
                errors.append("DOWNSTREAM_INTERFACE_CYCLE:" + row["id"])
        if not set(row["case_ids"]) <= case_ids:
            errors.append("MISSING_RF_CASE:" + row["id"])
        for path in [
            row["document"],
            row["design"],
            f"docs/testing/r5/{row['id']}.ko.md",
        ]:
            if not (root / path).is_file():
                errors.append("MISSING_RF_DOCUMENT:" + path)
        try:
            select_readset(root, row["id"])
        except (ValueError, OSError, KeyError) as error:
            errors.append("RF_READSET:" + str(error))
    for c in cases:
        if c["execution_status"] != "not_run":
            errors.append("SPEC_CHANGED_TO_EXECUTION:" + c["id"])
        if len(c["procedure"]) < 4 or not c["then"] or not c["evidence"]:
            errors.append("INSUFFICIENT_CASE:" + c["id"])
    counts.update(
        refinements=len(rows),
        new_product_case_specs=len(cases),
        all_product_case_specs=len(catalog),
    )
    recipes = json.loads((root / "tools/manifest.json").read_text())["recipes"]
    for recipe in recipes:
        if (
            recipe["enabled"]
            or recipe["installed"]
            or recipe["runtime_verified"]
        ):
            errors.append("UNSUPPORTED_TOOL_ACTIVATION:" + recipe["id"])
    counts["optional_tool_recipes"] = len(recipes)
    bindings = json.loads(
        (root / "configs/r5-skill-bindings.json").read_text()
    )
    for row in bindings["bindings"]:
        path = root / row["path"]
        if (
            hashlib.sha256(path.read_bytes()).hexdigest()
            != row["source_digest"]
        ):
            errors.append("SKILL_DIGEST_DRIFT:" + row["skill_id"])
    counts["new_skill_bindings"] = len(bindings["bindings"])
    try:
        import jsonschema

        fixtures = json.loads(
            (root / "tests/r5/schema-fixtures.json").read_text()
        )["fixtures"]
        for fixture in fixtures:
            schema = json.loads((root / fixture["schema"]).read_text())
            jsonschema.Draft202012Validator.check_schema(schema)
            validator = jsonschema.Draft202012Validator(schema)
            valid = not list(validator.iter_errors(fixture["value"]))
            if valid != fixture["valid"]:
                errors.append("R5_SCHEMA_CASE:" + fixture["id"])
        counts["schema_fixtures"] = len(fixtures)
    except ImportError:
        blocked.append("jsonschema_missing")
    db = sqlite3.connect(":memory:")
    try:
        for name in [
            "target-schema.sql",
            "governance-extension.sql",
            "r4-memory-observability.sql",
            "r5-adaptive-index.sql",
        ]:
            db.executescript((root / "contracts/sql" / name).read_text())
        if db.execute("PRAGMA foreign_key_check").fetchall():
            errors.append("SQL_FOREIGN_KEY_ERROR")
        counts["target_ddl_tables"] = db.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
    except sqlite3.Error as error:
        errors.append("SQL_DDL:" + str(error))
    finally:
        db.close()
    monitor = json.loads((root / "configs/monitoring-policy.json").read_text())
    if monitor["primary_surface"] != "native_dcode_textual":
        errors.append("MONITOR_PRIMARY_SURFACE")
    if monitor["native_command_implemented"]:
        errors.append("UNVERIFIED_NATIVE_ACTIVATION")
    return {
        "kind": "executed_preparation_validation_not_product",
        "success": not errors and not blocked,
        "counts": counts,
        "errors": errors,
        "blocked": blocked,
        "not_established": [
            "native_dcode_runtime",
            "Textual_screen_execution",
            "third_party_tool_installation",
            "operating_isolation",
            "memory_or_learning_effectiveness",
            "provider_cache",
        ],
    }


def main() -> int:
    """Persist the actual check result; product evidence unchanged."""
    result = inspect()
    (ROOT / "evidence/r5-preparation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result["blocked"] else int(not result["success"])


if __name__ == "__main__":
    raise SystemExit(main())
