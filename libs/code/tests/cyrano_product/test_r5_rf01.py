"""RF01 cases: project-local tool resolution, locks, isolation."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

CODE_ROOT = Path(__file__).resolve().parents[2]
CYRANO_ROOT = CODE_ROOT / "cyrano"
TOOLCHAIN = CYRANO_ROOT / "scripts" / "toolchain.py"

sys.path.insert(0, str(CYRANO_ROOT / "scripts"))
import toolchain  # noqa: E402


def _run(*args: str, cwd: Path = CODE_ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-B", str(TOOLCHAIN), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )


def _tmp_root(tmp_path: Path) -> Path:
    """Copy manifest and recipes; no test state in the dev tree."""
    root = tmp_path / "cyrano"
    (root / "tools" / "recipes").mkdir(parents=True)
    (root / "tools" / "manifest.json").write_text(
        (CYRANO_ROOT / "tools" / "manifest.json").read_text("utf-8"),
        encoding="utf-8",
    )
    for recipe in (CYRANO_ROOT / "tools" / "recipes").iterdir():
        if recipe.is_dir():
            target = root / "tools" / "recipes" / recipe.name
            target.mkdir()
            for item in recipe.iterdir():
                (target / item.name).write_bytes(item.read_bytes())
    return root


def test_rf01_01_plan_is_read_only(tmp_path):
    """R5-RF01-01: plan prints argv; no dirs, installs, or network."""
    root = _tmp_root(tmp_path)
    result = _run("plan", "--tool", "qmd")
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["network_required"] is True
    assert any(argv[0] == "npm" for argv in plan["install"])
    assert not (root / "tools" / ".state").exists()
    assert not (CYRANO_ROOT / "tools" / ".state").exists()


def test_rf01_02_changed_lock_rejected(tmp_path):
    """R5-RF01-02: a lock change after approval blocks install."""
    root = _tmp_root(tmp_path)
    state = root / "tools" / ".state" / "ty"
    state.mkdir(parents=True)
    lock = state / "requirements.lock"
    lock.write_bytes(b"ruff==0.9.0\n")
    approval = {
        "tool": "ty",
        "lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
        "recipe_sha256": hashlib.sha256(
            json.dumps(
                toolchain.load_recipe("ty", root),
                sort_keys=True,
            ).encode()
        ).hexdigest(),
    }
    (state / "lock-approval.json").write_text(json.dumps(approval))
    lock.write_bytes(b"ruff==0.9.0 \n")
    with pytest.raises(toolchain.ToolchainError, match="LOCK_CHANGED"):
        toolchain.check_approval(toolchain.load_recipe("ty", root), state)


def test_rf01_03_build_needs_explicit_consent():
    """R5-RF01-03: build-ack recipes refuse silent installs."""
    result = _run("install", "--tool", "qmd", "--apply", "--allow-network")
    assert result.returncode == 2
    assert "BUILD_CONSENT_REQUIRED" in result.stderr
    assert not (CYRANO_ROOT / "tools" / ".state" / "qmd").exists()


def test_rf01_04_gpl_tool_needs_license_ack():
    """R5-RF01-04: Serena (GPL) is refused without an explicit ack."""
    result = _run(
        "resolve",
        "--tool",
        "serena",
        "--apply",
        "--allow-network",
        "--allow-build",
    )
    assert result.returncode == 2
    assert "GPL_ACK_REQUIRED" in result.stderr


def test_rf01_05_partial_install_never_reports_verified(tmp_path):
    """R5-RF01-05: install absence keeps runtime_verified false."""
    root = _tmp_root(tmp_path)
    recipe = toolchain.load_recipe("ty", root)
    state = toolchain.state_path("ty", root)
    result = _run("doctor", "--tool", "ty")
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report["receipt_exists"] is False
    assert report["runtime_verified"] is False
    assert recipe["id"] == "ty"
    assert not state.exists()


def test_rf01_06_managed_env_strips_credentials(monkeypatch, tmp_path):
    """R5-RF01-06: managed installs see no HOME secrets."""
    state = tmp_path / "state"
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("NPM_CONFIG_USERCONFIG", "/real/home/.npmrc")
    env = toolchain.managed_env(state)
    assert "OPENAI_API_KEY" not in env
    assert "NPM_CONFIG_USERCONFIG" not in env
    assert env["HOME"] == str(state / "home")
    assert env["npm_config_userconfig"] == str(state / "empty-npmrc")
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert not state.exists()  # pure: construction creates nothing
