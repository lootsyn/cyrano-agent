"""Validate R4 design artifacts and doc routes, not product runtime."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from graphlib import TopologicalSorter
from pathlib import Path

from doc_route import RouteError, select_readset

ROOT = Path(__file__).resolve().parents[1]


def inspect(root: Path = ROOT) -> dict:
    """Check artifact consistency and report missing validators."""
    errors, blocked = [], []
    catalog = json.loads((root / "docs/document-catalog.json").read_text())
    counts = {"documents": len(catalog["documents"])}
    for item in catalog["documents"]:
        path = root / item["path"]
        if not path.is_file():
            errors.append("MISSING_DOCUMENT:" + item["path"])
        elif (
            item.get("sha256")
            and hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]
        ):
            errors.append("STALE_CATALOG:" + item["path"])
    routing = json.loads((root / ".agents/document-routing.json").read_text())
    for task in routing["tasks"]:
        try:
            select_readset(root, task)
        except RouteError as error:
            errors.append(task + ":" + str(error))
    counts["routed_tasks"] = len(routing["tasks"])
    rc = json.loads((root / "docs/development/r4-work-plan.json").read_text())
    rows = rc["refinements"]
    graph = {r["id"]: set(r["depends_on"]) for r in rows}
    try:
        order = list(TopologicalSorter(graph).static_order())
        if set(order) != set(graph):
            errors.append("DANGLING_RC_DEPENDENCY")
    except ValueError:
        errors.append("RC_DEPENDENCY_CYCLE")
    wp = json.loads((root / ".agents/work/plan.json").read_text())
    owners = {x["id"]: x for x in wp["work_packages"]}
    cases = json.loads((root / "tests/r4/cases.json").read_text())["cases"]
    case_ids = {x["id"] for x in cases}
    for row in rows:
        if row["owner_wp"] not in owners:
            errors.append("UNKNOWN_RC_OWNER")
            continue
        if row["owner_wp"] in row["requires_verified_wp_interfaces"]:
            errors.append("SELF_BLOCKING_WP_COMPLETION")
        if not set(row["case_ids"]) <= case_ids:
            errors.append("RC_CASE_MISSING")
        if row["id"] not in owners[row["owner_wp"]]["r4_refinements"]:
            errors.append("RC_OWNER_MAPPING")
    counts.update(refinements=len(rows), r4_case_designs=len(cases))
    try:
        import jsonschema

        fixtures = json.loads(
            (root / "tests/r4/schema-fixtures.json").read_text()
        )["fixtures"]
        for fixture in fixtures:
            filename, fragment = fixture["schema"].split("#", 1)
            schema = json.loads((root / filename).read_text())
            jsonschema.Draft202012Validator.check_schema(schema)
            node = schema
            for part in fragment.strip("/").split("/"):
                node = node[part]
            validator = jsonschema.Draft202012Validator(
                node, format_checker=jsonschema.FormatChecker()
            )
            valid = not list(validator.iter_errors(fixture["value"]))
            if valid != fixture["valid"]:
                errors.append("SCHEMA_CASE_MISMATCH:" + fixture["id"])
        counts["r4_schema_fixtures"] = len(fixtures)
    except ImportError:
        blocked.append("jsonschema_unavailable")
    db = sqlite3.connect(":memory:")
    try:
        for file in [
            "target-schema.sql",
            "governance-extension.sql",
            "r4-memory-observability.sql",
        ]:
            db.executescript((root / "contracts/sql" / file).read_text())
        if db.execute("PRAGMA foreign_key_check").fetchall():
            errors.append("SQL_FOREIGN_KEY_CHECK")
        counts["target_sql_tables"] = db.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
    except sqlite3.Error as error:
        errors.append("SQL_DESIGN_ERROR:" + str(error))
    finally:
        db.close()
    bridge = root.parent / ".agents/skills/cyrano-development/SKILL.md"
    source = root / ".agents/skills/cyrano-development/SKILL.md"
    if not bridge.is_file() or bridge.read_bytes() != source.read_bytes():
        errors.append("DEVELOPER_SKILL_BRIDGE_DRIFT")
    score = json.loads((root / "evidence/product-scorecard.json").read_text())
    if (
        score["status"] == "not_evaluated"
        and score["official_score"] is not None
    ):
        errors.append("UNSUPPORTED_OFFICIAL_SCORE")
    return {
        "kind": "r4_preparation_validation",
        "counts": counts,
        "success": not errors and not blocked,
        "errors": errors,
        "blocked": blocked,
        "not_established": [
            "native_dcode_import",
            "operating_authorization",
            "provider_cache",
            "product_metrics",
            "memory_effectiveness",
            "self_improvement_effectiveness",
        ],
    }


def main() -> int:
    """Persist truthful preparation results for this source snapshot."""
    result = inspect()
    (ROOT / "evidence/r4-preparation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result["blocked"] else int(not result["success"])


if __name__ == "__main__":
    raise SystemExit(main())
