"""Test documentation tooling, not native runtime authorization."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "cyrano"
sys.path.insert(0, str(ROOT / "scripts"))
from build_catalog import generate as catalog_generate
from build_routes import build, generate
from case_route import select
from check_integrated import fixture_report, pair_coverage
from doc_route import (
    RouteError,
    select_readset,
)


class AutomaticRegistrationTests(unittest.TestCase):
    """Derive routes from task metadata, never editing the router."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for path in (
            ".agents/work",
            "docs/design",
            "docs/testing",
            "docs/development",
        ):
            (self.root / path).mkdir(parents=True, exist_ok=True)
        for name in (
            "AGENTS.md",
            "docs/NAVIGATION.ko.md",
            "docs/design/a.md",
            "docs/testing/STRATEGY.ko.md",
            ".agents/work/WP00.ko.md",
        ):
            (self.root / name).write_text("# " + name + "\n")
        self.work = {
            "work_packages": [
                {
                    "id": "WP00",
                    "depends_on": [],
                    "document": ".agents/work/WP00.ko.md",
                    "primary_design": "docs/design/a.md",
                    "resource_refs": [],
                }
            ]
        }
        for file, key in (
            ("test-work-plan.json", "tasks"),
            ("r4-work-plan.json", "refinements"),
            ("r5-work-plan.json", "refinements"),
        ):
            (self.root / "docs/development" / file).write_text(
                json.dumps({key: []})
            )
        self.publish()

    def publish(self):
        (self.root / ".agents/work/plan.json").write_text(
            json.dumps(self.work)
        )

    def test_task_automatically_registered(self):
        self.assertEqual(set(generate(self.root)["tasks"]), {"WP00"})

    def test_new_task_requires_no_router_edit(self):
        new = copy.deepcopy(self.work["work_packages"][0])
        new.update(id="WP01", document=".agents/work/WP01.ko.md")
        (self.root / new["document"]).write_text("# Another task\n")
        self.work["work_packages"].append(new)
        self.publish()
        self.assertEqual(set(generate(self.root)["tasks"]), {"WP00", "WP01"})

    def test_changed_design_is_selected(self):
        (self.root / "docs/design/b.md").write_text("# New design\n")
        self.work["work_packages"][0]["primary_design"] = "docs/design/b.md"
        self.publish()
        self.assertIn("docs/design/b.md", build(self.root)["tasks"]["WP00"])

    def test_duplicate_identity_rejected(self):
        self.work["work_packages"].append(self.work["work_packages"][0])
        self.publish()
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            build(self.root)

    def test_missing_dependency_rejected(self):
        self.work["work_packages"][0]["depends_on"] = ["WP77"]
        self.publish()
        with self.assertRaisesRegex(ValueError, "UNKNOWN_WORK_DEPENDENCY"):
            build(self.root)

    def test_cycle_rejected(self):
        self.work["work_packages"][0]["depends_on"] = ["WP00"]
        self.publish()
        with self.assertRaises(ValueError):
            build(self.root)

    def test_missing_file_does_not_publish_partial_router(self):
        before = generate(self.root)
        self.work["work_packages"][0]["primary_design"] = "docs/missing.md"
        self.publish()
        with self.assertRaises(RouteError):
            generate(self.root)
        actual = json.loads(
            (self.root / ".agents/document-routing.json").read_text()
        )
        self.assertEqual(actual, before)

    def test_reference_not_default(self):
        self.work["work_packages"][0]["primary_design"] = "references/input.md"
        self.publish()
        with self.assertRaisesRegex(ValueError, "UNSAFE_DEFAULT_DOCUMENT"):
            build(self.root)

    def test_generated_not_default(self):
        self.work["work_packages"][0]["primary_design"] = (
            "docs/generated/all.md"
        )
        self.publish()
        with self.assertRaisesRegex(ValueError, "UNSAFE_DEFAULT_DOCUMENT"):
            build(self.root)

    def test_symlink_design_rejected(self):
        path = self.root / "docs/design/a.md"
        path.unlink()
        path.symlink_to(self.root / "AGENTS.md")
        with self.assertRaisesRegex(RouteError, "SYMLINK"):
            build(self.root)

    def test_stage_specific_reading(self):
        catalog_generate(self.root)
        _, plan = select_readset(self.root, "WP00", stage="plan")
        _, tests = select_readset(self.root, "WP00", stage="test")
        self.assertIn("docs/design/a.md", [x[0] for x in plan])
        self.assertNotIn("docs/design/a.md", [x[0] for x in tests])
        self.assertIn("docs/testing/STRATEGY.ko.md", [x[0] for x in tests])

    def test_unrelated_document_does_not_churn_readset(self):
        catalog_generate(self.root)
        before, _ = select_readset(self.root, "WP00")
        (self.root / "docs/design/unrelated.md").write_text("# Not selected\n")
        catalog_generate(self.root)
        after, _ = select_readset(self.root, "WP00")
        self.assertEqual(before["readset_digest"], after["readset_digest"])

    def test_selected_source_changes_digest(self):
        catalog_generate(self.root)
        before, _ = select_readset(self.root, "WP00")
        (self.root / "docs/design/a.md").write_text("# Changed semantics\n")
        catalog_generate(self.root)
        after, _ = select_readset(self.root, "WP00")
        self.assertNotEqual(before["readset_digest"], after["readset_digest"])

    def test_resources_are_not_loaded(self):
        (self.root / "docs/resource.json").write_text(
            '{"secret": "not-a-real-secret"}'
        )
        self.work["work_packages"][0]["resource_refs"] = ["docs/resource.json"]
        self.publish()
        catalog_generate(self.root)
        manifest, bodies = select_readset(self.root, "WP00")
        self.assertEqual(
            manifest["resource_paths_not_loaded"], ["docs/resource.json"]
        )
        self.assertNotIn(
            "not-a-real-secret", "".join(body for _, body in bodies)
        )

    def test_unknown_stage_rejected(self):
        catalog_generate(self.root)
        with self.assertRaisesRegex(RouteError, "UNKNOWN_STAGE"):
            select_readset(self.root, "WP00", stage="everything")


class IntegratedSpecificationTests(unittest.TestCase):
    """Keep contract and case claims separate from product evidence."""

    def load(self, name):
        return json.loads((ROOT / name).read_text())

    def test_fixture_expectations(self):
        result = fixture_report(ROOT)
        self.assertEqual(result["failures"], [])
        self.assertGreaterEqual(result["executed"], 50)

    def test_workflow_has_no_embedded_authorization_receipt(self):
        props = self.load("contracts/v2/runtime.schema.json")["$defs"][
            "WorkflowIR"
        ]["properties"]
        self.assertNotIn("execution_permit_ref", props)

    def test_subject_omits_progress_and_signature(self):
        props = self.load("contracts/v2/planning.schema.json")["$defs"][
            "PlanReviewSubject"
        ]["properties"]
        self.assertFalse(
            {"progress", "signature", "approval_ref"} & set(props)
        )

    def test_pair_matrix_recomputed(self):
        result = pair_coverage(
            self.load("tests/assessment/interaction-matrix.json")
        )
        self.assertEqual(result["missing"], [])
        self.assertGreater(result["required"], 100)

    def test_incomplete_matrix_is_not_full_coverage(self):
        data = self.load("tests/assessment/interaction-matrix.json")
        data["rows"] = data["rows"][:1]
        self.assertTrue(pair_coverage(data)["missing"])

    def test_unknown_factor_rejected(self):
        data = self.load("tests/assessment/interaction-matrix.json")
        data["rows"][0]["permission"] = "magic-approval"
        with self.assertRaisesRegex(ValueError, "UNKNOWN_FACTOR_VALUE"):
            pair_coverage(data)

    def test_case_route_is_owned(self):
        cases = select(ROOT, "WP09")
        self.assertTrue(cases)
        self.assertTrue(all(c["owner_wp"] == "WP09" for c in cases))

    def test_unknown_case_rejected(self):
        with self.assertRaisesRegex(ValueError, "NO_MATCHING"):
            select(ROOT, "WP09", "NONEXISTENT")

    def test_cross_owner_case_rejected(self):
        with self.assertRaisesRegex(ValueError, "NO_MATCHING"):
            select(ROOT, "WP09", "ISOLATE-012")

    def test_unassessed_score_not_fabricated(self):
        score = self.load("evidence/product-scorecard.json")
        self.assertIn(
            score["status"], {"not_evaluated", "computed_from_wp_evidence"}
        )
        self.assertIsNone(score["official_score"])

    def test_attachment_has_section_specific_owners(self):
        rows = self.load("contracts/integration/request-coverage.json")[
            "sections"
        ]
        self.assertEqual(len(rows), 44)
        self.assertNotEqual(
            rows[7]["document_owners"], rows[12]["document_owners"]
        )

    def test_no_runtime_history_archive_required(self):
        self.assertFalse((ROOT / "references/archive").exists())
        self.assertTrue((ROOT / "references/universal-harness").exists())

    def test_generated_routes_are_current(self):
        self.assertEqual(
            self.load(".agents/document-routing.json"), build(ROOT)
        )
