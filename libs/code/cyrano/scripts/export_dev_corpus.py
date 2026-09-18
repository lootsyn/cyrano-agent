"""Export a verified task readset to an immutable, owned corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from doc_route import select_readset

ROOT = Path(__file__).resolve().parents[1]


def export_task(task: str, *, apply: bool, root: Path = ROOT) -> dict:
    """Copy only catalog-verified task documents; return digests.

    Development helper, not a product ACL service. It rejects
    reference packs by default and never copies raw traces or secrets.
    """
    selected, bodies = select_readset(root, task)
    target = root / "tools/.state/corpus" / task / selected["readset_digest"]
    current = root
    for part in target.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("CORPUS_SYMLINK")
    rows = []
    for index, (source, text) in enumerate(bodies):
        raw = text.encode()
        name = f"{index:04d}.md"
        rows.append(
            {
                "source": source,
                "exported": name,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        dest = target / name
        if dest.is_symlink():
            raise ValueError("CORPUS_FILE_SYMLINK")
        if dest.exists() and dest.read_bytes() != raw:
            raise ValueError("IMMUTABLE_CORPUS_CHANGED")
        if apply:
            target.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                with dest.open("xb") as handle:
                    handle.write(raw)
    result = {
        "kind": "developer_readset_export",
        "task": task,
        "readset_digest": selected["readset_digest"],
        "corpus_path": str(target),
        "documents": rows,
        "product_acl_authority": False,
    }
    if apply:
        path = target / "corpus-manifest.json"
        raw = (
            json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        ).encode()
        if path.is_symlink():
            raise ValueError("CORPUS_MANIFEST_SYMLINK")
        if path.exists() and path.read_bytes() != raw:
            raise ValueError("CORPUS_MANIFEST_CHANGED")
        if not path.exists():
            with path.open("xb") as handle:
                handle.write(raw)
    return result


def main() -> int:
    """Print a no-write plan unless the developer supplies --apply."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                export_task(args.task, apply=args.apply),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (ValueError, OSError, KeyError) as error:
        print(json.dumps({"status": "blocked", "error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
