"""Specification-only regression checks; not real dcode integration tests."""

from __future__ import annotations

import unittest
from dataclasses import replace

from kernel_oracle import (
    VerifiedGateFacts,
    canonical_bytes,
    digest,
    promotion_blockers,
    readiness,
    validate_dag,
)


class CanonicalTests(unittest.TestCase):
    """Check the explicitly chosen signing serialization."""

    def test_key_order(self) -> None:
        self.assertEqual(digest({"b": 2, "a": 1}), digest({"a": 1, "b": 2}))

    def test_array_order(self) -> None:
        self.assertNotEqual(digest([1, 2]), digest([2, 1]))

    def test_unicode_preserved(self) -> None:
        self.assertNotEqual(digest("é"), digest("e\u0301"))

    def test_float_rejected(self) -> None:
        with self.assertRaises(ValueError):
            canonical_bytes({"amount": 1.2})

    def test_nested_float_rejected(self) -> None:
        with self.assertRaises(ValueError):
            canonical_bytes({"x": [float("nan")]})

    def test_non_string_keys_rejected(self) -> None:
        with self.assertRaises(ValueError):
            canonical_bytes({1: "value"})

    def test_bytes_rejected(self) -> None:
        with self.assertRaises(ValueError):
            canonical_bytes(b"raw")

    def test_boolean_preserved(self) -> None:
        self.assertEqual(canonical_bytes({"x": True}), b'{"x":true}')

    def test_decimal_string(self) -> None:
        self.assertEqual(canonical_bytes("1.25"), b'"1.25"')

    def test_empty_object(self) -> None:
        self.assertEqual(canonical_bytes({}), b"{}")


class GateTests(unittest.TestCase):
    """Check the semantics of trusted readiness facts."""

    def setUp(self) -> None:
        self.facts = VerifiedGateFacts()

    def test_complete_facts(self) -> None:
        self.assertEqual(readiness("completion", self.facts), ())

    def test_unresolved_blocks(self) -> None:
        facts = replace(self.facts, unresolved=1)
        self.assertIn("UNRESOLVED_OBLIGATION", readiness("spec", facts))

    def test_missing_review(self) -> None:
        facts = replace(self.facts, required_review_missing=True)
        self.assertIn("REQUIRED_REVIEW_MISSING", readiness("spec", facts))

    def test_stale_review(self) -> None:
        facts = replace(self.facts, reviews_current=False)
        self.assertIn("STALE_REVIEW", readiness("plan", facts))

    def test_spec_approval_for_plan(self) -> None:
        facts = replace(self.facts, spec_approved=False)
        self.assertIn("SPEC_APPROVAL_REQUIRED", readiness("plan", facts))

    def test_plan_not_execution_approval(self) -> None:
        facts = replace(self.facts, execution_authorized=False)
        self.assertIn(
            "EXECUTION_APPROVAL_REQUIRED", readiness("execution", facts)
        )

    def test_missing_plan_approval(self) -> None:
        facts = replace(self.facts, plan_approved=False)
        self.assertIn("PLAN_APPROVAL_REQUIRED", readiness("execution", facts))

    def test_scope_denied(self) -> None:
        facts = replace(self.facts, scope_valid=False)
        self.assertIn("SCOPE_DENIED", readiness("execution", facts))

    def test_audit_failure(self) -> None:
        facts = replace(self.facts, audit_healthy=False)
        self.assertIn("AUDIT_UNAVAILABLE", readiness("execution", facts))

    def test_adapter_failure(self) -> None:
        facts = replace(self.facts, adapter_governed=False)
        self.assertIn("UNSUPPORTED_RUNTIME", readiness("execution", facts))

    def test_verification_failure(self) -> None:
        facts = replace(self.facts, verification_satisfied=False)
        self.assertIn("VERIFICATION_MISSING", readiness("completion", facts))

    def test_final_review_missing(self) -> None:
        facts = replace(self.facts, final_review_satisfied=False)
        self.assertIn("FINAL_REVIEW_MISSING", readiness("completion", facts))

    def test_cancel(self) -> None:
        facts = replace(self.facts, cancelled=True)
        self.assertIn("CANCELLED", readiness("spec", facts))

    def test_unknown_stage(self) -> None:
        with self.assertRaises(ValueError):
            readiness("approved-by-model", self.facts)

    def test_scores_not_accepted(self) -> None:
        with self.assertRaises(TypeError):
            VerifiedGateFacts(confidence=0.99)


class DagTests(unittest.TestCase):
    """Check dependency correctness independently of any model."""

    def test_valid(self) -> None:
        self.assertEqual(validate_dag({"b": ["a"], "a": []}), ("a", "b"))

    def test_cycle(self) -> None:
        with self.assertRaisesRegex(ValueError, "INVALID_DAG"):
            validate_dag({"a": ["b"], "b": ["a"]})

    def test_self_cycle(self) -> None:
        with self.assertRaises(ValueError):
            validate_dag({"a": ["a"]})

    def test_unknown(self) -> None:
        with self.assertRaisesRegex(ValueError, "UNKNOWN_DEPENDENCY"):
            validate_dag({"a": ["missing"]})

    def test_empty(self) -> None:
        with self.assertRaisesRegex(ValueError, "EMPTY_PLAN"):
            validate_dag({})


class PromotionTests(unittest.TestCase):
    """Prevent uncertain learning from silently changing active releases."""

    def test_allowed(self) -> None:
        self.assertEqual(promotion_blockers("improved", 0, True, True), ())

    def test_inconclusive(self) -> None:
        self.assertIn(
            "NOT_PROVEN_IMPROVED",
            promotion_blockers("inconclusive", 0, True, True),
        )

    def test_security_regression(self) -> None:
        self.assertIn(
            "HARD_GATE_FAILURE",
            promotion_blockers("improved", 1, True, True),
        )

    def test_approval(self) -> None:
        self.assertIn(
            "APPROVAL_REQUIRED",
            promotion_blockers("improved", 0, False, True),
        )

    def test_parent_conflict(self) -> None:
        self.assertIn(
            "RELEASE_CONFLICT",
            promotion_blockers("improved", 0, True, False),
        )


if __name__ == "__main__":
    unittest.main()
