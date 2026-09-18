"""Build task doc routes from current plans without loading them."""

from __future__ import annotations

import json
from pathlib import Path

from doc_route import safe_file

ROOT = Path(__file__).resolve().parents[1]
STAGES = ("plan", "implement", "test")
FORBIDDEN_PREFIXES = ("docs/generated/", "references/", "evidence/")


def _load(root: Path, name: str) -> dict:
    """Read one owned JSON file, refusing links and path escapes."""
    return json.loads(safe_file(root, name).read_text(encoding="utf-8"))


def build(root: Path = ROOT) -> dict:
    """Return deterministic routes for every current WP, TS, RC and RF.

    A new task is registered when its owning plan declares a document
    and
    reading references. Missing owners and duplicate identities fail
    closed.
    Resource paths are navigation only; they are not injected into
    prompts.
    """
    work = _load(root, ".agents/work/plan.json")["work_packages"]
    by_id = {row["id"]: row for row in work}
    if len(by_id) != len(work):
        raise ValueError("DUPLICATE_WORK_ID")
    for row in work:
        if not set(row["depends_on"]) <= set(by_id):
            raise ValueError("UNKNOWN_WORK_DEPENDENCY:" + row["id"])
    from graphlib import TopologicalSorter

    tuple(
        TopologicalSorter(
            {r["id"]: r["depends_on"] for r in work}
        ).static_order()
    )
    tasks: dict = {}
    stages: dict = {}
    resources: dict = {}
    owners: dict = {}

    def register(row: dict, document: str, owner: str, design: str) -> None:
        task = row["id"]
        if task in tasks:
            raise ValueError("DUPLICATE_ROUTE_ID:" + task)
        if owner not in by_id:
            raise ValueError("UNKNOWN_ROUTE_OWNER:" + task)
        declared = row.get("reading_refs", {})
        routes = {}
        for stage in STAGES:
            default = (
                [document, design]
                if stage != "test"
                else [
                    document,
                    "docs/testing/STRATEGY.ko.md",
                ]
            )
            paths = list(dict.fromkeys(declared.get(stage, default)))
            if not paths or document not in paths:
                raise ValueError("TASK_DOCUMENT_NOT_ROUTED:" + task)
            for relative in paths:
                if relative.startswith(FORBIDDEN_PREFIXES):
                    raise ValueError("UNSAFE_DEFAULT_DOCUMENT:" + relative)
                if not relative.endswith(".md"):
                    raise ValueError("NOT_A_DOCUMENT:" + relative)
                safe_file(root, relative)
            routes[stage] = paths
        tasks[task] = routes["implement"]
        stages[task] = routes
        paths = row.get("resource_refs", by_id[owner].get("resource_refs", []))
        for relative in paths:
            safe_file(root, relative)
        resources[task] = list(dict.fromkeys(paths))
        owners[task] = owner

    for row in work:
        register(row, row["document"], row["id"], row["primary_design"])
    for file, key, prefix in (
        ("docs/development/test-work-plan.json", "tasks", "TS"),
        ("docs/development/r4-work-plan.json", "refinements", "RC"),
        ("docs/development/r5-work-plan.json", "refinements", "RF"),
    ):
        for row in _load(root, file)[key]:
            if prefix == "TS":
                matches = [
                    w["id"]
                    for w in work
                    if row["id"] in w.get("assessment_test_tasks", [])
                ]
                owner = row.get("owner_wp") or (
                    matches[0]
                    if matches
                    else (row.get("execute_requires_wp") or ["WP20"])[0]
                )
                document = row.get(
                    "document", f"docs/testing/work/{row['id']}.ko.md"
                )
                # Existing project uses docs/development/test-work/ on
                # some tasks.
                if not (root / document).is_file():
                    alternatives = sorted(
                        root.glob(f"docs/**/{row['id']}.ko.md")
                    )
                    if len(alternatives) != 1:
                        raise ValueError(
                            "AMBIGUOUS_TEST_DOCUMENT:" + row["id"]
                        )
                    document = alternatives[0].relative_to(root).as_posix()
                design = by_id[owner]["primary_design"]
            else:
                owner = row["owner_wp"]
                document = row.get(
                    "document",
                    f"docs/development/refinements/{row['id']}.ko.md",
                )
                design = row.get("design", row.get("design_ref"))
            register(row, document, owner, design)
    return {
        "schema_version": "cyrano.document-routing/1",
        "not_native_dcode_configuration": True,
        "generated_from": [
            ".agents/work/plan.json",
            "docs/development/test-work-plan.json",
            "docs/development/r4-work-plan.json",
            "docs/development/r5-work-plan.json",
        ],
        "always": ["AGENTS.md", "docs/NAVIGATION.ko.md"],
        "tasks": dict(sorted(tasks.items())),
        "stages": dict(sorted(stages.items())),
        "resources": dict(sorted(resources.items())),
        "owner_wp": dict(sorted(owners.items())),
        "rule": "Never inject the full catalog, resources, "
        "or research corpus.",
    }


def generate(root: Path = ROOT) -> dict:
    """Replace the generated router only after all paths validate."""
    value = build(root)
    target = root / ".agents/document-routing.json"
    raw = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(raw, encoding="utf-8")
    temporary.replace(target)
    return value


if __name__ == "__main__":
    print(json.dumps({"routed_tasks": len(generate()["tasks"])}))
