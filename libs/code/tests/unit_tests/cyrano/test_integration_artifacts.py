"""Test artifact preservation, not product enforcement."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "cyrano"
sys.path.insert(0, str(ROOT / "scripts"))
from check_integration import (  # noqa: E402
    check,
    mapping_errors,
    projection_errors,
    resolve_reference,
    scorecard_errors,
)
from style_audit import inspect_text  # noqa: E402


def load(path):
    """Read a local synthetic input."""
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class MappingTests(unittest.TestCase):
    """Reject dropped, changed or double-counted source obligations."""

    def setUp(self):
        self.source = load(
            "references/universal-harness/fixtures/acceptance-cases.json"
        )["cases"]
        self.target = load("tests/acceptance/catalog.json")["cases"]
        self.mapping = load("contracts/integration/acceptance-map.json")[
            "mappings"
        ]

    def errors(self):
        return mapping_errors(self.source, self.target, self.mapping)

    def test_source_scenarios_are_preserved(self):
        self.assertEqual(self.errors(), [])

    def test_missing_mapping_is_not_empty_success(self):
        self.mapping.pop()
        self.assertIn("MISSING_SOURCE_OBLIGATION", self.errors())

    def test_duplicate_source_mapping_is_rejected(self):
        self.mapping.append(copy.deepcopy(self.mapping[0]))
        self.assertIn("DUPLICATE_CASE_MAPPING", self.errors())

    def test_changed_expected_result_is_detected(self):
        self.target[0]["then"] = "approve without evidence"
        self.assertIn("SOURCE_SCENARIO_CHANGED", self.errors())

    def test_changed_source_invalidates_hash(self):
        self.source[0]["given"] = "changed input"
        self.assertIn("SOURCE_SCENARIO_HASH_MISMATCH", self.errors())

    def test_dropped_canonical_case_is_rejected(self):
        self.target.pop(0)
        self.assertIn("DANGLING_CASE_MAPPING", self.errors())

    def test_duplicate_canonical_id_is_rejected(self):
        self.target.append(copy.deepcopy(self.target[0]))
        self.assertIn("DUPLICATE_CASE_ID", self.errors())

    def test_case_owner_must_match_work_package(self):
        self.mapping[0]["owner_wp"] = "WP23"
        self.assertIn("CASE_OWNER_MISMATCH", self.errors())

    def test_interview_does_not_get_a_second_credit_id(self):
        self.mapping[0]["target_id"] = "UH-R01"
        self.target[0]["id"] = "UH-R01"
        self.assertIn("INTERVIEW_DUPLICATE_INSTEAD_OF_REUSE", self.errors())

    def test_namespace_prevents_requirement_id_collision(self):
        entry = next(m for m in self.mapping if m["source_id"] == "PLAN-01")
        case = next(c for c in self.target if c["id"] == entry["target_id"])
        entry["target_id"] = "PLAN-01"
        case["id"] = "PLAN-01"
        self.assertIn("SOURCE_CASE_NAMESPACE_LOST", self.errors())


class ProjectionTests(unittest.TestCase):
    """Check signing fields, not a signature service."""

    def setUp(self):
        self.schema = load("contracts/v2/governance.schema.json")
        self.rules = load("contracts/v2/digest-projections.json")

    def test_current_subjects_cover_fields_exactly(self):
        self.assertEqual(projection_errors(self.schema, self.rules), [])

    def test_missing_delivery_mode_is_rejected(self):
        self.rules["types"]["GovernedWorkPlan"]["subject_fields"].remove(
            "delivery_mode"
        )
        self.assertTrue(projection_errors(self.schema, self.rules))

    def test_signature_cannot_hash_itself(self):
        rule = self.rules["types"]["TrustedApprovalReceipt"]
        rule["subject_fields"].append("attestation")
        rule["envelope_fields"].remove("attestation")
        self.assertIn(
            "SELF_REFERENTIAL_SUBJECT:TrustedApprovalReceipt",
            projection_errors(self.schema, self.rules),
        )

    def test_overlap_is_not_a_complete_subject(self):
        self.rules["types"]["GovernedWorkPlan"]["envelope_fields"].append(
            "delivery_mode"
        )
        self.assertTrue(projection_errors(self.schema, self.rules))

    def test_local_schema_pointer_resolves(self):
        node = resolve_reference(
            ROOT, "contracts/v2/governance.schema.json#/$defs/SessionQuery"
        )
        self.assertFalse(node["additionalProperties"])

    def test_schema_pointer_cannot_escape_project(self):
        with self.assertRaises(ValueError):
            resolve_reference(ROOT, "../outside.json")

    def test_unknown_type_cannot_default(self):
        with self.assertRaises(KeyError):
            resolve_reference(
                ROOT, "contracts/v2/governance.schema.json#/$defs/Missing"
            )


class ScorecardTests(unittest.TestCase):
    """Reject unsupported awards and hard-gate bypass."""

    def setUp(self):
        self.score = copy.deepcopy(load("evidence/product-scorecard.json"))
        # Keep unit input synthetic when product evidence is added
        # later.
        self.score["verified_points"] = 0
        self.score["release_eligible"] = False
        for item in self.score["criteria"]:
            item.update(
                points=0,
                status="not_evaluated",
                evidence_refs=[],
                review_ref=None,
            )
        self.score["hard_gates"] = {
            key: "not_tested"
            for key in ("authorization", "isolation", "regression")
        }

    def test_unexecuted_scorecard_claims_no_points(self):
        self.assertEqual(scorecard_errors(self.score), [])
        self.assertEqual(self.score["verified_points"], 0)

    def test_points_without_evidence_are_rejected(self):
        self.score["criteria"][0]["points"] = 2
        self.score["verified_points"] = 2
        self.assertIn(
            "UNSUPPORTED_PRODUCT_CREDIT", scorecard_errors(self.score)
        )

    def test_totals_must_match_criteria(self):
        self.score["verified_points"] = 40
        self.assertIn("SCORE_TOTAL_MISMATCH", scorecard_errors(self.score))

    def test_release_cannot_ignore_unrun_hard_gates(self):
        self.score["release_eligible"] = True
        self.assertIn("HARD_GATE_BYPASS", scorecard_errors(self.score))

    def test_one_criterion_cannot_exceed_its_actual_weight(self):
        self.score["criteria"][0]["points"] = 4
        self.score["verified_points"] = 4
        self.assertIn("SCORE_OUT_OF_RANGE", scorecard_errors(self.score))


class StyleMigrationTests(unittest.TestCase):
    """Report physical line limits without modifying source code."""

    def test_short_code_has_no_length_findings(self):
        self.assertEqual(inspect_text("value = 1\n", "sample.py"), [])

    def test_long_code_is_a_finding(self):
        result = inspect_text("name = '" + "a" * 90 + "'\n", "sample.py")
        self.assertEqual(result[0]["limit"], 79)

    def test_comment_uses_72_limit(self):
        result = inspect_text("# " + "a" * 73 + "\n", "sample.py")
        self.assertEqual(result[0]["kind"], "comment")
        self.assertEqual(result[0]["limit"], 72)

    def test_docstring_uses_72_limit(self):
        text = '"""' + "a" * 75 + '"""\n'
        self.assertEqual(inspect_text(text, "sample.py")[0]["limit"], 72)

    def test_syntax_error_is_not_a_clean_audit(self):
        with self.assertRaises(SyntaxError):
            inspect_text("def f(:\n", "sample.py")


class WholeArtifactTests(unittest.TestCase):
    """Inspect integration files, not runtime behavior."""

    def test_complete_integration_report(self):
        report = check(ROOT)
        self.assertTrue(report["success"], report["errors"])
        self.assertEqual(report["counts"]["mapped_source_cases"], 124)
        self.assertEqual(report["counts"]["work_packages"], 24)

    def test_session_and_candidate_machines_are_distinct(self):
        state = load("contracts/v2/session-state-machine.json")
        self.assertEqual(state["domain"], "work_session_not_candidate")
        self.assertEqual(len(state["states"]), 29)
        candidate = ROOT / "../deepagents_code/cyrano/kernel/transitions.py"
        self.assertTrue(candidate.is_file())

    def test_all_guard_specs_name_real_evidence_inputs(self):
        guards = load("contracts/v2/session-guards.json")["guards"]
        self.assertEqual(len(guards), 38)
        for guard in guards:
            self.assertEqual(guard["authority"], "trusted_service_only")
            self.assertTrue(guard["trusted_inputs"])
            self.assertTrue(guard["algorithm"])
            self.assertTrue(guard["error_code"])

    def test_source_code_is_not_mounted_as_an_active_plugin(self):
        registry = load("contracts/contract-registry.json")
        self.assertFalse(registry["source_contracts_are_runtime_types"])
        composition = load("configs/agent-composition.json")
        self.assertNotIn("references/universal-harness", str(composition))

    def test_imported_fixtures_do_not_claim_product_execution(self):
        source = load(
            "references/universal-harness/fixtures/acceptance-cases.json"
        )
        for case in source["cases"]:
            self.assertEqual(case["execution_status"], "not_run")


if __name__ == "__main__":
    unittest.main()
