"""WP06 product tests: verified runtime, sentinel matrix, launch isolation."""

import asyncio
import json
from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.dcode.adapter import AttemptRequest, runtime_status
from deepagents_code.cyrano.dcode.bridge import (
    AttemptBridge,
    apply_override,
    map_virtual_path,
    start_verified_runtime,
)
from deepagents_code.cyrano.dcode.capabilities import CapabilityService
from deepagents_code.cyrano.dcode.middleware import (
    build_launch_view,
    check_path,
    map_role,
    mediation_matrix,
    verify_extension_sentinel,
)

ALL_PROBES = {
    k: "verified"
    for k in (
        "extension_loading",
        "async_middleware",
        "child_observation",
        "tool_mediation",
        "sandbox_isolation",
        "trusted_approval",
        "context_manifest",
        "cancel_recovery",
    )
}


def _request() -> AttemptRequest:
    return AttemptRequest(
        attempt_id="a1",
        input_snapshot="sha256:in",
        context_digest="sha256:ctx",
        permit_ref="permit-1",
        runtime_lock_digest="lock-1",
    )


def test_dcode_setup():
    """Dispatch is blocked until every required probe verifies."""
    with pytest.raises(CyranoError) as exc:
        start_verified_runtime({"extension_loading": "missing"}, "l")
    assert exc.value.code == "DCODE_RUNTIME_NOT_VERIFIED"
    handle = start_verified_runtime(ALL_PROBES, "lock-1")
    bridge = AttemptBridge(handle)

    async def handler(req: AttemptRequest) -> str:
        return "artifact:1"

    receipt = asyncio.run(
        bridge.execute_attempt(_request(), handler)
    )
    assert receipt.result_ref == "artifact:1"
    unverified = AttemptBridge.__new__(AttemptBridge)
    unverified._handle = type(handle)(
        verified=False,
        runtime_lock_digest="x",
        probe_report={},
    )
    unverified._guard = None
    unverified._budget = None
    unverified._events = []
    with pytest.raises(CyranoError) as exc2:
        asyncio.run(
            unverified.execute_attempt(_request(), handler)
        )
    assert exc2.value.code == "DCODE_RUNTIME_NOT_VERIFIED"


def test_dcode_child():
    """A child attempt may only narrow the parent's granted scope."""
    handle = start_verified_runtime(ALL_PROBES, "lock-1")
    bridge = AttemptBridge(handle)
    parent = frozenset({"src/**", "tests/**"})

    async def handler(req: AttemptRequest) -> str:
        return "ok"

    ok = asyncio.run(
        bridge.execute_child(
            _request(), handler, parent, frozenset({"src/**"})
        )
    )
    assert ok.result_ref == "ok"
    with pytest.raises(CyranoError) as exc:
        asyncio.run(
            bridge.execute_child(
                _request(), handler, parent, frozenset({"etc/**"})
            )
        )
    assert exc.value.code == "SCOPE_DENIED"


def test_dcode_virtual():
    """Virtual paths never auto-map to host paths."""
    assert map_virtual_path("/virtual/workspace/a.py") is None
    mapped = map_virtual_path(
        "/virtual/workspace/a.py",
        {"/virtual/workspace/a.py": "/host/approved/a.py"},
    )
    assert mapped == "/host/approved/a.py"
    assert map_virtual_path("/virtual/b.py", {}) is None


def test_dcode_override():
    """Overrides require a verified allowlist; plausible names fail."""
    with pytest.raises(CyranoError):
        apply_override(
            "hooks.on_save", frozenset({"hooks.on_save"}),
            allowlist_verified=False,
        )
    with pytest.raises(CyranoError):
        apply_override(
            "hooks.evil", frozenset({"hooks.on_save"}),
            allowlist_verified=True,
        )
    assert (
        apply_override(
            "hooks.on_save", frozenset({"hooks.on_save"}),
            allowlist_verified=True,
        )
        == "hooks.on_save"
    )


def test_uh_run_09():
    """Child tasks inherit the same guard; an unguarded path fails."""
    calls: list[str] = []

    def guard(path: str) -> bool:
        calls.append(path)
        return path != "child"  # parent forgot to permit children

    for path in ("native", "extension", "mcp"):
        assert check_path(path, guard) == path
    with pytest.raises(CyranoError) as exc:
        check_path("child", guard)
    assert exc.value.code == "SCOPE_DENIED"
    assert calls == ["native", "extension", "mcp", "child"]


def test_uh_cache_10():
    """Model ids are telemetry; capability resolution never branches."""
    caps = CapabilityService(
        {"tool_mediation": True}, model_id="any-model-x"
    )
    assert caps.resolve("tool_mediation") == "verified"
    caps_other = CapabilityService(
        {"tool_mediation": True}, model_id="different-model-y"
    )
    assert caps_other.resolve("tool_mediation") == "verified"
    assert caps.resolve("cancel_recovery") == "unknown"


def test_uh_ops_03():
    """A disabled extension sentinel aborts governed launch."""
    with pytest.raises(CyranoError) as exc:
        verify_extension_sentinel(False)
    assert exc.value.code == "CAPABILITY_UNAVAILABLE"
    verify_extension_sentinel(True)


def test_integ_native_load(tmp_path: Path):
    """Project trust configs are excluded; the source is untouched."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x = 1\n")
    evil = tmp_path / "mcp.json"
    evil.write_text('{"mcpServers": {"evil": {"command": "curl"}}}')
    before = evil.read_bytes()
    view = build_launch_view(tmp_path, tmp_path / "view")
    assert "mcp.json" in view.excluded
    assert not (view.view_root / "mcp.json").exists()
    assert (view.view_root / "src" / "main.py").exists()
    assert evil.read_bytes() == before  # original untouched
    manifest = json.dumps(sorted(view.excluded))
    assert view.manifest_digest.startswith("sha256:")


def test_integ_role_mapping():
    """Only explicit versioned role mappings grant authority."""
    assert map_role("planner", version="v1") == "plan"
    with pytest.raises(CyranoError) as exc:
        map_role("Planner", version="v1")  # no string normalization
    assert exc.value.code == "UNKNOWN_ROLE"
    with pytest.raises(CyranoError):
        map_role("admin", version="v1")
    with pytest.raises(CyranoError):
        map_role("planner", version="v99")


def test_sentinel_matrix_covers_all_paths():
    """Every sentinel path is mediated; an unknown path is denied."""
    seen: list[str] = []
    matrix = mediation_matrix(lambda p: seen.append(p) or True)
    assert set(matrix) == {
        "native", "extension", "mcp", "child",
        "compaction", "retry", "remember",
    }
    with pytest.raises(CyranoError):
        check_path("shell_escape", lambda p: True)


def test_runtime_status_stays_honest():
    """The public status never claims a live integration."""
    status = runtime_status()
    assert status["governed_available"] is False
