"""Test the reference contracts without pretending to run a coding agent."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from contracts.reference_models import (
    CheckResult,
    CompletionRequirement,
    QualityPolicy,
    QualityReport,
    derive_verdict,
    structural_completion_rejections,
)

ROOT = Path(__file__).resolve().parents[1]


def read_json(name: str) -> dict:
    """Load a synthetic fixture."""
    return json.loads((ROOT / "fixtures" / name).read_text(encoding="utf-8"))


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = read_json("positive/quality-report.json")
        self.report = QualityReport.model_validate(self.payload)
        self.requirement = CompletionRequirement.model_validate(
            read_json("positive/completion-requirement.json")
        )

    def report_with(self, **updates: object) -> QualityReport:
        payload = copy.deepcopy(self.payload)
        payload.update(updates)
        return QualityReport.model_validate(payload)

    def test_valid_policy(self) -> None:
        QualityPolicy.model_validate(read_json("positive/quality-policy.json"))

    def test_positive_manifest(self) -> None:
        models = {
            "QualityPolicy": QualityPolicy,
            "QualityReport": QualityReport,
            "CompletionRequirement": CompletionRequirement,
        }
        manifest = read_json("manifest.json")
        for entry in manifest["positive"]:
            with self.subTest(entry["path"]):
                models[entry["model"]].model_validate(read_json(entry["path"]))

    def test_negative_manifest(self) -> None:
        models = {
            "QualityPolicy": QualityPolicy,
            "QualityReport": QualityReport,
            "CompletionRequirement": CompletionRequirement,
        }
        for entry in read_json("manifest.json")["negative"]:
            with self.subTest(entry["path"]):
                with self.assertRaises(ValidationError):
                    models[entry["model"]].model_validate(read_json(entry["path"]))

    def test_clean_binding(self) -> None:
        self.assertEqual(
            structural_completion_rejections(self.requirement, self.report), ()
        )

    def test_every_identity_binding(self) -> None:
        fields = (
            "workspace_id", "attempt_id", "plan_digest", "policy_digest",
            "toolchain_digest", "suite_digest",
        )
        for field in fields:
            with self.subTest(field):
                value = "sha256:" + "f" * 64 if field.endswith("digest") else "other"
                report = self.report_with(**{field: value})
                reasons = structural_completion_rejections(self.requirement, report)
                self.assertIn(f"MISMATCH_{field.upper()}", reasons)

    def test_local_report_not_governed(self) -> None:
        report = self.report_with(verification_level="local_advisory")
        self.assertIn(
            "LOCAL_ADVISORY_ONLY",
            structural_completion_rejections(self.requirement, report),
        )

    def test_stale_report_reducer(self) -> None:
        verdict = derive_verdict(
            self.report.required_check_ids, self.report.checks,
            self.report.snapshot_before, "sha256:" + "f" * 64,
        )
        self.assertEqual(verdict, "STALE")

    def test_missing_check_blocks(self) -> None:
        self.assertEqual(
            derive_verdict(
                self.report.required_check_ids, self.report.checks[:-1],
                self.report.snapshot_before, self.report.snapshot_after,
            ),
            "BLOCKED",
        )

    def test_duplicate_check_blocks(self) -> None:
        self.assertEqual(
            derive_verdict(
                self.report.required_check_ids,
                self.report.checks + self.report.checks[:1],
                self.report.snapshot_before, self.report.snapshot_after,
            ),
            "BLOCKED",
        )

    def test_empty_requirements_block(self) -> None:
        self.assertEqual(
            derive_verdict((), (), self.report.snapshot_before,
                           self.report.snapshot_after),
            "BLOCKED",
        )

    def test_raw_fail_cannot_be_claimed_as_pass(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["checks"][-1].update(raw_status="FAIL", exit_code=1)
        with self.assertRaises(ValidationError):
            QualityReport.model_validate(payload)

    def test_error_priority(self) -> None:
        payload = copy.deepcopy(self.payload["checks"][-1])
        payload.update(raw_status="ERROR", exit_code=None)
        checks = self.report.checks[:-1] + (CheckResult.model_validate(payload),)
        self.assertEqual(
            derive_verdict(
                self.report.required_check_ids, checks,
                self.report.snapshot_before, self.report.snapshot_after,
            ),
            "ERROR",
        )

    def test_required_skip_blocks(self) -> None:
        payload = copy.deepcopy(self.payload["checks"][-1])
        payload.update(raw_status="SKIPPED", executed=False, exit_code=None)
        checks = self.report.checks[:-1] + (CheckResult.model_validate(payload),)
        self.assertEqual(
            derive_verdict(
                self.report.required_check_ids, checks,
                self.report.snapshot_before, self.report.snapshot_after,
            ),
            "BLOCKED",
        )

    def test_baseline_is_distinct(self) -> None:
        report = QualityReport.model_validate(
            read_json("positive/baselined-report.json")
        )
        self.assertEqual(report.verdict, "PASS_WITH_BASELINE")
        self.assertTrue(any(check.raw_status == "FAIL" for check in report.checks))
        self.assertIn(
            "BASELINE_NOT_AUTHORIZED",
            structural_completion_rejections(self.requirement, report),
        )

    def test_authorized_baseline_structure(self) -> None:
        data = self.requirement.model_dump(mode="json")
        data["allow_baseline"] = True
        requirement = CompletionRequirement.model_validate(data)
        report = QualityReport.model_validate(
            read_json("positive/baselined-report.json")
        )
        self.assertEqual(structural_completion_rejections(requirement, report), ())

    def test_review_blockers(self) -> None:
        data = self.requirement.model_dump(mode="json")
        data["review_open_blockers"] = 1
        requirement = CompletionRequirement.model_validate(data)
        self.assertIn(
            "REVIEW_HAS_BLOCKERS",
            structural_completion_rejections(requirement, self.report),
        )

    def test_stale_review(self) -> None:
        data = self.requirement.model_dump(mode="json")
        data["review_snapshot_digest"] = "sha256:" + "f" * 64
        requirement = CompletionRequirement.model_validate(data)
        self.assertIn(
            "STALE_REVIEW",
            structural_completion_rejections(requirement, self.report),
        )

    def test_missing_review_approval(self) -> None:
        data = self.requirement.model_dump(mode="json")
        data["review_disposition"] = "request_changes"
        requirement = CompletionRequirement.model_validate(data)
        self.assertIn(
            "REVIEW_NOT_APPROVED",
            structural_completion_rejections(requirement, self.report),
        )

    def test_required_set_binding(self) -> None:
        report = self.report_with(required_check_ids=["format"])
        self.assertIn(
            "MISMATCH_REQUIRED_CHECKS",
            structural_completion_rejections(self.requirement, report),
        )

    def test_report_frozen(self) -> None:
        with self.assertRaises(ValidationError):
            self.report.verdict = "FAIL"

    def test_unexecuted_pass_rejected(self) -> None:
        payload = copy.deepcopy(self.payload["checks"][0])
        payload["executed"] = False
        with self.assertRaises(ValidationError):
            CheckResult.model_validate(payload)

    def test_test_failure_baseline_rejected(self) -> None:
        payload = copy.deepcopy(self.payload["checks"][-1])
        payload.update(
            raw_status="FAIL", exit_code=1, baseline_covered=True,
            baseline_comparison_digest="sha256:" + "b" * 64,
        )
        with self.assertRaises(ValidationError):
            CheckResult.model_validate(payload)

    def test_timeout_is_executed_error(self) -> None:
        payload = copy.deepcopy(self.payload["checks"][0])
        payload.update(raw_status="ERROR", exit_code=None)
        check = CheckResult.model_validate(payload)
        self.assertTrue(check.executed)
        self.assertEqual(check.raw_status, "ERROR")


if __name__ == "__main__":
    unittest.main()
