"""Exercise document selection, not provider prompt caching."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "cyrano"
sys.path.insert(0, str(ROOT / "scripts"))
from doc_route import RouteError, select_readset  # noqa: E402


class DocumentRouteTests(unittest.TestCase):
    """Keep unstable or untrusted content out of default readsets."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "docs").mkdir()
        (self.root / ".agents").mkdir()
        self.documents = [
            ("AGENTS.md", "development", "Standing instructions.\n"),
            ("docs/task.md", "design", "One task only.\n"),
        ]
        self.publish()

    def publish(self, task_paths=None):
        rows = []
        for path, category, text in self.documents:
            file = self.root / path
            file.write_text(text)
            rows.append(
                {
                    "path": path,
                    "category": category,
                    "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                }
            )
        (self.root / "docs/document-catalog.json").write_text(
            json.dumps({"documents": rows})
        )
        (self.root / ".agents/document-routing.json").write_text(
            json.dumps(
                {
                    "always": ["AGENTS.md"],
                    "tasks": {"RC00": task_paths or ["docs/task.md"]},
                }
            )
        )

    def test_repeat_read_has_identical_manifest(self):
        self.assertEqual(
            select_readset(self.root, "RC00"),
            select_readset(self.root, "RC00"),
        )

    def test_repeat_does_not_claim_cache_hit(self):
        result, _ = select_readset(self.root, "RC00")
        self.assertEqual(result["provider_cache_hit"], "not_measured")
        self.assertIsNone(result["token_count"])

    def test_duplicate_path_included_once(self):
        self.publish(["AGENTS.md", "docs/task.md", "docs/task.md"])
        result, _ = select_readset(self.root, "RC00")
        self.assertEqual(len(result["documents"]), 2)

    def test_changed_unindexed_document_is_rejected(self):
        (self.root / "docs/task.md").write_text("changed")
        with self.assertRaisesRegex(RouteError, "STALE_DOCUMENT_CATALOG"):
            select_readset(self.root, "RC00")

    def test_updated_document_changes_digest(self):
        before, _ = select_readset(self.root, "RC00")
        self.documents[1] = ("docs/task.md", "design", "Reviewed change.\n")
        self.publish()
        after, _ = select_readset(self.root, "RC00")
        self.assertNotEqual(before["readset_digest"], after["readset_digest"])

    def test_reference_requires_explicit_permission(self):
        self.documents[1] = ("docs/task.md", "reference", "Historical note.\n")
        self.publish()
        with self.assertRaisesRegex(RouteError, "REFERENCE_CONSENT"):
            select_readset(self.root, "RC00")
        result, _ = select_readset(self.root, "RC00", allow_reference=True)
        self.assertEqual(len(result["documents"]), 2)

    def test_generated_reference_is_still_forbidden(self):
        self.documents[1] = ("docs/task.md", "generated", "Aggregate.\n")
        self.publish()
        with self.assertRaisesRegex(RouteError, "NONCANONICAL"):
            select_readset(self.root, "RC00", allow_reference=True)

    def test_unregistered_path_is_rejected(self):
        self.publish(["docs/missing.md"])
        with self.assertRaisesRegex(RouteError, "UNREGISTERED"):
            select_readset(self.root, "RC00")

    def test_unknown_task_is_rejected(self):
        with self.assertRaisesRegex(RouteError, "UNKNOWN_TASK"):
            select_readset(self.root, "ALL")

    def test_byte_budget_is_enforced(self):
        with self.assertRaisesRegex(RouteError, "READSET_TOO_LARGE"):
            select_readset(self.root, "RC00", max_bytes=1)

    def test_nonpositive_budget_is_rejected(self):
        with self.assertRaisesRegex(RouteError, "INVALID_READSET_BUDGET"):
            select_readset(self.root, "RC00", max_bytes=0)

    def test_symlink_source_is_rejected(self):
        path = self.root / "docs/task.md"
        path.unlink()
        path.symlink_to(self.root / "AGENTS.md")
        with self.assertRaisesRegex(RouteError, "DOCUMENT_SYMLINK"):
            select_readset(self.root, "RC00")

    def test_missing_source_is_rejected(self):
        (self.root / "docs/task.md").unlink()
        with self.assertRaisesRegex(RouteError, "DOCUMENT_MISSING"):
            select_readset(self.root, "RC00")

    def test_traversal_is_rejected_even_when_registered(self):
        catalog = self.root / "docs/document-catalog.json"
        value = json.loads(catalog.read_text())
        value["documents"][1]["path"] = "../outside.md"
        catalog.write_text(json.dumps(value))
        route = self.root / ".agents/document-routing.json"
        value = json.loads(route.read_text())
        value["tasks"]["RC00"] = ["../outside.md"]
        route.write_text(json.dumps(value))
        with self.assertRaisesRegex(RouteError, "UNSAFE_DOCUMENT_PATH"):
            select_readset(self.root, "RC00")

    def test_selected_document_order_is_stable(self):
        _, bodies = select_readset(self.root, "RC00")
        self.assertEqual([p for p, _ in bodies], ["AGENTS.md", "docs/task.md"])
