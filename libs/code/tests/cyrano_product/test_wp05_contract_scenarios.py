"""WP05 contract scenarios: tail stability, limits, bounded output."""

import pytest

from deepagents_code.cyrano.context.compiler import (
    Block,
    bounded_tool_result,
    compile_context,
)
from deepagents_code.cyrano.context.usage import (
    measured_cache_ratio,
    normalize_usage,
)
from deepagents_code.cyrano.contracts.canonical import raw_digest
from deepagents_code.cyrano.contracts.types import CyranoError


def test_con_ctx_01_dynamic_tail_change_keeps_prefix():
    """CON-CTX-01: changed tail leaves the stable digest intact."""
    blocks = [Block("policy", 0, "p"), Block("role", 1, "r")]
    first = compile_context(blocks, {"observation": "v1"})
    second = compile_context(blocks, {"observation": "v2"})
    assert first.stable_digest == second.stable_digest
    assert first.dynamic_text != second.dynamic_text


def test_con_ctx_07_no_tokenizer_reports_unknown():
    """CON-CTX-07: without a tokenizer the limit is explicit unknown."""
    with pytest.raises(CyranoError) as exc:
        compile_context(
            [Block("a", 0, "x")],
            {},
            require_token_gate=True,
            token_limit=None,
        )
    assert exc.value.code == "CONTEXT_LIMIT_UNKNOWN"
    compiled = compile_context([Block("a", 0, "x")], {})
    assert compiled.stable_bytes > 0


def test_uh_cache_08_bounded_tool_result():
    """UH-CACHE-08: oversized stdout -> excerpt + digest + ref."""
    data = b"x" * 4096
    result = bounded_tool_result(data, cap=64)
    assert result["truncated"] is True
    assert result["excerpt"] == data[:64]
    assert result["digest"] == raw_digest(data)
    assert result["artifact_ref"] == raw_digest(data)
    small = bounded_tool_result(b"tiny", cap=64)
    assert small["truncated"] is False
    assert small["artifact_ref"] is None


def test_con_cac_09_missing_counters_are_null():
    """CON-CAC-09: omitted counters stay null; ratio unresolved."""
    report = normalize_usage({"input_tokens": 50})
    assert report.cache_read is None
    assert report.cache_write is None
    assert measured_cache_ratio(report) is None
