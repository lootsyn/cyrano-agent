"""Structural assessment tests; none award product grading points."""

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

CODE = Path(__file__).resolve().parents[3]
ROOT = CODE / "cyrano"
sys.path.insert(0, str(CODE))
from deepagents_code.cyrano.evaluation.assessment import (
    BINDINGS,
    evidence_structure_errors,
    rubric_errors,
    scorecard_template,
)


class RubricTests(unittest.TestCase):
    def setUp(self):
        self.rubric = json.loads(
            (ROOT / "contracts/assessment/rubric.json").read_text()
        )
        self.cases = json.loads(
            (ROOT / "tests/assessment/cases.json").read_text()
        )["cases"]

    def errors(self):
        return rubric_errors(self.rubric, self.cases)

    def test_exact_weights(self):
        self.assertEqual(self.errors(), [])

    def test_total_forty(self):
        self.assertEqual(
            sum(r["max_points"] for r in self.rubric["criteria"]), 40
        )

    def test_wrong_weight(self):
        self.rubric["criteria"][0]["max_points"] = 2
        self.assertIn("WEIGHT_MISMATCH:1-1", self.errors())

    def test_boolean_weight(self):
        self.rubric["criteria"][0]["max_points"] = True
        self.assertIn("WEIGHT_MISMATCH:1-1", self.errors())

    def test_duplicate_criterion(self):
        self.rubric["criteria"].append(deepcopy(self.rubric["criteria"][0]))
        self.assertIn("DUPLICATE_CRITERION", self.errors())

    def test_missing_criterion(self):
        self.rubric["criteria"].pop()
        self.assertIn("CRITERION_SET_MISMATCH", self.errors())

    def test_atom_total(self):
        self.rubric["criteria"][0]["atoms"][0]["points"] = 0
        self.assertIn("ATOM_TOTAL_MISMATCH:1-1", self.errors())

    def test_duplicate_atom(self):
        row = self.rubric["criteria"][0]
        row["atoms"][1]["id"] = row["atoms"][0]["id"]
        self.assertIn("DUPLICATE_ATOM", self.errors())

    def test_unknown_case(self):
        self.rubric["criteria"][0]["mandatory_case_ids"].append("UNKNOWN")
        self.assertIn("UNKNOWN_CASE:UNKNOWN", self.errors())

    def test_case_wrong_criterion(self):
        self.cases[0]["criterion_id"] = "2-1"
        self.assertIn("CASE_CRITERION_MISMATCH:R3-11-01", self.errors())

    def test_duplicate_case(self):
        self.cases.append(deepcopy(self.cases[0]))
        self.assertIn("DUPLICATE_CASE", self.errors())

    def test_uncovered_case(self):
        self.rubric["criteria"][0]["mandatory_case_ids"].pop()
        self.assertIn("UNCOVERED_CASES", self.errors())

    def test_wrong_maximum(self):
        self.rubric["maximum"] = 100
        self.assertIn("MAXIMUM_MISMATCH", self.errors())

    def test_templates_never_grant_score(self):
        card = scorecard_template(self.rubric)
        self.assertIsNone(card["official_score"])
        self.assertEqual(card["verified_points"], 0)
        self.assertFalse(card["release_eligible"])
        self.assertEqual(len(card["criteria"]), 15)


class EvidenceStructureTests(unittest.TestCase):
    def setUp(self):
        self.binding = {
            name: "sha256:" + str(i + 1) * 64
            for i, name in enumerate(BINDINGS)
        }
        self.row = {
            "case_id": "case1",
            "status": "passed",
            "tests_executed": 1,
            "raw_artifact_refs": ["fixture-only"],
            "review_ref": "fixture-review",
            "evidence_kind": "actual_execution",
            **self.binding,
        }
        self.value = {
            "schema_version": "cyrano.assessment-evidence/3",
            "template_not_execution": False,
            "scope": "synthetic_test_only",
            **self.binding,
            "records": [self.row],
        }

    def errors(self):
        return evidence_structure_errors(self.value, self.binding, {"case1"})

    def test_valid_shape_not_authentication(self):
        self.assertEqual(self.errors(), [])
        self.assertNotIn("authorized", self.value)

    def test_template_rejected(self):
        self.value["template_not_execution"] = True
        self.assertIn("TEMPLATE_NOT_EVIDENCE", self.errors())

    def test_empty_results(self):
        self.value["records"] = []
        self.assertIn("EMPTY_EXECUTION_SET", self.errors())

    def test_binding_drift(self):
        self.value["source_digest"] = "sha256:" + "f" * 64
        self.assertIn("STALE_BINDING:source_digest", self.errors())

    def test_zero_binding(self):
        self.value["source_digest"] = "sha256:" + "0" * 64
        self.assertIn("INVALID_BINDING:source_digest", self.errors())

    def test_malformed_binding(self):
        self.value["runtime_digest"] = "not-a-digest"
        self.assertIn("INVALID_BINDING:runtime_digest", self.errors())

    def test_record_binding_drift(self):
        self.row["policy_digest"] = "sha256:" + "e" * 64
        self.assertIn("RECORD_BINDING_MISMATCH:case1", self.errors())

    def test_zero_executed(self):
        self.row["tests_executed"] = 0
        self.assertIn("NO_EXECUTED_TESTS:case1", self.errors())

    def test_bool_executed(self):
        self.row["tests_executed"] = True
        self.assertIn("NO_EXECUTED_TESTS:case1", self.errors())

    def test_failed_result(self):
        self.row["status"] = "failed"
        self.assertIn("CASE_NOT_PASSED:case1", self.errors())

    def test_skipped_result(self):
        self.row["skipped"] = 1
        self.assertIn("MANDATORY_CASE_NOT_EXECUTED:case1", self.errors())

    def test_xfailed_result(self):
        self.row["xfailed"] = 1
        self.assertIn("MANDATORY_CASE_NOT_EXECUTED:case1", self.errors())

    def test_deselected_result(self):
        self.row["deselected"] = 1
        self.assertIn("MANDATORY_CASE_NOT_EXECUTED:case1", self.errors())

    def test_missing_raw(self):
        self.row["raw_artifact_refs"] = []
        self.assertIn("NO_RAW_ARTIFACTS:case1", self.errors())

    def test_missing_review(self):
        self.row["review_ref"] = None
        self.assertIn("NO_INDEPENDENT_REVIEW:case1", self.errors())

    def test_self_report(self):
        self.row["evidence_kind"] = "self_report"
        self.assertIn("NOT_EXECUTION_EVIDENCE:case1", self.errors())

    def test_duplicate_result(self):
        self.value["records"].append(deepcopy(self.row))
        self.assertIn("DUPLICATE_RESULT:case1", self.errors())

    def test_missing_mandatory(self):
        self.row["case_id"] = "other"
        self.assertIn("MISSING_MANDATORY_CASES", self.errors())

    def test_undeclared_case(self):
        self.row["case_id"] = "unknown"
        self.assertIn("UNDECLARED_CASE:unknown", self.errors())

    def test_wrong_version(self):
        self.value["schema_version"] = "v0"
        self.assertIn("EVIDENCE_VERSION", self.errors())


if __name__ == "__main__":
    unittest.main()
