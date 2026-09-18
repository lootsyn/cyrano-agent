"""Execute R3 export-schema positive and negative fixtures only."""

import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Reject malformed exports; shape validity is not authority."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print("ASSESSMENT_SCHEMA_BLOCKED: jsonschema is unavailable")
        return 2
    schema = json.loads(
        (ROOT / "contracts/assessment/evidence.schema.json").read_text()
    )
    Draft202012Validator.check_schema(schema)
    check = Draft202012Validator(schema)
    binding = {
        name: "sha256:" + "a" * 64
        for name in (
            "source_digest",
            "runtime_digest",
            "policy_digest",
            "suite_digest",
        )
    }
    row = {
        "case_id": "synthetic",
        "status": "passed",
        "tests_executed": 1,
        "raw_artifact_refs": ["synthetic://fixture"],
        "review_ref": "synthetic",
        "evidence_kind": "actual_execution",
        **binding,
    }
    base = {
        "schema_version": "cyrano.assessment-evidence/3",
        **binding,
        "scope": "synthetic_fixture_only",
        "records": [row],
        "template_not_execution": False,
    }
    samples = [("valid_export_shape", base, True)]
    for key in schema["required"]:
        value = deepcopy(base)
        value.pop(key)
        samples.append(("missing_" + key, value, False))
    for key, invalid in (
        ("tests_executed", True),
        ("tests_executed", -1),
        ("status", "approved"),
        ("case_id", ""),
        ("evidence_kind", "trusted-because-I-say-so"),
    ):
        value = deepcopy(base)
        value["records"][0][key] = invalid
        samples.append(("invalid_" + key + str(invalid), value, False))
    value = deepcopy(base)
    value["approved"] = True
    samples.append(("injected_approval", value, False))
    failures = [
        name
        for name, value, valid in samples
        if check.is_valid(value) != valid
    ]
    result = {
        "kind": "synthetic_schema_fixtures_not_product_evidence",
        "schemas": 1,
        "cases_checked": len(samples),
        "failed": failures,
        "success": not failures,
        "authentication_verified": False,
    }
    (ROOT / "evidence/assessment-schema.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(json.dumps(result, indent=2))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
