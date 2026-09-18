"""Read acceptance specs for one work package, never run them."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from doc_route import safe_file

ROOT = Path(__file__).resolve().parents[1]


def select(root: Path, task: str, case: str | None = None) -> list[dict]:
    """Select owned cases; reject unknown tasks and cross-task IDs."""
    plan = json.loads(safe_file(root, ".agents/work/plan.json").read_text())
    owners = {w["id"]: w for w in plan["work_packages"]}
    if task not in owners:
        raise ValueError("UNKNOWN_WORK_PACKAGE:" + task)
    data = json.loads(
        safe_file(root, "tests/acceptance/catalog.json").read_text()
    )
    rows = data["cases"] if isinstance(data, dict) else data
    ids = set(owners[task]["acceptance_ids"])
    selected = [
        c for c in rows if c["id"] in ids and (case is None or c["id"] == case)
    ]
    if not selected:
        raise ValueError("NO_MATCHING_OWNED_CASE")
    return sorted(selected, key=lambda item: item["id"])


def main() -> int:
    """Print an index, or one complete case on explicit selection."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True)
    parser.add_argument("--case")
    args = parser.parse_args()
    try:
        rows = select(ROOT, args.task, args.case)
        if args.case is None:
            rows = [
                {
                    k: c[k]
                    for k in ("id", "title", "given", "when", "then")
                    if k in c
                }
                for c in rows
            ]
        print(
            json.dumps(
                {"kind": "specification_not_execution", "cases": rows},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (ValueError, KeyError, OSError) as error:
        print(json.dumps({"status": "blocked", "error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
