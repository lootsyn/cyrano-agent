"""Validate this design package, not a dcode runtime or learning engine.

Requires jsonschema and PyYAML. All fixture records are synthetic.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError as exc:
    raise SystemExit("Install jsonschema and PyYAML in a validation environment.") from exc

ROOT = Path(__file__).resolve().parents[1]


def load_json(relative_path: str) -> Any:
    """Read a package-local JSON document."""
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def check(condition: bool, description: str) -> None:
    """Fail rather than silently record a successful check."""
    if not condition:
        raise ValueError(description)


def main() -> int:
    """Validate structure and fixtures and write a narrowly scoped report."""
    report_path = ROOT / "evidence/design-validation.json"
    report: dict[str, Any] = {
        "scope": "design_package_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "failed",
        "highest_demonstrated_level": "contract_tested",
        "checks": [],
        "runtime_integration": "not_tested",
        "replay_engine_execution": "not_tested",
        "security_boundary_enforcement": "not_tested",
        "real_model_effectiveness": "not_tested",
        "canary_and_rollback_execution": "not_tested",
    }
    try:
        schema = load_json("contracts/dream-contracts.schema.json")
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        report["checks"].append({"name": "schema_syntax", "status": "passed"})
        fixtures = load_json("fixtures/contract-cases.json")
        for case in fixtures["positive"]:
            validator.validate(case["record"])
        for case in fixtures["negative"]:
            check(
                not validator.is_valid(case["record"]),
                f"Negative fixture unexpectedly accepted: {case['name']}",
            )
        report["checks"].append(
            {
                "name": "synthetic_schema_fixtures",
                "status": "passed",
                "positive_passed": len(fixtures["positive"]),
                "negative_rejected": len(fixtures["negative"]),
            }
        )
        config = yaml.safe_load(
            (ROOT / "config/dream.example.yaml").read_text(encoding="utf-8")
        )
        check(config["enabled"] is False, "Example must not start learning.")
        check(
            config["release"]["automatic_promotion"] is False,
            "Example must not authorize automatic promotion.",
        )
        check(
            config["release"]["canary_enabled"] is False,
            "Example must not authorize a canary rollout.",
        )
        check(
            config["learning"]["require_experiment_permit"] is True,
            "Experiment permits must be required.",
        )
        report["checks"].append(
            {"name": "example_config_safe_defaults", "status": "passed"}
        )
        cases = yaml.safe_load(
            (ROOT / "tests/acceptance-tests.yaml").read_text(encoding="utf-8")
        )["cases"]
        check(len({case["id"] for case in cases}) == len(cases), "Duplicate case ID.")
        check(
            all(case["execution_status"] == "not_run" for case in cases),
            "Unexecuted product scenarios must not be marked as passed.",
        )
        check(
            all(case.get(key) for case in cases for key in ("given", "when", "then")),
            "Incomplete acceptance specification.",
        )
        report["checks"].append(
            {
                "name": "acceptance_spec_inventory",
                "status": "passed",
                "specifications": len(cases),
                "product_tests_executed": 0,
            }
        )
        required = [
            "README.ko.md",
            "DESIGN.ko.md",
            "FULL_DESIGN.ko.md",
            "FULL_DESIGN.ko.html",
            "IMPLEMENTATION_HANDOFF.ko.md",
            "contracts/SEMANTICS.ko.md",
            "prompts/roles.ko.md",
            "SOURCES.md",
            "sources.json",
        ]
        for filename in required:
            check((ROOT / filename).is_file(), f"Missing package file: {filename}")
        source_ids = {s["id"] for s in load_json("sources.json")["external_sources"]}
        check(source_ids == {f"S{i:02d}" for i in range(1, 9)}, "Source inventory mismatch.")
        report["checks"].append({"name": "package_inventory", "status": "passed"})
        report["status"] = "passed"
        report["limitations"] = [
            "Synthetic JSON records only; production digests are not verified.",
            "Semantic service checks, type checking, authorization, and replay are not implemented here.",
            "No real dcode, model, sandbox, holdout, deployment, or rollback was executed.",
        ]
    except (ValueError, OSError, KeyError, TypeError) as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        # Preserve a truthful failure report for third-party schema/YAML errors.
        report["error"] = f"{type(exc).__name__}: {exc}"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
