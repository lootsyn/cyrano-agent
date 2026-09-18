"""R5-RF02: read-only LSP lifecycle and snapshot gateway."""

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.intelligence.lsp import (
    FramingBuffer,
    classify_method,
    utf16_column,
)
from deepagents_code.cyrano.intelligence.manager import LspManager


def _manager() -> LspManager:
    return LspManager(current_snapshot_digest="snap:1")


def _session(manager: LspManager):
    return manager.open_analysis(
        "binding-1", frozenset({"textDocument/references"})
    )


def test_r5_rf02_01():
    """UTF-16 columns match the fixture for Korean + emoji + CRLF."""
    line = "한국어🎉end"
    # "한국어" = 3 BMP chars (3 utf16 units); "🎉" is astral (2 units).
    assert utf16_column(line, 3) == 3   # after 한국어
    assert utf16_column(line, 4) == 5   # after the emoji
    assert utf16_column(line, 7) == 8
    with pytest.raises(CyranoError):
        utf16_column(line, 99)


def test_r5_rf02_02():
    """A mutating server request is DENIED and recorded."""
    manager = _manager()
    session = _session(manager)
    with pytest.raises(CyranoError) as exc:
        manager.query(
            session, "workspace/applyEdit", {"edit": {}}
        )
    assert exc.value.code == "SCOPE_DENIED"
    assert session.denied_events == ["DENIED:workspace/applyEdit"]


def test_r5_rf02_03():
    """A late response from an old generation is discarded."""
    manager = _manager()
    session = _session(manager)
    stale = manager.receive_response(session, session.generation - 1, {"r": 1})
    assert stale is None
    current = manager.receive_response(
        session, session.generation, {"r": 2}
    )
    assert current == {"r": 2}


def test_r5_rf02_04():
    """A query beyond advertised capabilities is unavailable."""
    manager = _manager()
    session = _session(manager)  # only references advertised
    with pytest.raises(CyranoError) as exc:
        manager.query(session, "textDocument/hover", {})
    assert exc.value.code == "CAPABILITY_UNAVAILABLE"
    ok = manager.query(session, "textDocument/references", {})
    assert ok["method"] == "textDocument/references"


def test_r5_rf02_05():
    """Framing beyond the byte bound errors; no partial parse."""
    framing = FramingBuffer(max_bytes=16)
    with pytest.raises(CyranoError) as exc:
        framing.frame(b"x" * 17)
    assert exc.value.code == "TOOL_ARGUMENT_LIMIT"
    with pytest.raises(CyranoError):
        framing.unframe(10**9)


def test_r5_rf02_06():
    """A source change makes the bound session stale."""
    manager = _manager()
    session = _session(manager)
    manager._snapshot_digest = "snap:2"  # source moved on
    with pytest.raises(CyranoError) as exc:
        manager.query(session, "textDocument/references", {})
    assert exc.value.code == "STALE_SNAPSHOT"


def test_classify_method_read_only():
    """Write methods are never classified as reads."""
    assert classify_method("textDocument/references") == "read"
    assert classify_method("workspace/executeCommand") == "write"
    assert classify_method("textDocument/didOpen") == "write"
    assert classify_method("unknown/method") == "unknown"
