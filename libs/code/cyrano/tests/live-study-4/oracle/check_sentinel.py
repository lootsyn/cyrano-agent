"""Trusted evaluator for the sentinel cap conventions.

Every ``sentinel/*.py`` file — including ``__init__.py`` and
``registry.py`` — must be matched by a cap ``caps/<stem>.json``, and
``registry.REGISTERED`` must list exactly the live capability modules
(every sentinel stem except ``__init__`` and ``registry``).

Every cap must satisfy the current cap schema. The only grandfathered
artifact is the frozen ``caps/alpha.json`` seed: it may keep the old
``sentinel.cap/2`` schema only while byte-identical to the frozen
legacy expectation recorded under ``expected/legacy-caps.json``. Any
other cap — new, rewritten, or belonging to another module — must
declare ``sentinel.cap/3``. Caps are never deleted: a removed
module's cap stays on disk with ``lifecycle: "removed"``; a renamed
module retires its old cap the same way and enters the new one at
``"provisional"``. New caps enter at lifecycle ``"provisional"`` and
tier ``"standard"`` unless the task states otherwise. Tier
``"privileged"`` requires at least two owners. A cap whose module no
longer exists must have lifecycle ``"removed"``; a live module's cap
may not be ``"removed"``.

Per-task sealed expectations live under ``expected/<task>.json`` and
may pin exact field values per cap path or minimum owner counts.
This file and its expectations live outside the agent-editable
scope; the model cannot edit the oracle. Usage:
``python check_sentinel.py <repo-root> [<task-key>]`` — exit 0 pass,
1 convention violation, 2 usage error.
"""

import ast
import hashlib
import json
import sys
from pathlib import Path

TIERS = ("observer", "standard", "privileged")
LIFECYCLE = ("active", "provisional", "sunset", "removed")
SCHEMA_V3 = "sentinel.cap/3"
SCHEMA_V2 = "sentinel.cap/2"
COMPAT_V3 = "sentinel/3"
REQUIRED = ("name", "schema", "compat", "tier", "lifecycle", "owners")
CONTRACT = (
    "SENTINEL CAP CONTRACT (sentinel.cap/3): every sentinel module "
    "file <m>.py (including __init__.py and registry.py) requires "
    "caps/<m>.json containing {\"name\": <m>, \"schema\": "
    "\"sentinel.cap/3\", \"compat\": \"sentinel/3\", \"tier\": one of "
    "observer|standard|privileged, \"lifecycle\": one of "
    "active|provisional|sunset|removed, \"owners\": [non-empty "
    "strings]}. Caps are never deleted — a removed module's cap stays "
    "with lifecycle \"removed\"; a rename retires the old cap the same "
    "way and enters the new one at \"provisional\"; new caps enter at "
    "\"provisional\" and tier \"standard\" unless the task states "
    "otherwise. Tier \"privileged\" requires at least two owners. A "
    "cap whose module no longer exists must have lifecycle "
    "\"removed\". The legacy caps/alpha.json (sentinel.cap/2) is "
    "grandfathered only while byte-identical to the frozen seed; any "
    "cap written now must declare sentinel.cap/3."
)


def _load(oracle_dir: Path, name: str) -> dict[str, object]:
    path = oracle_dir / "expected" / name
    if not path.is_file():
        return {}
    data = json.loads(path.read_text())
    return data if isinstance(data, dict) else {}


def _legacy_digests(oracle_dir: Path) -> dict[str, str]:
    data = _load(oracle_dir, "legacy-caps.json")
    return {str(k): str(v) for k, v in data.items()}


def _registered(root: Path) -> list[str]:
    tree = ast.parse((root / "sentinel" / "registry.py").read_text())
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and getattr(node.targets[0], "id", "") == "REGISTERED"
        ):
            return sorted(ast.literal_eval(node.value))
    return []


def _module_files(root: Path) -> set[str]:
    return {p.stem for p in (root / "sentinel").glob("*.py")}


def _cap_paths(root: Path) -> dict[str, Path]:
    return {p.stem: p for p in (root / "caps").glob("*.json")}


def _cap_document(path: Path) -> tuple[dict[str, object] | None, str]:
    try:
        body = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, f"{path.name} unparsable: {exc}"
    if not isinstance(body, dict):
        return None, f"{path.name} is not a JSON object"
    return body, ""


def _cap_failures(
    rel: str,
    document: dict[str, object],
    *,
    stem: str,
    legacy: dict[str, str],
    path: Path,
) -> list[str]:
    """Field-level checks; the v2 grandfather is digest-bound."""
    failures: list[str] = []
    schema = document.get("schema")
    if schema == SCHEMA_V2:
        digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if legacy.get(rel) != digest:
            failures.append(
                f"{rel}: schema {SCHEMA_V2} not grandfathered"
            )
        return failures
    if schema != SCHEMA_V3:
        failures.append(f"{rel}: schema {schema!r} != {SCHEMA_V3}")
        return failures
    if document.get("name") != stem:
        failures.append(f"{rel}: name {document.get('name')!r} != {stem!r}")
    if document.get("compat") != COMPAT_V3:
        failures.append(f"{rel}: compat != {COMPAT_V3!r}")
    if document.get("tier") not in TIERS:
        failures.append(f"{rel}: tier {document.get('tier')!r} invalid")
    if document.get("lifecycle") not in LIFECYCLE:
        failures.append(
            f"{rel}: lifecycle {document.get('lifecycle')!r} invalid"
        )
    owners = document.get("owners")
    if (
        not isinstance(owners, list)
        or not owners
        or any(not isinstance(o, str) or not o for o in owners)
    ):
        failures.append(f"{rel}: owners must be a non-empty string list")
    elif document.get("tier") == "privileged" and len(owners) < 2:
        failures.append(f"{rel}: privileged tier needs >=2 owners")
    return failures


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: check_sentinel.py <repo-root> [<task-key>]")
        return 2
    root = Path(sys.argv[1])
    oracle_dir = Path(__file__).resolve().parent
    task_key = sys.argv[2] if len(sys.argv) > 2 else ""
    violations: list[str] = []

    modules = _module_files(root)
    live = sorted(modules - {"__init__", "registry"})

    registered = _registered(root)
    if registered != live:
        violations.append(
            f"REGISTERED {registered} != live modules {live}"
        )

    caps = _cap_paths(root)
    for stem in sorted(modules):
        if stem not in caps:
            violations.append(f"MISSING_CAP: sentinel/{stem}.py")
    legacy = _legacy_digests(oracle_dir)
    for stem, path in sorted(caps.items()):
        rel = path.relative_to(root).as_posix()
        document, error = _cap_document(path)
        if document is None:
            violations.append(f"CAP_UNPARSABLE: {error}")
            continue
        violations.extend(
            _cap_failures(
                rel, document, stem=stem, legacy=legacy, path=path
            )
        )
        lifecycle = document.get("lifecycle")
        if stem not in modules and lifecycle != "removed":
            violations.append(
                f"{rel}: orphan cap must be lifecycle removed"
            )
        if stem in modules and lifecycle == "removed":
            violations.append(
                f"{rel}: live module cap marked removed"
            )

    expectation = _load(oracle_dir, f"{task_key}.json")
    if task_key and not expectation and not (
        oracle_dir / "expected" / f"{task_key}.json"
    ).is_file():
        print(f"NO_EXPECTATIONS: expected/{task_key}.json missing")
        return 2
    must_exist = expectation.get("caps_must_exist", ())
    if isinstance(must_exist, list):
        for rel in must_exist:
            if not (root / str(rel)).is_file():
                violations.append(f"{rel}: cap deleted (caps never delete)")
    cap_fields = expectation.get("cap_fields", {})
    if isinstance(cap_fields, dict):
        for rel, pins in sorted(cap_fields.items()):
            path = root / rel
            if not path.is_file():
                violations.append(f"{rel}: expected cap missing")
                continue
            document, error = _cap_document(path)
            if document is None:
                violations.append(f"CAP_UNPARSABLE: {error}")
                continue
            if isinstance(pins, dict):
                for field, wanted in sorted(pins.items()):
                    if document.get(field) != wanted:
                        violations.append(
                            f"{rel}: {field} "
                            f"{document.get(field)!r} != {wanted!r}"
                        )
    min_owners = expectation.get("min_owners", {})
    if isinstance(min_owners, dict):
        for rel, minimum in sorted(min_owners.items()):
            path = root / rel
            document = None
            if path.is_file():
                document, _ = _cap_document(path)
            owners = (
                document.get("owners") if isinstance(document, dict) else None
            )
            count = len(owners) if isinstance(owners, list) else 0
            if count < int(minimum):
                violations.append(
                    f"{rel}: owners {count} < required {minimum}"
                )

    if violations:
        print("CONVENTION VIOLATIONS:")
        for item in violations:
            print(f"- {item}")
        print()
        print(CONTRACT)
        return 1
    print("conventions satisfied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
