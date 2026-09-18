"""Cross-field tests; synthetic input is never execution authority."""

import copy
import json
import unittest
from pathlib import Path

from deepagents_code.cyrano.contracts.subjects import binding_digest
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.contracts.validation import validate_semantics
from deepagents_code.cyrano.interview.worker_adapter import (
    WorkerBinding,
    validate_worker_binding,
)

ROOT = Path(__file__).resolve().parents[3] / "cyrano"
FIXTURES = json.loads((ROOT / "tests/fixtures/schema-cases.json").read_text())[
    "cases"
]


def example(schema_type: str) -> dict[str, object]:
    """Copy a tagged schema-only fixture before specializing."""
    return copy.deepcopy(
        next(
            c["payload"] for c in FIXTURES if c["id"] == schema_type + "-valid"
        )
    )


class SubjectTests(unittest.TestCase):
    def test_lifecycle_does_not_change_subject(self):
        candidate = example("CandidateProposal")
        changed = {**candidate, "status": "evaluating"}
        self.assertEqual(
            binding_digest("CandidateProposal", candidate),
            binding_digest("CandidateProposal", changed),
        )

    def test_patch_changes_subject(self):
        candidate = example("CandidateProposal")
        changed = {**candidate, "patch_digest": "sha256:" + "b" * 64}
        self.assertNotEqual(
            binding_digest("CandidateProposal", candidate),
            binding_digest("CandidateProposal", changed),
        )

    def test_scope_changes_subject(self):
        candidate = example("CandidateProposal")
        changed = {
            **candidate,
            "scope": {"tenant": "new", "user": "u", "workspace": "w"},
        }
        self.assertNotEqual(
            binding_digest("CandidateProposal", candidate),
            binding_digest("CandidateProposal", changed),
        )

    def test_receipt_is_not_part_of_signed_subject(self):
        plan = example("ExperimentPlan")
        changed = {**plan, "permit_ref": "permit-new", "status": "authorized"}
        self.assertEqual(
            binding_digest("ExperimentPlan", plan),
            binding_digest("ExperimentPlan", changed),
        )

    def test_unknown_subject_type(self):
        with self.assertRaises(CyranoError):
            binding_digest("unknown", {})

    def test_missing_or_extra_subject_field(self):
        candidate = example("CandidateProposal")
        for value in [
            {**candidate, "added_permission": True},
            {k: v for k, v in candidate.items() if k != "scope"},
        ]:
            with self.assertRaises(CyranoError):
                binding_digest("CandidateProposal", value)

    def test_projection_inventory_matches_schema(self):
        schema = json.loads(
            (ROOT / "contracts/v1/cyrano.schema.json").read_text()
        )
        projections = json.loads(
            (ROOT / "contracts/v1/digest-projections.json").read_text()
        )["types"]
        for name, record in projections.items():
            with self.subTest(schema=name):
                left, right = (
                    set(record["subject_fields"]),
                    set(record["envelope_fields"]),
                )
                self.assertFalse(left & right)
                self.assertEqual(
                    left | right, set(schema["$defs"][name]["properties"])
                )

    def test_candidate_no_experiment_hash_cycle(self):
        candidate = example("CandidateProposal")
        self.assertIn("learning_work_plan_digest", candidate)
        self.assertNotIn("experiment_plan_digest", candidate)


class SemanticTests(unittest.TestCase):
    def report(self):
        item = example("EvaluationReport")
        item.update(
            actual_pairs=1,
            planned_pairs=1,
            missing_pairs=0,
            independent_families=1,
            safety_failures=0,
            execution_refs=["base", "candidate"],
            intervals=[
                {
                    "metric": "quality",
                    "lower": "0.01",
                    "estimate": "0.02",
                    "upper": "0.03",
                    "method": "synthetic-test",
                    "unit": "fraction",
                    "measurement_kind": "actual",
                }
            ],
            status="eligible_for_review",
            replay_supported=0,
            replay_scheduled=0,
        )
        return item

    def test_complete_shape_still_not_authority(self):
        self.assertIsNone(validate_semantics(self.report()))

    def test_missing_uncertainty_is_not_eligible(self):
        item = self.report()
        item["intervals"] = []
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_missing_pair_cannot_disappear(self):
        item = self.report()
        item["planned_pairs"] = 2
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_more_actual_than_planned(self):
        item = self.report()
        item["actual_pairs"] = 2
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_duplicate_execution_receipts(self):
        item = self.report()
        item["execution_refs"] = ["same", "same"]
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_zero_actual(self):
        item = self.report()
        item.update(actual_pairs=0, planned_pairs=0)
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_safety_regression(self):
        item = self.report()
        item["safety_failures"] = 1
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_zero_independent_family(self):
        item = self.report()
        item["independent_families"] = 0
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_unknown_and_reversed_intervals(self):
        for vals in [(None, None, None), ("2", "1", "0"), ("NaN", "0", "1")]:
            item = self.report()
            item["intervals"] = [
                dict(zip(["lower", "estimate", "upper"], vals))
            ]
            with self.assertRaises(CyranoError):
                validate_semantics(item)

    def test_negative_counts(self):
        item = self.report()
        item["actual_pairs"] = -1
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_bool_not_count(self):
        item = self.report()
        item["actual_pairs"] = True
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_fake_wire_digest(self):
        item = example("ContextManifest")
        item.update(wire_observed=False, wire_digest="sha256:" + "a" * 64)
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_observed_wire_requires_digest(self):
        item = example("ContextManifest")
        item.update(wire_observed=True, wire_digest=None)
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_unknown_token_precision(self):
        item = example("ContextManifest")
        item.update(
            wire_observed=False,
            wire_digest=None,
            token_count=10,
            token_measurement_source="unknown",
        )
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_invalid_memory_dates(self):
        item = example("MemoryRecord")
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_naive_memory_dates(self):
        item = example("MemoryRecord")
        item.update(
            valid_from="2026-09-16T00:00:00", valid_until="2026-09-17T00:00:00"
        )
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_self_report_not_active_memory(self):
        item = example("MemoryRecord")
        item.update(
            status="active",
            valid_until="2026-09-17T00:00:00Z",
            approval_ref="authority",
        )
        item["evidence_refs"][0]["trust"] = "model_report"
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_template_cannot_activate(self):
        item = example("SkillManifest")
        item.update(
            status="active",
            scope={"tenant": "__BIND_TENANT__", "user": "u", "workspace": "w"},
        )
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_unapproved_skill(self):
        item = example("SkillManifest")
        item.update(status="active", approval_ref=None)
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_plan_approval_not_execution(self):
        item = example("PlanBundle")
        item.update(
            status="executing",
            plan_approval_ref="a",
            review_refs=["r"],
            execution_permit_ref=None,
        )
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_learning_plan_needs_review(self):
        item = example("LearningWorkPlan")
        item.update(status="authorized", authorization_ref="a", review_refs=[])
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_experiment_needs_permit(self):
        item = example("ExperimentPlan")
        item.update(status="running", permit_ref=None)
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_negative_cost_budget(self):
        item = example("ExperimentPlan")
        item["budget"]["cost_limit"] = "-1"
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_release_needs_signature(self):
        item = example("HarnessRelease")
        item.update(
            status="active", promotion_approval_ref="a", signature_ref=None
        )
        with self.assertRaises(CyranoError):
            validate_semantics(item)

    def test_interview_cannot_execute(self):
        item = example("InterviewContract")
        item["execution_authorized"] = True
        with self.assertRaises(CyranoError):
            validate_semantics(item)


class InterviewBindingTests(unittest.TestCase):
    def setUp(self):
        self.expected = WorkerBinding(
            "t", "evidence-scout", 5, "sha256:" + "a" * 64
        )
        self.payload = {
            "task_id": "t",
            "role": "evidence_scout",
            "base_revision": 5,
            "input_digest": "a" * 64,
        }

    def test_original_role_and_digest_are_preserved(self):
        self.assertIsNone(validate_worker_binding(self.payload, self.expected))

    def test_wrong_role(self):
        self.payload["role"] = "facilitator"
        with self.assertRaises(CyranoError):
            validate_worker_binding(self.payload, self.expected)

    def test_stale_result(self):
        self.payload["base_revision"] = 4
        with self.assertRaises(CyranoError):
            validate_worker_binding(self.payload, self.expected)

    def test_wrong_digest(self):
        self.payload["input_digest"] = "b" * 64
        with self.assertRaises(CyranoError):
            validate_worker_binding(self.payload, self.expected)

    def test_wrong_task(self):
        self.payload["task_id"] = "other"
        with self.assertRaises(CyranoError):
            validate_worker_binding(self.payload, self.expected)

    def test_unknown_role(self):
        with self.assertRaises(CyranoError):
            validate_worker_binding(
                self.payload,
                WorkerBinding("t", "unknown", 5, "sha256:" + "a" * 64),
            )

    def test_unqualified_digest(self):
        with self.assertRaises(CyranoError):
            validate_worker_binding(
                self.payload, WorkerBinding("t", "evidence-scout", 5, "a" * 64)
            )
