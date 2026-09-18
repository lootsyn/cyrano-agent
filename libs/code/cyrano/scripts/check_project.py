"""Dependency-free structural checks for the dev-ready project."""

import ast
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from graphlib import CycleError, TopologicalSorter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Check source/config/plan structure; no product security claim."""
    errors: list[str] = []
    counts: dict[str, int] = {}
    project = json.loads(
        (ROOT / "project-manifest.json").read_text(encoding="utf-8")
    )
    for package in project["packages"]:
        path = ROOT / package["path"]
        for relative in ["README.md", "__init__.py"]:
            if not (path / relative).is_file():
                errors.append(f"missing package file {path / relative}")
    plan = json.loads(
        (ROOT / ".agents/work/plan.json").read_text(encoding="utf-8")
    )["work_packages"]
    ids = {w["id"] for w in plan}
    if len(ids) != len(plan):
        errors.append("duplicate work package")
    try:
        list(
            TopologicalSorter(
                {w["id"]: set(w["depends_on"]) for w in plan}
            ).static_order()
        )
    except CycleError:
        errors.append("work plan cycle")
    cases = json.loads(
        (ROOT / "tests/acceptance/catalog.json").read_text(encoding="utf-8")
    )["cases"]
    case_ids = {c["id"] for c in cases}
    if len(case_ids) != len(cases):
        errors.append("duplicate acceptance id")
    for case in cases:
        if case["owner_wp"] not in ids:
            errors.append("unknown test owner " + case["id"])
        if not all(case.get(k) for k in ["given", "when", "then"]):
            errors.append("incomplete test " + case["id"])
    for work in plan:
        if not set(work["depends_on"]) <= ids:
            errors.append("unknown dependency " + work["id"])
        for path in work["input_refs"]:
            if not (ROOT / path).exists():
                errors.append("missing WP input " + path)
        for case in work["acceptance_ids"]:
            if case not in case_ids:
                errors.append("unknown WP acceptance " + case)
        if (
            work["status"] == "verified"
            and not (ROOT / work["completion_evidence"]).is_file()
        ):
            errors.append("verified WP without evidence " + work["id"])
    counts.update(
        packages=len(project["packages"]),
        work_packages=len(plan),
        acceptance_specifications=len(cases),
    )
    catalogue = json.loads((ROOT / "configs/tool-catalogue.json").read_text())[
        "tools"
    ]
    tool_ids = {t["id"] for t in catalogue}
    role_paths = list((ROOT / "configs/agents").glob("*.json"))
    skill_paths = list((ROOT / "configs/skills").glob("*.json"))
    skill_ids = {json.loads(p.read_text())["id"] for p in skill_paths}
    role_ids = {json.loads(p.read_text())["id"] for p in role_paths}
    for p in role_paths:
        role = json.loads(p.read_text())
        if not (ROOT / role["prompt_path"]).is_file():
            errors.append("missing role prompt " + str(p))
        if not set(role["skills"]) <= skill_ids:
            errors.append("unknown role skill " + str(p))
        if not set(role["allowed_tools"]) <= tool_ids:
            errors.append("unknown role tool " + str(p))
        if role["authority"] != "proposal_only":
            errors.append("role authority escalation " + str(p))
        for field in ["input_schema", "output_schema"]:
            file, _, fragment = role[field].partition("#")
            path = ROOT / file
            if not path.is_file():
                errors.append("missing role schema " + role[field])
                continue
            node = json.loads(path.read_text())
            for segment in fragment.strip("/").split("/") if fragment else []:
                if segment not in node:
                    errors.append("invalid schema pointer " + role[field])
                    break
                node = node[segment]
    for p in skill_paths:
        skill = json.loads(p.read_text())
        root = ROOT / "plugins/cyrano/skills" / skill["id"]
        entry = root / "SKILL.md"
        if not entry.is_file():
            errors.append("missing skill " + skill["id"])
            continue
        raw = entry.read_bytes()
        if (
            "sha256:" + hashlib.sha256(raw).hexdigest()
            != skill["content_digest"]
        ):
            errors.append("skill digest stale " + skill["id"])
        if len(raw) > skill["context_byte_budget"]:
            errors.append("skill budget " + skill["id"])
        if not set(skill["allowed_roles"]) <= role_ids:
            errors.append("unknown allowed role " + skill["id"])
        if (
            not set(skill["activation_tests"] + skill["counterexample_tests"])
            <= case_ids
        ):
            errors.append("skill acceptance refs missing " + skill["id"])
        for resource in skill["resources"]:
            target = (root / resource["path"]).resolve()
            if (
                not target.is_relative_to(root.resolve())
                or not target.is_file()
            ):
                errors.append("skill resource escape/missing " + skill["id"])
                continue
            if (
                "sha256:" + hashlib.sha256(target.read_bytes()).hexdigest()
                != resource["digest"]
            ):
                errors.append("skill resource stale " + skill["id"])
    counts.update(
        product_roles=len(role_paths),
        product_skills=len(skill_paths),
        developer_skills=len(
            list((ROOT / ".agents/skills").glob("*/SKILL.md"))
        ),
    )
    for p in (ROOT / ".agents/notes").glob("*/*/*.md"):
        if p.name == "AGENTS.md":
            continue
        text = p.read_text(encoding="utf-8")
        stage = p.relative_to(ROOT / ".agents/notes").parts[0]
        if (
            not text.startswith("# Agent Note:")
            or f"Status: {stage}" not in text
        ):
            errors.append("note lifecycle/header " + str(p.relative_to(ROOT)))
        required = (
            [
                "Problem",
                "Proposal",
                "Alternatives considered",
                "Acceptance criteria",
                "Risks",
            ]
            if stage == "proposed"
            else [
                "Problem",
                "Decision",
                "Alternatives considered",
                "Consequences",
            ]
            if stage == "implemented"
            else []
        )
        if not all("## " + heading in text for heading in required):
            errors.append("incomplete note " + str(p.relative_to(ROOT)))
    if (ROOT / "AGENTS.md").stat().st_size > 12000:
        errors.append("root AGENTS byte budget")
    # Validate Markdown targets outside archived input and generated
    # aggregate.
    checked_links = 0
    for p in ROOT.rglob("*.md"):
        relative = str(p.relative_to(ROOT))
        if relative.startswith(("references/", "docs/generated/")):
            continue
        text = p.read_text(encoding="utf-8")
        text = re.sub(r"```.*?```", "", text, flags=re.S)
        for target in re.findall(r"\[[^\]]+\]\(([^\s)]+)\)", text):
            if "://" in target or target.startswith(("#", "mailto:", "data:")):
                continue
            filename = target.partition("#")[0]
            resolved = (p.parent / filename).resolve()
            if not resolved.is_relative_to(ROOT.parent):
                errors.append("external local link " + relative + ":" + target)
            elif not resolved.exists():
                errors.append("missing local link " + relative + ":" + target)
            checked_links += 1
    counts["local_links_checked"] = checked_links
    active_python = (
        list((ROOT.parent / "deepagents_code/cyrano").rglob("*.py"))
        + list((ROOT.parent / "tests/unit_tests/cyrano").rglob("*.py"))
        + [
            p
            for folder in ["scripts", "plugins", "tests"]
            for p in (ROOT / folder).rglob("*.py")
        ]
    )
    for path in active_python:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            errors.append(f"syntax {path.relative_to(ROOT.parent)}: {exc}")
    counts["python_sources_parsed"] = len(active_python)
    # Future SQL is checked in an in-memory DB, not used as a migration.
    try:
        db = sqlite3.connect(":memory:")
        db.executescript(
            (ROOT / "contracts/sql/target-schema.sql").read_text()
        )
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            errors.append("target SQL integrity")
        counts["target_sql_tables"] = db.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
        db.close()
    except sqlite3.DatabaseError as exc:
        errors.append("target SQL invalid: " + str(exc))
    defaults = json.loads(
        (ROOT / "configs/profiles/development.json").read_text()
    )
    for key in [
        "network_enabled",
        "live_model_enabled",
        "learning_enabled",
        "auto_promotion_enabled",
        "remote_trace_export",
    ]:
        if defaults.get(key) is not False:
            errors.append("unsafe default " + key)
    if defaults.get("canary_percent") != 0:
        errors.append("canary default")
    if (
        subprocess.call(
            [sys.executable, str(ROOT / "scripts/build_docs.py"), "--check"]
        )
        != 0
    ):
        errors.append("generated docs freshness")
    if (
        subprocess.call(
            [sys.executable, str(ROOT / "scripts/check_integration.py")]
        )
        != 0
    ):
        errors.append("integration contracts and source traceability")
    if (
        subprocess.call([sys.executable, str(ROOT / "scripts/check_r4.py")])
        != 0
    ):
        errors.append("R4 document routes, schemas, SQL and work mapping")
    report = {
        "kind": "executed_project_structure_check",
        "counts": counts,
        "errors": errors,
        "success": not errors,
        "does_not_establish": [
            "full_lint_typecheck",
            "production_dcode",
            "OS_security",
            "live_effectiveness",
        ],
    }
    (ROOT / "evidence/project-check.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
