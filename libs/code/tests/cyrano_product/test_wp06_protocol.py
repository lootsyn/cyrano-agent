"""WP06 protocol tests: fragment assembly, call ids, orphan/stale results."""

import json

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.dcode.normalization import ProtocolNormalizer


def test_con_mod_01():
    """A malformed request never reaches dispatch."""
    n = ProtocolNormalizer()
    with pytest.raises(CyranoError) as exc:
        n.feed("c1", "read_file", b"not-json{", final=True)
    assert exc.value.code == "INCOMPLETE_TOOL_CALL"


def test_con_mod_02():
    """Fragmented args only dispatch when the final fragment parses."""
    n = ProtocolNormalizer()
    assert n.feed("c1", "read", b'{"path":', final=False) is None
    with pytest.raises(CyranoError) as exc:
        n.finalize()  # c1 never got a final fragment
    assert exc.value.code == "INCOMPLETE_TOOL_CALL"


def test_con_mod_03():
    """UTF-8 multi-byte characters split across fragments reassemble."""
    n = ProtocolNormalizer()
    payload = json.dumps({"text": "한국어 🎉"}).encode()
    cut = len(payload) // 2
    assert n.feed("c1", "write", payload[:cut], final=False) is None
    call = n.feed("c1", "write", payload[cut:], final=True)
    assert call is not None
    assert call.arguments["text"] == "한국어 🎉"


def test_con_mod_04():
    """Reusing a call id for a different tool is a collision."""
    n = ProtocolNormalizer()
    n.feed("c1", "read", b"{}", final=False)
    with pytest.raises(CyranoError) as exc:
        n.feed("c1", "write", b"{}", final=False)
    assert exc.value.code == "CALL_ID_COLLISION"


def test_con_mod_05():
    """Same tool name with distinct ids yields independent calls."""
    n = ProtocolNormalizer()
    a = n.feed("c1", "read", b'{"p": 1}', final=True)
    b = n.feed("c2", "read", b'{"p": 2}', final=True)
    assert a is not None and b is not None
    assert a.call_id != b.call_id
    assert a.arguments != b.arguments


def test_con_mod_06():
    """A result for an unknown call is recorded, never dispatched."""
    n = ProtocolNormalizer()
    with pytest.raises(CyranoError) as exc:
        n.record_result("ghost", {"out": 1})
    assert exc.value.code == "INPUT_INVALID"
    assert n.orphan_results == [("ghost", {"out": 1})]


def test_con_mod_07():
    """A completed call without a result gets observation_missing."""
    n = ProtocolNormalizer()
    n.feed("c1", "read", b"{}", final=True)
    n.finalize()
    synthetic = dict(n.synthetic_results)
    assert synthetic["c1"]["status"] == "observation_missing"


def test_con_mod_08():
    """Signed reasoning never exports as text across providers."""
    n = ProtocolNormalizer()
    n.feed("c1", "think", b'{"reasoning": "opaque-blob"}', final=True)
    history = n.export_history()
    assert history == [{"call_id": "c1", "name": "think"}]
    assert "reasoning" not in json.dumps(history)


def test_con_mod_09():
    """A required image part on a text-only runtime is unavailable."""
    n = ProtocolNormalizer()
    with pytest.raises(CyranoError) as exc:
        n.require_content("image")
    assert exc.value.code == "CAPABILITY_UNAVAILABLE"
    n.require_content("text")


def test_con_mod_10():
    """Argument bytes and open-call count are hard-limited."""
    n = ProtocolNormalizer(max_args_bytes=8)
    with pytest.raises(CyranoError) as exc:
        n.feed("c1", "write", b'{"big": "overflow"}', final=False)
    assert exc.value.code == "TOOL_ARGUMENT_LIMIT"
    limited = ProtocolNormalizer(max_calls=1)
    limited.feed("a", "t", b"", final=False)
    with pytest.raises(CyranoError) as exc2:
        limited.feed("b", "t", b"", final=False)
    assert exc2.value.code == "TOOL_ARGUMENT_LIMIT"


def test_con_mod_11():
    """A call has exactly one retry owner; a second claim conflicts."""
    n = ProtocolNormalizer()
    n.feed("c1", "read", b"{}", final=True)
    n.claim_retry("c1", "broker")
    n.claim_retry("c1", "broker")  # same owner: idempotent
    with pytest.raises(CyranoError) as exc:
        n.claim_retry("c1", "sdk-loop")
    assert exc.value.code == "CONFLICT"


def test_con_mod_12():
    """Cancellation records usage; a late result is stale."""
    n = ProtocolNormalizer()
    n.feed("c1", "write", b"{}", final=True)
    n.cancel("c1")
    n.record_usage("c1", {"input": 10, "output": 5})
    assert n.record_result("c1", {"ok": True}) == "stale"
    slot_calls = n.finalize()
    assert all(c.call_id for c in slot_calls)
