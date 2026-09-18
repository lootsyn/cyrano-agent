"""Validate this design kit without claiming runtime or model integration."""

from __future__ import annotations

import ast
import base64
import hashlib
import importlib.util
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> Any:
    """Load UTF-8 JSON from a local design artifact."""
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value: dict[str, Any]) -> bytes:
    """Serialize the fixed, float-free signing fixture."""
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def validate() -> dict[str, Any]:
    """Run actual structural checks and return scoped, explicit results."""
    schemas = {}
    for path in sorted((ROOT / "contracts").glob("*.schema.json")):
        document = load(path)
        Draft202012Validator.check_schema(document)
        schemas[path.name.removesuffix(".schema.json")] = document

    valid_count = 0
    for path in sorted((ROOT / "fixtures" / "valid").glob("*.json")):
        validator = Draft202012Validator(
            schemas[path.stem], format_checker=FormatChecker()
        )
        validator.validate(load(path))
        valid_count += 1

    rejected_count = 0
    for case in load(ROOT / "fixtures" / "negative-index.json"):
        validator = Draft202012Validator(schemas[case["schema"]])
        errors = list(validator.iter_errors(load(ROOT / case["file"])))
        if not errors:
            raise AssertionError(
                f"Invalid example accepted: {case['case_id']}"
            )
        rejected_count += 1

    source = load(ROOT / "fixtures" / "source-interview-manifest.json")
    for item in source["files"]:
        data = (ROOT / item["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise AssertionError(f"Original file changed: {item['path']}")

    original = load(
        ROOT / "source_interview" / "fixtures" / "readiness-cases.json"
    )["cases"]
    cases = load(ROOT / "fixtures" / "acceptance-cases.json")["cases"]
    by_id = {case["case_id"]: case for case in cases}
    if len(by_id) != len(cases):
        raise AssertionError("Duplicate acceptance IDs")
    for case in original:
        for key in ("title", "given", "when", "then"):
            if by_id[case["id"]][key] != case[key]:
                raise AssertionError(
                    f"Original regression changed: {case['id']}"
                )
    if any(case["execution_status"] != "not_run" for case in cases):
        raise AssertionError("Acceptance specification claims execution")

    receipt = load(ROOT / "fixtures" / "valid" / "approval-receipt-v2.json")
    attestation = receipt.pop("attestation")
    public = load(ROOT / "fixtures" / "test-public-key.json")
    key = Ed25519PublicKey.from_public_bytes(
        base64.b64decode(public["public_key_base64"])
    )
    signature = base64.urlsafe_b64decode(attestation["signature"] + "==")
    key.verify(signature, canonical(receipt))
    receipt["action"] = "authorize_execution"
    try:
        key.verify(signature, canonical(receipt))
    except InvalidSignature:
        pass
    else:
        raise AssertionError("Tampered receipt accepted")

    connection = sqlite3.connect(":memory:")
    connection.executescript(
        (ROOT / "sql" / "001_initial.sql").read_text(encoding="utf-8")
    )
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    ]
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise AssertionError("Foreign keys disabled")
    connection.execute(
        "INSERT INTO memory_search VALUES (?, ?, ?, ?)",
        ("test-memory", "verification", "review before change", "workflow"),
    )
    if not connection.execute(
        "SELECT memory_id FROM memory_search WHERE memory_search MATCH ?",
        ("verification",),
    ).fetchone():
        raise AssertionError("FTS5 smoke failed")
    try:
        connection.execute(
            "INSERT INTO sessions VALUES "
            "('s','missing','INTAKE',0,0,NULL,NULL,'p','r','l','{}','t','t')"
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("Foreign key violation accepted")
    connection.close()

    for path in ROOT.rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            str(ROOT / "reference"),
            "-p",
            "test_*.py",
            "-v",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    (ROOT / "reference" / "TEST_OUTPUT.txt").write_text(
        result.stdout + result.stderr, encoding="utf-8"
    )
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    match = re.search(r"Ran (\d+) tests", result.stderr)
    if not match:
        raise AssertionError("Cannot determine reference test count")

    return {
        "status": "PASS_STRUCTURAL_AND_REFERENCE_ONLY",
        "schemas_validated": len(schemas),
        "valid_examples_accepted": valid_count,
        "invalid_examples_rejected": rejected_count,
        "source_files_hash_verified": len(source["files"]),
        "original_cases_preserved": len(original),
        "acceptance_cases_defined_not_executed": len(cases),
        "reference_oracle_tests_passed": int(match.group(1)),
        "ed25519_fixture_signature_valid": True,
        "ed25519_fixture_tamper_rejected": True,
        "sql_ddl_executed": True,
        "sqlite_foreign_key_and_fts5_smoke": True,
        "sqlite_tables_including_fts_shadow": tables,
        "python_syntax_validated": True,
        "python_runtime": sys.version.split()[0],
        "dcode_installed_in_validation_env": bool(
            importlib.util.find_spec("deepagents_code")
        ),
        "NOT_RUN": [
            "Actual dcode extension/middleware integration",
            "Actual model calls and prompt-cache billing/latency",
            "Actual cross-session memory behavior in dcode",
            "Governed OS sandbox and trusted human approval E2E",
            "124 acceptance specification cases as runtime tests",
            "Real baseline/holdout self-improvement evaluation",
            "Production dashboard and remote telemetry export",
            "Browser visual render: Chromium executable unavailable",
            "Black/Ruff/mypy quality checks of a completed implementation",
        ],
    }


if __name__ == "__main__":
    report = validate()
    output = ROOT / "VALIDATION_REPORT.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
