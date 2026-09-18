"""WP23 harness regression: ``_extract_note`` banner contamination.

Study 3's improvement note opened with a bare thread UUID — the
``App:`` banner wraps its trailing ``Thread:`` value onto the next
line, and the extractor kept that continuation as note content.
These cases pin the corrected extraction against the observed
stdout shape; historical note artifacts stay untouched.
"""

import importlib
import sys
from pathlib import Path

CODE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE / "cyrano" / "scripts"))
live = importlib.import_module("run_live_study")

STDOUT_OBSERVED = (
    "Running task non-interactively...\n"
    # The banner wraps: the thread UUID lands on the next line.
    "App: v0.1.70 | Agent: wp23r3 | Model: m | Thread: \n"
    "01a0b313-4fd3-7c30-82b0-b0c5c8aaf23e\n"
    "Starting LangGraph server...\n"
    "✓ Server ready\n"
    "🔧 Calling tool: ls\n"
    "# Widget module & metadata convention (widgetbox)\n"
    "\n"
    "**Module contract.** Every widget module lives at widgetbox/<m>.py.\n"
    "🔧 Calling tool: write_file\n"
    "Usage Stats: ...\n"
)


def test_wrapped_thread_uuid_is_not_note_content():
    note = live._extract_note(STDOUT_OBSERVED)
    assert "01a0b313" not in note
    assert note.startswith("# Widget module")
    assert "widgetbox/<m>.py" in note


def test_unwrapped_banner_keeps_all_content():
    stdout = (
        "Running task non-interactively...\n"
        "App: v0.1.70 | Agent: a | Model: m "
        "| Thread: 5d063a1e-1a2b-4c3d-8e4f-a1b2c3d4e5f6\n"
        "Starting LangGraph server...\n"
        "✓ Server ready\n"
        "# note line one\n"
        "second line\n"
        "Usage Stats: ...\n"
    )
    note = live._extract_note(stdout)
    assert note.startswith("# note line one")
    assert "second line" in note


def test_uuid_inside_note_body_survives():
    # Only a bare-UUID line directly after the App banner is noise;
    # a UUID inside real content is preserved.
    stdout = (
        "App: v0.1.70 | Agent: a | Model: m | Thread: \n"
        "01a0b313-4fd3-7c30-82b0-b0c5c8aaf23e\n"
        "release id 01a0b313-4fd3-7c30-82b0-b0c5c8aaf23e approved\n"
    )
    note = live._extract_note(stdout)
    assert note == (
        "release id 01a0b313-4fd3-7c30-82b0-b0c5c8aaf23e approved"
    )
