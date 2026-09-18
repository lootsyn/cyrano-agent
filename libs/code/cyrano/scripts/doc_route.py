"""Select deterministic, scoped dev documents; never activate agents."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {"generated", "historical", "evidence"}


class RouteError(ValueError):
    """A requested readset is unsafe, stale, unknown, or too large."""


def safe_file(root: Path, relative: str) -> Path:
    """Resolve a catalog path; reject traversal and symlinks."""
    if not relative or "\\" in relative:
        raise RouteError("UNSAFE_DOCUMENT_PATH")
    parts = relative.split("/")
    if relative.startswith("/") or any(p in {"", ".", ".."} for p in parts):
        raise RouteError("UNSAFE_DOCUMENT_PATH")
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise RouteError("DOCUMENT_SYMLINK")
    if not current.resolve().is_relative_to(root.resolve()):
        raise RouteError("DOCUMENT_ESCAPE")
    if not current.is_file():
        raise RouteError("DOCUMENT_MISSING:" + relative)
    return current


def select_readset(
    root: Path,
    task: str,
    *,
    max_bytes: int = 98304,
    allow_reference: bool = False,
    stage: str = "implement",
) -> tuple[dict, list[tuple[str, str]]]:
    """Return a stable manifest and verified source bodies for one task.

    Args:
        root: Cyrano development-resource directory.
        task: Registered WP, TS, RC or RF identifier.
        stage: plan, implement, or test document selection.
        max_bytes: Maximum sum of UTF-8 source bytes, not a token limit.
        allow_reference: Permit explicitly routed reference sources.

    Returns:
        A deterministic readset manifest and ordered path/content pairs.

    Raises:
        RouteError: A task, path, digest, authority, or budget is
        invalid.
    """
    if max_bytes < 1:
        raise RouteError("INVALID_READSET_BUDGET")
    if stage not in {"plan", "implement", "test"}:
        raise RouteError("UNKNOWN_STAGE:" + stage)
    catalog = json.loads(
        safe_file(root, "docs/document-catalog.json").read_text()
    )
    routing = json.loads(
        safe_file(root, ".agents/document-routing.json").read_text()
    )
    if task not in routing["tasks"]:
        raise RouteError("UNKNOWN_TASK:" + task)
    entries = {item["path"]: item for item in catalog["documents"]}
    selected = (
        routing.get("stages", {})
        .get(task, {})
        .get(stage, routing["tasks"][task])
    )
    paths = list(dict.fromkeys(routing["always"] + selected))
    records, bodies = [], []
    for relative in paths:
        if relative not in entries:
            raise RouteError("UNREGISTERED_DOCUMENT:" + relative)
        entry = entries[relative]
        category = entry["category"]
        if category in FORBIDDEN:
            raise RouteError("NONCANONICAL_DEFAULT_DOCUMENT")
        if category == "reference" and not allow_reference:
            raise RouteError("EXPLICIT_REFERENCE_CONSENT_REQUIRED")
        raw = safe_file(root, relative).read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != entry.get("sha256"):
            raise RouteError("STALE_DOCUMENT_CATALOG:" + relative)
        records.append(
            {
                "path": relative,
                "category": category,
                "sha256": actual,
                "bytes": len(raw),
            }
        )
        bodies.append((relative, raw.decode("utf-8")))
    size = sum(item["bytes"] for item in records)
    if size > max_bytes:
        raise RouteError(f"READSET_TOO_LARGE:{size}>{max_bytes}")
    canonical = json.dumps(records, sort_keys=True, separators=(",", ":"))
    manifest = {
        "task": task,
        "documents": records,
        "source_bytes": size,
        "readset_digest": hashlib.sha256(canonical.encode()).hexdigest(),
        "token_count": None,
        "provider_cache_hit": "not_measured",
        "stage": stage,
        "owner_wp": routing.get("owner_wp", {}).get(task),
        "resource_paths_not_loaded": routing.get("resources", {}).get(
            task, []
        ),
    }
    return manifest, bodies


def main() -> int:
    """Print the selected manifest, optionally the read bodies."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True)
    parser.add_argument("--content", action="store_true")
    parser.add_argument(
        "--stage", choices=["plan", "implement", "test"], default="implement"
    )
    parser.add_argument("--reference", action="store_true")
    parser.add_argument("--max-bytes", type=int, default=98304)
    args = parser.parse_args()
    try:
        manifest, bodies = select_readset(
            ROOT,
            args.task,
            max_bytes=args.max_bytes,
            allow_reference=args.reference,
            stage=args.stage,
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        if args.content:
            for path, content in bodies:
                print(f"\n--- DOCUMENT: {path} ---\n{content}")
        return 0
    except (RouteError, OSError, ValueError, KeyError) as error:
        print(json.dumps({"status": "blocked", "error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
