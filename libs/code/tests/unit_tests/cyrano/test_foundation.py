"""Behavior tests for shipped foundation code, never live model."""

import math
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from deepagents_code.cyrano.context.compiler import (
    Block,
    cache_read_ratio,
    compile_context,
)
from deepagents_code.cyrano.contracts.canonical import (
    canonical_bytes,
    digest,
    raw_digest,
)
from deepagents_code.cyrano.contracts.types import CyranoError, Outcome, Scope
from deepagents_code.cyrano.dcode.adapter import (
    REQUIRED,
    require_governed,
    runtime_status,
)
from deepagents_code.cyrano.evaluation.gates import (
    Evaluation,
    decision,
    validate_splits,
)
from deepagents_code.cyrano.events.coverage import Coverage
from deepagents_code.cyrano.improvement.classification import classify
from deepagents_code.cyrano.improvement.replay import (
    RecordedTransition,
    Replay,
)
from deepagents_code.cyrano.interview.readiness import (
    Obligation,
    affected_closure,
    assess,
)
from deepagents_code.cyrano.kernel.transitions import transition
from deepagents_code.cyrano.memory.selection import Memory, select_memories
from deepagents_code.cyrano.plugins.registry import Registry
from deepagents_code.cyrano.sqlite.store import EventStore
from deepagents_code.cyrano.workflow.plan import WorkUnit, order_plan


class CanonicalTests(unittest.TestCase):
    def test_key_order(self):
        self.assertEqual(digest({"b": 2, "a": 1}), digest({"a": 1, "b": 2}))

    def test_array_order_preserved(self):
        self.assertNotEqual(digest([1, 2]), digest([2, 1]))

    def test_unicode_normalized_for_artifact(self):
        self.assertEqual(digest("e\u0301"), digest("é"))

    def test_raw_bytes_are_not_normalized(self):
        self.assertNotEqual(raw_digest(b"a\r\n"), raw_digest(b"a\n"))

    def test_reject_float(self):
        with self.assertRaises(CyranoError):
            canonical_bytes({"x": 0.1})

    def test_reject_nan(self):
        with self.assertRaises(CyranoError):
            canonical_bytes(math.nan)

    def test_reject_key_collision(self):
        with self.assertRaises(CyranoError):
            canonical_bytes({"é": 1, "e\u0301": 2})

    def test_reject_nonstring_key(self):
        with self.assertRaises(CyranoError):
            canonical_bytes({1: "value"})

    def test_reject_integer_overflow(self):
        with self.assertRaises(CyranoError):
            canonical_bytes(2**53)

    def test_reject_surrogate(self):
        with self.assertRaises(CyranoError):
            canonical_bytes("\ud800")

    def test_bool_not_integer(self):
        self.assertEqual(canonical_bytes(True), b"true")


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.blocks = [
            Block("role", 20, "review"),
            Block("constitution", 10, "verify"),
        ]

    def test_deterministic_order(self):
        first = compile_context(self.blocks, {"task": 1})
        second = compile_context(list(reversed(self.blocks)), {"task": 1})
        self.assertEqual(first, second)

    def test_dynamic_tail_preserves_static_prefix(self):
        first = compile_context(self.blocks, {"task": 1})
        second = compile_context(self.blocks, {"task": 2})
        self.assertEqual(first.stable_digest, second.stable_digest)
        self.assertNotEqual(first.request_digest, second.request_digest)

    def test_role_change_invalidates_prefix(self):
        first = compile_context(self.blocks, {})
        second = compile_context([Block("role", 20, "implement")], {})
        self.assertNotEqual(first.stable_digest, second.stable_digest)

    def test_exact_bytes_hash(self):
        result = compile_context(self.blocks, {})
        self.assertEqual(
            result.stable_digest, raw_digest(result.stable_text.encode())
        )

    def test_duplicate_block(self):
        with self.assertRaises(CyranoError):
            compile_context(self.blocks * 2, {})

    def test_unsafe_block_id(self):
        with self.assertRaises(CyranoError):
            compile_context([Block("bad>id", 1, "x")], {})

    def test_no_silent_budget_truncation(self):
        with self.assertRaises(CyranoError):
            compile_context(self.blocks, {}, max_bytes=1)

    def test_cache_hit_not_claimed(self):
        self.assertFalse(compile_context(self.blocks, {}).wire_observed)

    def test_missing_usage_is_unknown(self):
        self.assertIsNone(cache_read_ratio(100, None))

    def test_zero_input_is_not_hit(self):
        self.assertIsNone(cache_read_ratio(0, 0))

    def test_usage_semantics(self):
        self.assertEqual(
            cache_read_ratio(100, 50, inclusive_semantics=True), 0.5
        )
        self.assertIsNone(cache_read_ratio(100, 50))
        with self.assertRaises(CyranoError):
            cache_read_ratio(100, 101, inclusive_semantics=True)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "state.sqlite3"
        self.store = EventStore(self.path)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_retry_is_idempotent(self):
        self.assertEqual(self.store.append("s", 0, "k", {"x": 1}), 1)
        self.assertEqual(self.store.append("s", 0, "k", {"x": 1}), 1)
        self.assertEqual(len(self.store.events("s")), 1)

    def test_key_payload_conflict(self):
        self.store.append("s", 0, "k", {"x": 1})
        with self.assertRaises(CyranoError):
            self.store.append("s", 0, "k", {"x": 2})

    def test_key_revision_conflict(self):
        self.store.append("s", 0, "k", {"x": 1})
        with self.assertRaises(CyranoError):
            self.store.append("s", 1, "k", {"x": 1})

    def test_cas_rejects_stale_writer(self):
        self.store.append("s", 0, "a", {"x": 1})
        with self.assertRaises(CyranoError):
            self.store.append("s", 0, "b", {"x": 2})
        self.assertEqual(self.store.events("s"), [{"x": 1}])

    def test_reopen_persists_events(self):
        self.store.append("s", 0, "a", {"x": 1})
        self.store.close()
        self.store = EventStore(self.path)
        self.assertEqual(self.store.events("s"), [{"x": 1}])

    def test_same_key_separate_streams(self):
        self.store.append("s1", 0, "k", {"x": 1})
        self.store.append("s2", 0, "k", {"x": 2})
        self.assertEqual(self.store.events("s1"), [{"x": 1}])

    def test_rollback_cannot_leave_job(self):
        with self.assertRaises(CyranoError):
            self.store.append("s", 9, "k", {"x": 1}, enqueue=True)
        self.assertIsNone(self.store.claim("w", 10, 5))
        self.assertEqual(self.store.events("s"), [])

    def test_outbox_dedupe(self):
        self.store.append("s", 0, "k", {"x": 1}, enqueue=True)
        self.store.append("s", 0, "k", {"x": 1}, enqueue=True)
        first = self.store.claim("w", 10, 5)
        self.assertIsNotNone(first)
        self.assertIsNone(self.store.claim("w2", 11, 5))

    def test_old_fence_rejected(self):
        self.store.append("s", 0, "k", {}, enqueue=True)
        key, fence = self.store.claim("one", 10, 5)
        next_key, next_fence = self.store.claim("two", 16, 5)
        self.assertEqual(key, next_key)
        self.assertGreater(next_fence, fence)
        with self.assertRaises(CyranoError):
            self.store.finish(key, "one", fence, 17)
        self.store.finish(key, "two", next_fence, 17)
        self.assertIsNone(self.store.claim("three", 100, 5))

    def test_expired_worker_cannot_finish(self):
        self.store.append("s", 0, "k", {}, enqueue=True)
        key, fence = self.store.claim("one", 10, 5)
        with self.assertRaises(CyranoError):
            self.store.finish(key, "one", fence, 15)

    def test_invalid_lease(self):
        with self.assertRaises(CyranoError):
            self.store.claim("one", 10, 0)


class InterviewTests(unittest.TestCase):
    def ready(self, obligations, **changes):
        args = dict(
            target_stage="planning",
            required_review_current=True,
            important_assumptions=0,
            stale_evidence=0,
            unresolved_conflicts=0,
        )
        args.update(changes)
        return assess(obligations, **args)

    def test_critical_obligation_blocks(self):
        self.assertFalse(
            self.ready([Obligation("error-policy", True, False)]).ready
        )

    def test_zero_questions_possible(self):
        self.assertTrue(self.ready([]).ready)

    def test_planning_not_execution(self):
        self.assertFalse(self.ready([]).execution_authorized)

    def test_required_reviewer_failure(self):
        self.assertFalse(self.ready([], required_review_current=False).ready)

    def test_important_assumption_blocks(self):
        self.assertFalse(self.ready([], important_assumptions=1).ready)

    def test_stale_evidence_blocks(self):
        self.assertFalse(self.ready([], stale_evidence=1).ready)

    def test_conflict_blocks(self):
        self.assertFalse(self.ready([], unresolved_conflicts=1).ready)

    def test_critical_deferral_cannot_hide_duty(self):
        item = Obligation("delete", True, False, "planning", True)
        self.assertFalse(self.ready([item]).ready)

    def test_explicit_noncritical_deferral(self):
        item = Obligation("log-wording", False, False, "planning", True)
        self.assertTrue(self.ready([item]).ready)

    def test_invalidation_closure(self):
        graph = {
            "scenario": {"decision"},
            "review": {"scenario"},
            "approval": {"review"},
        }
        self.assertEqual(
            affected_closure({"decision"}, graph),
            {"decision", "scenario", "review", "approval"},
        )

    def test_invalidation_cycles_terminate(self):
        self.assertEqual(
            affected_closure({"a"}, {"a": {"b"}, "b": {"a"}}), {"a", "b"}
        )


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.scope = Scope("t", "u", "w")
        self.now = datetime(2026, 9, 16, tzinfo=timezone.utc)

    def memory(self, **changes):
        values = dict(
            memory_id="m",
            scope=self.scope,
            status="active",
            valid_until=self.now + timedelta(days=1),
            required_digests=("d",),
            evidence_refs=("e",),
            content_ref="blob:m",
            rank=1,
        )
        values.update(changes)
        return Memory(**values)

    def select(self, *records):
        return select_memories(
            list(records), self.scope, self.now, frozenset({"d"})
        )

    def test_select_verified_memory(self):
        self.assertEqual(len(self.select(self.memory())), 1)

    def test_cross_workspace_not_visible(self):
        self.assertEqual(
            self.select(self.memory(scope=Scope("t", "u", "other"))), []
        )

    def test_candidate_not_active(self):
        self.assertEqual(self.select(self.memory(status="candidate")), [])

    def test_expired_not_active(self):
        self.assertEqual(self.select(self.memory(valid_until=self.now)), [])

    def test_digest_change_stales_memory(self):
        self.assertEqual(
            self.select(self.memory(required_digests=("new",))), []
        )

    def test_unbacked_memory_excluded(self):
        self.assertEqual(self.select(self.memory(evidence_refs=())), [])

    def test_stable_tie_break(self):
        result = self.select(
            self.memory(memory_id="z"), self.memory(memory_id="a")
        )
        self.assertEqual([item.memory_id for item in result], ["a", "z"])

    def test_reject_wildcard_scope(self):
        with self.assertRaises(CyranoError):
            Scope("t", "u", "*")

    def test_naive_time_rejected(self):
        with self.assertRaises(CyranoError):
            self.select(self.memory(valid_until=datetime(2026, 10, 1)))


class ImprovementTests(unittest.TestCase):
    def impact(self, paths, **kw):
        args = dict(input_semantics_unchanged=False, policy_ir_validated=False)
        args.update(kw)
        return classify(paths, **args)

    def test_skill_change_uses_b(self):
        self.assertEqual(self.impact(["skills/test/SKILL.md"]).path, "B")

    def test_memory_change_uses_b(self):
        self.assertEqual(self.impact(["memory/one.json"]).path, "B")

    def test_interview_change_uses_b(self):
        self.assertEqual(self.impact(["workflow/interview.json"]).path, "B")

    def test_input_attestation_not_name(self):
        self.assertEqual(
            self.impact(["policies/exploration/a.json"]).path, "B"
        )

    def test_valid_a_still_needs_actual_evaluation(self):
        result = self.impact(
            ["policies/exploration/a.json"],
            input_semantics_unchanged=True,
            policy_ir_validated=True,
        )
        self.assertEqual(result.path, "A")
        self.assertTrue(result.requires_live)

    def test_protected_change(self):
        self.assertEqual(
            self.impact(["evaluation/sealed/secret.json"]).effect_class,
            "protected_change",
        )

    def test_mixed_change_goes_b(self):
        result = self.impact(
            ["policies/exploration/a.json", "memory/one.json"],
            input_semantics_unchanged=True,
            policy_ir_validated=True,
        )
        self.assertEqual(result.path, "B")

    def test_noop_rejected(self):
        with self.assertRaises(CyranoError):
            self.impact([])

    def test_path_traversal_rejected(self):
        with self.assertRaises(CyranoError):
            self.impact(["skills/../../policies/permissions/p.json"])

    def test_promotion_needs_evidence(self):
        with self.assertRaises(CyranoError):
            transition("await_approval", "promoted")

    def test_cannot_skip_review(self):
        with self.assertRaises(CyranoError):
            transition("evaluated", "promoted", evidence_ready=True)

    def test_approved_transition(self):
        self.assertEqual(
            transition("await_approval", "promoted", evidence_ready=True),
            "promoted",
        )


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.replay = Replay(
            [
                RecordedTransition("a", "da", frozenset(), "failed"),
                RecordedTransition("b", "db", frozenset({"a"}), "passed"),
                RecordedTransition("c", "dc", frozenset(), "partial"),
            ]
        )

    def test_initial_future_hidden(self):
        self.assertEqual(self.replay.view(), {})

    def test_supported_transition(self):
        self.assertEqual(
            self.replay.step({"a": "da"}, frozenset({"a"}), worker_cap=1),
            "supported",
        )
        self.assertEqual(self.replay.view(), {"a": "failed"})

    def test_future_change_does_not_change_current_view(self):
        other = Replay(
            [RecordedTransition("a", "da", frozenset(), "different-future")]
        )
        self.assertEqual(self.replay.view(), other.view())

    def test_dependency_cannot_be_skipped(self):
        self.assertEqual(
            self.replay.step({"b": "db"}, frozenset({"b"}), worker_cap=1),
            "out_of_support",
        )
        self.assertEqual(self.replay.view(), {})

    def test_no_partial_batch_reveal(self):
        result = self.replay.step(
            {"a": "da", "missing": "x"},
            frozenset({"a", "missing"}),
            worker_cap=2,
        )
        self.assertEqual(result, "out_of_support")
        self.assertEqual(self.replay.view(), {})

    def test_input_change_unsupported(self):
        self.assertEqual(
            self.replay.step({"a": "changed"}, frozenset({"a"}), worker_cap=1),
            "out_of_support",
        )

    def test_parent_child_cannot_share_batch(self):
        self.assertEqual(
            self.replay.step(
                {"a": "da", "b": "db"}, frozenset({"a", "b"}), worker_cap=2
            ),
            "out_of_support",
        )

    def test_illegal_action_rejected(self):
        with self.assertRaises(CyranoError):
            self.replay.step({"a": "da"}, frozenset(), worker_cap=1)

    def test_worker_cap_enforced(self):
        with self.assertRaises(CyranoError):
            self.replay.step(
                {"a": "da", "c": "dc"}, frozenset({"a", "c"}), worker_cap=1
            )

    def test_sequential_dependency(self):
        self.replay.step({"a": "da"}, frozenset({"a"}), worker_cap=1)
        self.replay.step({"b": "db"}, frozenset({"b"}), worker_cap=1)
        self.assertEqual(self.replay.view(), {"a": "failed", "b": "passed"})

    def test_public_view_copy(self):
        view = self.replay.view()
        view["a"] = "injected"
        self.assertEqual(self.replay.view(), {})


class EvaluationTests(unittest.TestCase):
    def result(self, **changes):
        values = dict(
            path="B",
            actual_pairs=60,
            planned_pairs=60,
            safety_failures=0,
            quality_delta_lower=0.01,
            cost_delta_upper=-0.05,
            quality_margin=0.01,
            minimum_saving=0.02,
            evidence_valid=True,
        )
        values.update(changes)
        return Evaluation(**values)

    def test_b_cannot_promote_replay_only(self):
        self.assertEqual(decision(self.result(actual_pairs=0)), "inconclusive")

    def test_a_also_needs_live_pairs(self):
        self.assertEqual(
            decision(self.result(path="A", actual_pairs=0)), "inconclusive"
        )

    def test_safe_improvement_only_eligible_for_review(self):
        self.assertEqual(decision(self.result()), "eligible_for_review")

    def test_safety_failure_dominates_cost_savings(self):
        self.assertEqual(
            decision(self.result(safety_failures=1, cost_delta_upper=-0.9)),
            "rejected",
        )

    def test_invalid_evidence(self):
        self.assertEqual(
            decision(self.result(evidence_valid=False)), "invalid"
        )

    def test_missing_metric_unknown(self):
        self.assertEqual(
            decision(self.result(cost_delta_upper=None)), "inconclusive"
        )

    def test_quality_uncertainty_blocks(self):
        self.assertEqual(
            decision(self.result(quality_delta_lower=-0.1)), "inconclusive"
        )

    def test_not_enough_savings(self):
        self.assertEqual(
            decision(self.result(cost_delta_upper=0)), "inconclusive"
        )

    def test_nan_rejected(self):
        with self.assertRaises(CyranoError):
            decision(self.result(cost_delta_upper=math.nan))

    def test_same_family_split_rejected(self):
        with self.assertRaises(CyranoError):
            validate_splits({"dev": {"f1"}, "holdout": {"f1"}})

    def test_disjoint_families(self):
        validate_splits({"dev": {"f1"}, "holdout": {"f2"}})


class LifecycleTests(unittest.TestCase):
    def test_failed_registration_rolls_back(self):
        class Bad:
            def setup(self, register):
                register("x", 1)
                raise RuntimeError("setup failed")

        registry = Registry()
        with self.assertRaises(RuntimeError):
            registry.load("bad", Bad())
        self.assertEqual(registry.services, {})

    def test_duplicate_service_preserves_original(self):
        class P:
            def setup(self, register):
                register("x", 1)
                return lambda: None

        registry = Registry()
        registry.load("a", P())
        with self.assertRaises(CyranoError):
            registry.load("b", P())
        self.assertEqual(registry.services, {"x": 1})
        registry.close()

    def test_teardown_reverse_order(self):
        output = []

        class P:
            def __init__(self, name):
                self.name = name

            def setup(self, register):
                register(self.name, 1)
                return lambda: output.append(self.name)

        registry = Registry()
        registry.load("a", P("a"))
        registry.load("b", P("b"))
        registry.close()
        registry.close()
        self.assertEqual(output, ["b", "a"])
        self.assertEqual(registry.services, {})

    def test_disposal_error_does_not_skip_other_plugins(self):
        output = []

        class P:
            def setup(self, register):
                return lambda: output.append("cleaned")

        class Bad:
            def setup(self, register):
                def dispose():
                    raise RuntimeError("disposal failed")

                return dispose

        registry = Registry()
        registry.load("a", P())
        registry.load("b", Bad())
        with self.assertRaises(ExceptionGroup):
            registry.close()
        self.assertEqual(output, ["cleaned"])


class RuntimeAndPlanTests(unittest.TestCase):
    def test_missing_runtime_probe_blocks_governed(self):
        with self.assertRaises(CyranoError):
            require_governed({})

    def test_not_tested_probe_is_not_verified(self):
        report = {key: "verified" for key in REQUIRED}
        report["sandbox_isolation"] = "not_tested"
        with self.assertRaises(CyranoError):
            require_governed(report)

    def test_pure_probe_helper(self):
        require_governed({key: "verified" for key in REQUIRED})
        self.assertFalse(runtime_status()["governed_available"])

    def test_process_exit_not_task_success(self):
        self.assertFalse(Outcome("finished", "unknown", "unknown").complete)
        self.assertTrue(Outcome("finished", "passed", "accepted").complete)

    def test_empty_coverage_not_full_coverage(self):
        self.assertFalse(Coverage(frozenset(), frozenset()).complete)

    def test_observability_gap(self):
        report = Coverage(frozenset({"model", "child"}), frozenset({"model"}))
        self.assertEqual(report.gaps, frozenset({"child"}))

    def unit(self, name, deps=()):
        return WorkUnit(name, deps, ("REQ",), ("ACC",), ("src/a.py",))

    def test_plan_order(self):
        self.assertEqual(
            order_plan([self.unit("b", ("a",)), self.unit("a")]), ("a", "b")
        )

    def test_plan_cycle(self):
        with self.assertRaises(CyranoError):
            order_plan([self.unit("b", ("a",)), self.unit("a", ("b",))])

    def test_plan_missing_dependency(self):
        with self.assertRaises(CyranoError):
            order_plan([self.unit("b", ("missing",))])

    def test_plan_missing_acceptance(self):
        with self.assertRaises(CyranoError):
            order_plan([WorkUnit("a", (), ("R",), (), ())])


if __name__ == "__main__":
    unittest.main()
