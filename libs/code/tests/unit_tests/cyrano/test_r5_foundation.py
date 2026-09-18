"""Exercise R5 pure primitives, not native integration."""

from __future__ import annotations

import dataclasses
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from deepagents_code.cyrano.intelligence.contracts import (
    AnalysisError,
    IndexBinding,
    require_read_operation,
    safe_source_path,
)
from deepagents_code.cyrano.memory.playbook import (
    DeltaError,
    EntryDelta,
    PlaybookEntry,
    apply_delta,
)
from deepagents_code.cyrano.monitor.projection import (
    MonitorProjection,
    ProjectionError,
    terminal_text,
)

SCRIPTS = Path(__file__).resolve().parents[3] / "cyrano/scripts"
sys.path.insert(0, str(SCRIPTS))
import toolchain


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.binding = IndexBinding("w", "src", "env", "acl", "provider", "1")

    def test_identical_binding(self):
        self.binding.require_match(self.binding)

    def test_every_binding_field_is_material(self):
        for field in dataclasses.fields(self.binding):
            with self.subTest(field=field.name):
                changed = dataclasses.replace(
                    self.binding, **{field.name: "other"}
                )
                with self.assertRaises(AnalysisError):
                    changed.require_match(self.binding)

    def test_readonly_supported(self):
        require_read_operation("definition", frozenset({"definition"}))

    def test_unknown_or_write_denied(self):
        for operation in [
            "rename",
            "workspace/applyEdit",
            "executeCommand",
            "shell",
        ]:
            with (
                self.subTest(operation=operation),
                self.assertRaises(AnalysisError),
            ):
                require_read_operation(operation, frozenset({operation}))

    def test_unsupported_not_defaulted(self):
        with self.assertRaises(AnalysisError):
            require_read_operation("references", frozenset())

    def test_real_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "한글.py").write_text("x = 1\n")
            self.assertEqual(
                safe_source_path(root, "한글.py"), root / "한글.py"
            )

    def test_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            for path in ["../x", "/x", "a//b", "a/./b", "a\\b", "C:x", ""]:
                with self.subTest(path=path), self.assertRaises(AnalysisError):
                    safe_source_path(Path(tmp), path)

    def test_symlink_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "real.py").write_text("x=1")
            (root / "alias.py").symlink_to(root / "real.py")
            with self.assertRaises(AnalysisError):
                safe_source_path(root, "alias.py")

    def test_missing_file(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            self.assertRaises(AnalysisError),
        ):
            safe_source_path(Path(tmp), "missing")


class DeltaTests(unittest.TestCase):
    def setUp(self):
        self.entry = PlaybookEntry("e1", 1, "w", "verify tests", ("ev1",))
        self.delta = EntryDelta(
            "refine", "e1", 1, "w", "verify db tests", ("ev2",)
        )
        self.kw = dict(
            expected_release="r",
            actual_release="r",
            permitted_scope="w",
            known_evidence=frozenset({"ev1", "ev2"}),
            max_chars=100,
        )

    def apply(self, delta=None, entries=None, **kw):
        return apply_delta(
            (self.entry,) if entries is None else entries,
            delta or self.delta,
            **(self.kw | kw),
        )

    def test_refine_is_candidate_and_immutable(self):
        result = self.apply()
        self.assertEqual(result[0].revision, 2)
        self.assertEqual(result[0].evidence, ("ev1", "ev2"))
        self.assertEqual(self.entry.revision, 1)
        self.assertEqual(self.entry.text, "verify tests")

    def test_add_sorted_identity(self):
        delta = EntryDelta("add", "a", 0, "w", "new rule", ("ev2",))
        self.assertEqual([e.entry_id for e in self.apply(delta)], ["a", "e1"])

    def test_stale_release(self):
        with self.assertRaises(DeltaError):
            self.apply(actual_release="new")

    def test_stale_revision(self):
        with self.assertRaises(DeltaError):
            self.apply(dataclasses.replace(self.delta, expected_revision=3))

    def test_protected_entry(self):
        with self.assertRaises(DeltaError):
            self.apply(
                entries=(dataclasses.replace(self.entry, protected=True),)
            )

    def test_foreign_scope(self):
        with self.assertRaises(DeltaError):
            self.apply(dataclasses.replace(self.delta, scope="foreign"))

    def test_foreign_base_entry(self):
        with self.assertRaises(DeltaError):
            self.apply(
                entries=(dataclasses.replace(self.entry, scope="foreign"),)
            )

    def test_unknown_evidence(self):
        with self.assertRaises(DeltaError):
            self.apply(dataclasses.replace(self.delta, evidence=("missing",)))

    def test_missing_evidence(self):
        with self.assertRaises(DeltaError):
            self.apply(dataclasses.replace(self.delta, evidence=()))

    def test_no_silent_capacity_compaction(self):
        with self.assertRaises(DeltaError):
            self.apply(max_chars=2)
        self.assertEqual(self.entry.text, "verify tests")

    def test_whitespace_counts_capacity(self):
        with self.assertRaises(DeltaError):
            self.apply(dataclasses.replace(self.delta, text=" " * 200 + "x"))

    def test_duplicate_entry_id(self):
        with self.assertRaises(DeltaError):
            self.apply(entries=(self.entry, self.entry))

    def test_duplicate_content(self):
        delta = EntryDelta("add", "e2", 0, "w", self.entry.text, ("ev2",))
        with self.assertRaises(DeltaError):
            self.apply(delta)

    def test_deprecate_preserves_history(self):
        result = self.apply(
            dataclasses.replace(self.delta, operation="deprecate")
        )
        self.assertTrue(result[0].deprecated)
        self.assertEqual(result[0].text, self.entry.text)

    def test_deprecated_cannot_refine(self):
        with self.assertRaises(DeltaError):
            self.apply(
                entries=(dataclasses.replace(self.entry, deprecated=True),)
            )

    def test_unknown_delta(self):
        with self.assertRaises(DeltaError):
            self.apply(
                dataclasses.replace(self.delta, operation="rewrite_all")
            )

    def test_bool_not_revision(self):
        with self.assertRaises(DeltaError):
            self.apply(dataclasses.replace(self.delta, expected_revision=True))


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.view = MonitorProjection("w", "r", "g")

    def event(self, seq=1, kind="phase.changed", **payload):
        return {
            "event_id": f"e{seq}",
            "commit_seq": seq,
            "workspace_id": "w",
            "request_id": "r",
            "generation": "g",
            "event_type": kind,
            "payload": payload,
        }

    def test_exact_duplicate(self):
        event = self.event()
        self.assertTrue(self.view.ingest(event))
        self.assertFalse(self.view.ingest(event))

    def test_conflict_same_id(self):
        self.view.ingest(self.event())
        with self.assertRaises(ProjectionError):
            self.view.ingest(self.event(message="changed"))

    def test_scope_and_generation(self):
        for field in ["workspace_id", "request_id", "generation"]:
            with self.subTest(field=field), self.assertRaises(ProjectionError):
                self.view.ingest(self.event() | {field: "other"})

    def test_bool_sequence(self):
        with self.assertRaises(ProjectionError):
            self.view.ingest(self.event() | {"commit_seq": True})

    def test_nonstring_event_type(self):
        with self.assertRaises(ProjectionError):
            self.view.ingest(self.event() | {"event_type": 1})

    def test_nonfinite_json(self):
        with self.assertRaises(ProjectionError):
            self.view.ingest(self.event(amount=float("nan")))

    def test_late_and_gap_are_allowed(self):
        for seq in [10, 1, 7]:
            self.view.ingest(self.event(seq))
        self.assertEqual(self.view.cursor, 10)
        self.assertEqual(
            [x["commit_seq"] for x in self.view.timeline()], [1, 7, 10]
        )
        self.assertEqual(self.view.summary()["coverage"], "partial_or_unknown")

    def test_same_seq_different_identity(self):
        self.view.ingest(self.event())
        with self.assertRaises(ProjectionError):
            self.view.ingest(self.event() | {"event_id": "different"})

    def test_physical_retry_count(self):
        for i in range(1, 4):
            e = self.event(
                i,
                "model.attempt_started",
                attempt_id=f"a{i}",
                logical_request_id="logical",
                is_retry=i > 1,
            )
            self.view.ingest(e)
            self.view.ingest(e)
        result = self.view.summary()
        self.assertEqual(result["logical_requests_observed"], 1)
        self.assertEqual(result["physical_attempts_observed"], 3)
        self.assertEqual(result["retries_observed"], 2)

    def test_conflicting_attempt_binding(self):
        self.view.ingest(
            self.event(
                1,
                "model.attempt_started",
                attempt_id="a",
                logical_request_id="l",
                is_retry=False,
            )
        )
        self.view.ingest(
            self.event(
                2,
                "model.attempt_started",
                attempt_id="a",
                logical_request_id="other",
                is_retry=True,
            )
        )
        with self.assertRaises(ProjectionError):
            self.view.summary()

    def test_missing_application_evidence_id(self):
        self.view.ingest(self.event(1, "memory.applied"))
        with self.assertRaises(ProjectionError):
            self.view.summary()

    def test_incoming_payload_copied(self):
        event = self.event(message="original")
        self.view.ingest(event)
        event["payload"]["message"] = "edited"
        self.assertEqual(
            self.view.timeline()[0]["payload"]["message"], "original"
        )

    def test_returned_summary_is_not_internal_state(self):
        self.view.ingest(self.event(1, "test.failed", cause="unknown"))
        first = self.view.summary()["first_observed_failure"]
        first["payload"]["cause"] = "invented"
        self.assertEqual(
            self.view.summary()["first_observed_failure"]["payload"]["cause"],
            "unknown",
        )

    def test_cap_requires_snapshot(self):
        self.view.max_events = 1
        self.view.ingest(self.event())
        with self.assertRaises(ProjectionError):
            self.view.ingest(self.event(2))

    def test_terminal_controls_and_cjk(self):
        text = "한글\n[red]text[/red]\x1b]52;clipboard\x07\u202etest"
        safe = terminal_text(text)
        self.assertIn("한글\n[red]", safe)
        self.assertNotIn("\x1b", safe)
        self.assertNotIn("\u202e", safe)

    def test_render_limit(self):
        self.assertEqual(terminal_text("abcdef", 3), "abc")
        with self.assertRaises(ProjectionError):
            terminal_text("a", 0)


class ToolchainTests(unittest.TestCase):
    def test_no_global_python_install(self):
        r = toolchain.load_recipe("graphify")
        argv = toolchain.commands(r, Path("/tmp/local"), "install")
        self.assertIn("--require-hashes", argv[-1])
        self.assertIn("--python", argv[-1])
        self.assertNotIn("--system", str(argv))

    def test_npm_resolve_scripts_disabled(self):
        argv = toolchain.commands(
            toolchain.load_recipe("qmd"), Path("/tmp/local"), "resolve"
        )
        self.assertIn("--ignore-scripts", argv[0])
        self.assertNotIn("-g", argv[0])

    def test_serena_source_is_pinned(self):
        r = toolchain.load_recipe("serena")
        self.assertEqual(len(r["revision"]), 40)
        self.assertIn(
            r["revision"],
            toolchain.commands(r, Path("/tmp/local"), "resolve")[-1],
        )
        self.assertNotIn("latest", r["revision"])

    def test_unknown_tool(self):
        with self.assertRaises(toolchain.ToolchainError):
            toolchain.load_recipe("knip")

    def test_lock_change_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            r = toolchain.load_recipe("ty")
            (root / "requirements.lock").write_text("a")
            (root / "lock-approval.json").write_text(
                json.dumps({"lock_sha256": "wrong", "recipe_sha256": "wrong"})
            )
            with self.assertRaises(toolchain.ToolchainError):
                toolchain.check_approval(r, root)

    def test_state_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tools").mkdir()
            (root / "tools/manifest.json").write_text(
                json.dumps({"recipes": [{"id": "qmd"}]})
            )
            (root / "outside").mkdir()
            (root / "tools/.state").symlink_to(root / "outside")
            with self.assertRaises(toolchain.ToolchainError):
                toolchain.state_path("qmd", root)

    def test_apply_required_before_subprocess(self):
        with (
            patch.object(
                sys, "argv", ["toolchain", "resolve", "--tool", "qmd"]
            ),
            patch.object(toolchain.subprocess, "run") as run,
        ):
            with self.assertRaises(toolchain.ToolchainError):
                toolchain.main()
            run.assert_not_called()

    def test_network_ack_required(self):
        with (
            patch.object(
                sys,
                "argv",
                ["toolchain", "resolve", "--tool", "qmd", "--apply"],
            ),
            patch.object(toolchain.subprocess, "run") as run,
        ):
            with self.assertRaises(toolchain.ToolchainError):
                toolchain.main()
            run.assert_not_called()

    def test_build_ack_required(self):
        with (
            patch.object(
                sys,
                "argv",
                [
                    "toolchain",
                    "install",
                    "--tool",
                    "qmd",
                    "--apply",
                    "--allow-network",
                ],
            ),
            patch.object(toolchain.subprocess, "run") as run,
        ):
            with self.assertRaises(toolchain.ToolchainError):
                toolchain.main()
            run.assert_not_called()

    def test_gpl_ack_required(self):
        with (
            patch.object(
                sys,
                "argv",
                [
                    "toolchain",
                    "resolve",
                    "--tool",
                    "serena",
                    "--apply",
                    "--allow-network",
                ],
            ),
            patch.object(toolchain.subprocess, "run") as run,
        ):
            with self.assertRaises(toolchain.ToolchainError):
                toolchain.main()
            run.assert_not_called()
