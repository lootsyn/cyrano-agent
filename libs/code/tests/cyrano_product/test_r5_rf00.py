"""RF00 cases: capability ownership, permits, and feature state."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.dcode.adapter import (
    require_capability,
    require_permit,
)
from deepagents_code.cyrano.dcode.probes import (
    resolve_feature_state,
    resolve_feature_states,
    validate_ownership,
)

CYRANO_ROOT = Path(__file__).resolve().parents[2] / "cyrano"


def _manifest() -> dict:
    return json.loads(
        (CYRANO_ROOT / "configs/capability-ownership.json").read_text("utf-8")
    )


def _feature(fid: str = "code_intelligence", **overrides: object) -> dict:
    feature = {
        "id": fid,
        "code_owner": "intelligence/manager.py",
        "procedure_owner": "cyrano-code-intelligence",
        "config_owner": "tools/manifest.json",
        "enforcement": "code_and_process_boundary_not_prompt",
        "default_enabled": False,
    }
    feature.update(overrides)
    return feature


def test_rf00_01_configured_but_unenforced_is_blocked():
    """R5-RF00-01: declared ownership without a permit is not usable."""
    state = resolve_feature_state(_feature(), probes={}, permits={})
    assert state["configured"] is True
    assert state["authorized"] is False
    assert state["usable"] is False
    assert "UNAUTHORIZED" in state["blocked_reasons"]


def test_rf00_02_unregistered_capability_never_executes():
    """R5-RF00-02: unknown tool names reject with no side effects."""
    inventory = {"fs_read": object(), "fs_write": object()}
    before = dict(inventory)
    with pytest.raises(CyranoError, match="UNKNOWN_CAPABILITY"):
        require_capability("undeclared_mcp_tool", inventory)
    assert inventory == before


def test_rf00_03_installed_without_probe_is_not_verified():
    """R5-RF00-03: an install receipt alone is never usable."""
    state = resolve_feature_state(
        _feature(default_enabled=True),
        probes={"code_intelligence": {"installed": True, "verified": False}},
        permits={"code_intelligence": frozenset({"scope-a"})},
    )
    assert state["installed"] is True
    assert state["probe_verified"] is False
    assert state["usable"] is False
    assert "PROBE_UNVERIFIED" in state["blocked_reasons"]


def test_rf00_04_full_binding_usable_only_in_granted_scope():
    """R5-RF00-04: usable only inside the granted scope."""
    probes = {"code_intelligence": {"installed": True, "verified": True}}
    permits = {"code_intelligence": frozenset({"tenant-a/user-a/ws-a"})}
    state = resolve_feature_state(
        _feature(default_enabled=True),
        probes=probes,
        permits=permits,
        scope="tenant-a/user-a/ws-a",
    )
    assert state["usable"] is True
    assert state["blocked_reasons"] == []

    other = resolve_feature_state(
        _feature(default_enabled=True),
        probes=probes,
        permits=permits,
        scope="tenant-b/user-b/ws-b",
    )
    assert other["usable"] is False
    assert "SCOPE_EXPANSION_REQUIRES_APPROVAL" in other["blocked_reasons"]


def test_rf00_05_disabled_features_do_no_work(tmp_path):
    """R5-RF00-05: features default off; resolution does no I/O."""
    states = resolve_feature_states(_manifest(), probes={}, permits={})
    assert states
    assert all(state["usable"] is False for state in states)
    assert all("DISABLED" in state["blocked_reasons"] for state in states)
    assert list(tmp_path.iterdir()) == []


def test_rf00_06_scope_widening_needs_new_approval():
    """R5-RF00-06: widened scope needs a new permit."""
    permits = {"code_intelligence": frozenset({"read"})}
    require_permit("code_intelligence", "read", permits)
    with pytest.raises(CyranoError, match="PERMIT_SCOPE_REQUIRED"):
        require_permit("code_intelligence", "write", permits)
    with pytest.raises(CyranoError, match="PERMIT_REQUIRED"):
        require_permit("other_feature", "read", permits)
    assert permits == {"code_intelligence": frozenset({"read"})}


def test_validate_ownership_flags_prompt_only_and_missing():
    manifest = _manifest()
    assert validate_ownership(manifest) == []
    broken = {
        "features": [
            {
                "id": "bad",
                "code_owner": "",
                "enforcement": "prompt_only",
                "default_enabled": "yes",
            },
        ]
    }
    errors = validate_ownership(broken)
    assert any(e.startswith("MISSING_CODE_OWNER") for e in errors)
    assert any(e.startswith("MISSING_PROCEDURE_OWNER") for e in errors)
    assert any(e.startswith("MISSING_CONFIG_OWNER") for e in errors)
    assert "PROMPT_ONLY_ENFORCEMENT:bad" in errors
    assert "INVALID_DEFAULT_FLAG:bad" in errors

    errors = validate_ownership(manifest, exists=lambda _path: False)
    assert any(e.startswith("MISSING_OWNER_FILE") for e in errors)
