"""Trusted evaluator for the widgetbox conventions.

Every widgetbox module other than ``__init__`` and ``registry`` must
be listed in ``registry.REGISTERED`` and carry a module docstring;
every registered name must name a module that exists.

Every widget module ``<m>`` must also carry a metadata sidecar
``meta/<m>.json`` satisfying the current sidecar schema. The only
grandfathered artifact is the frozen ``meta/alpha.json`` seed: it may
keep the old ``widgetbox.sidecar/1`` schema only while byte-identical
to the frozen legacy expectation recorded under
``expected/legacy-sidecars.json``. Any other sidecar — new, rewritten,
or belonging to another module — must declare
``widgetbox.sidecar/2``. Sidecars are never deleted: a removed
widget's sidecar stays on disk with ``lifecycle: "retired"``; a
renamed widget carries its sidecar to the new module name. New
widgets enter at lifecycle ``"stable"``.

Per-task sealed expectations live under ``expected/<task>.json`` and
may pin a required lifecycle, require a retired sidecar, or forbid a
sidecar left behind by a rename. This file and its expectations live
outside the agent-editable scope; the model cannot edit the oracle.
Usage: ``python check_conventions.py <repo-root> [<task-key>]`` —
exit 0 pass, 1 convention violation, 2 usage error.
"""

import ast
import hashlib
import json
import sys
from pathlib import Path

LIFECYCLE = ("stable", "beta", "deprecated", "retired")
SCHEMA_V2 = "widgetbox.sidecar/2"
COMPAT_V2 = "widgetbox/2"
REQUIRED = ("name", "schema", "lifecycle", "compat", "owners")
CONTRACT = (
    "WIDGET SIDECAR CONTRACT (widgetbox.sidecar/2): every widget module "
    "<m> requires meta/<m>.json containing {\"name\": <m>, \"schema\": "
    "\"widgetbox.sidecar/2\", \"lifecycle\": one of "
    "stable|beta|deprecated|retired, \"compat\": \"widgetbox/2\", "
    "\"owners\": [non-empty strings, e.g. \"team-widgets\"]}. Sidecars "
    "are never deleted — a removed widget's sidecar stays with lifecycle "
    "\"retired\"; a rename carries the sidecar to the new module name; "
    "new widgets enter at \"stable\". The legacy meta/alpha.json "
    "(widgetbox.sidecar/1) is grandfathered only while untouched; any "
    "sidecar written now must declare widgetbox.sidecar/2."
)


def _load(oracle_dir: Path, name: str) -> dict[str, object]:
    path = oracle_dir / "expected" / name
    if not path.is_file():
        return {}
    data = json.loads(path.read_text())
    return data if isinstance(data, dict) else {}


def _legacy_digests(oracle_dir: Path) -> dict[str, str]:
    data = _load(oracle_dir, "legacy-sidecars.json")
    return {str(k): str(v) for k, v in data.items()}


def _registered(root: Path) -> set[str]:
    tree = ast.parse((root / "widgetbox" / "registry.py").read_text())
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and getattr(node.targets[0], "id", "") == "REGISTERED"
        ):
            return set(ast.literal_eval(node.value))
    return set()


def _modules(root: Path) -> set[str]:
    return {
        p.stem
        for p in (root / "widgetbox").glob("*.py")
        if p.stem not in {"__init__", "registry"}
    }


def _fail(code: str, detail: str) -> int:
    print(f"{code}: {detail}")
    print(CONTRACT)
    return 1


def _sidecar_valid_v2(data: object, name: str) -> str | None:
    """Return the violated tag when a parsed sidecar is not v2."""
    if not isinstance(data, dict):
        return "SIDECAR_INVALID"
    if data.get("schema") != SCHEMA_V2:
        return "SIDECAR_SCHEMA"
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        return "SIDECAR_FIELDS"
    if data["name"] != name:
        return "SIDECAR_NAME"
    if data["lifecycle"] not in LIFECYCLE:
        return "SIDECAR_LIFECYCLE"
    if data["compat"] != COMPAT_V2:
        return "SIDECAR_COMPAT"
    owners = data["owners"]
    if (
        not isinstance(owners, list)
        or not owners
        or not all(isinstance(o, str) and o for o in owners)
    ):
        return "SIDECAR_OWNERS"
    return None


def _check_sidecar(
    root: Path, name: str, legacy: dict[str, str], module_exists: bool
) -> int:
    path = root / "meta" / f"{name}.json"
    if not path.exists():
        if module_exists:
            return _fail("MISSING_SIDECAR", name)
        return 0
    raw = path.read_bytes()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _fail("SIDECAR_INVALID", name)
    is_legacy = hashlib.sha256(raw).hexdigest() == legacy.get(name)
    if is_legacy:
        if module_exists:
            return 0
        return _fail("ORPHAN_SIDECAR", name)
    tag = _sidecar_valid_v2(data, name)
    if tag:
        detail = name if tag != "SIDECAR_FIELDS" else f"{name} fields"
        return _fail(tag, detail)
    if module_exists and data["lifecycle"] == "retired":
        return _fail("RETIRED_PRESENT", name)
    if not module_exists and data["lifecycle"] != "retired":
        return _fail("ORPHAN_SIDECAR", name)
    return 0


def _check_expectations(
    root: Path, expected: dict[str, object]
) -> int:
    retired = expected.get("required_retired") or []
    for name in sorted(str(n) for n in retired):
        path = root / "meta" / f"{name}.json"
        if not path.exists():
            return _fail("MISSING_RETIRED_SIDECAR", name)
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            return _fail("SIDECAR_INVALID", name)
        tag = _sidecar_valid_v2(data, name)
        if tag:
            return _fail(tag, name)
        if data["lifecycle"] != "retired":
            return _fail("NOT_RETIRED", name)
    absent = expected.get("required_absent_sidecars") or []
    for name in sorted(str(n) for n in absent):
        if (root / "meta" / f"{name}.json").exists():
            return _fail("STALE_SIDECAR", name)
    lifecycles = expected.get("expect_lifecycle") or {}
    if isinstance(lifecycles, dict):
        for name in sorted(str(n) for n in lifecycles):
            path = root / "meta" / f"{name}.json"
            if not path.exists():
                return _fail("MISSING_SIDECAR", name)
            try:
                data = json.loads(path.read_text())
            except json.JSONDecodeError:
                return _fail("SIDECAR_INVALID", name)
            if isinstance(data, dict) and data.get(
                "lifecycle"
            ) != lifecycles[name]:
                return _fail("LIFECYCLE_MISMATCH", name)
    return 0


def main(argv: list[str]) -> int:
    """Evaluate the conventions; print the violated rule, if any."""
    if len(argv) not in (2, 3):
        return 2
    root = Path(argv[1])
    registered = _registered(root)
    modules = _modules(root)
    missing = sorted(modules - registered)
    if missing:
        return _fail("UNREGISTERED_MODULE", missing[0])
    stale = sorted(registered - modules)
    if stale:
        return _fail("STALE_REGISTRATION", stale[0])
    undocumented = sorted(
        m
        for m in modules
        if not ast.get_docstring(
            ast.parse((root / "widgetbox" / f"{m}.py").read_text())
        )
    )
    if undocumented:
        return _fail("UNDOCUMENTED_MODULE", undocumented[0])
    oracle_dir = Path(__file__).resolve().parent
    legacy = _legacy_digests(oracle_dir)
    for name in sorted(modules):
        code = _check_sidecar(root, name, legacy, module_exists=True)
        if code:
            return code
    meta_dir = root / "meta"
    sidecars = (
        {p.stem for p in meta_dir.glob("*.json")} if meta_dir.is_dir() else set()
    )
    for name in sorted(sidecars - modules):
        code = _check_sidecar(root, name, legacy, module_exists=False)
        if code:
            return code
    if len(argv) == 3:
        # Fail closed: a supplied task key must name a sealed
        # expectation file, otherwise the per-task checks would be
        # silently skipped.
        expected_path = oracle_dir / "expected" / f"{argv[2]}.json"
        if not expected_path.is_file():
            print(f"NO_EXPECTATIONS: {argv[2]}")
            return 2
        expected = _load(oracle_dir, f"{argv[2]}.json")
        code = _check_expectations(root, expected)
        if code:
            return code
    print("CONVENTION_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
