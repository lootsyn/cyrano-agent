"""Plan and install pinned, project-local developer tools.

No product process invokes this installer. Resolution and native
builds may execute third-party code; use a secret-free development
environment. Every mutating operation requires explicit consent flags.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ToolchainError(ValueError):
    """Reject missing consent, path escapes, or stale approvals."""


def load_recipe(tool: str, root: Path = ROOT) -> dict:
    """Return one manifest-owned recipe.

    Arbitrary packages are never accepted; only registered tools load.

    Raises:
        ToolchainError: ``TOOL_NOT_ADOPTED`` for an unregistered tool.
    """
    recipes = json.loads((root / "tools/manifest.json").read_text())
    entries = recipes["recipes"]
    for recipe in entries:
        if recipe["id"] == tool:
            return recipe
    raise ToolchainError("TOOL_NOT_ADOPTED")


def state_path(tool: str, root: Path = ROOT) -> Path:
    """Return the managed path after rejecting symlinked components.

    Raises:
        ToolchainError: On symlinked components or path escapes.
    """
    load_recipe(tool, root)
    current = root
    if current.is_symlink():
        raise ToolchainError("SYMLINK_ROOT")
    for segment in ("tools", ".state", tool):
        current /= segment
        if current.is_symlink():
            raise ToolchainError("SYMLINK_STATE")
    if not current.resolve().is_relative_to(root.resolve()):
        raise ToolchainError("STATE_ESCAPE")
    return current


def digest(path: Path) -> str:
    """Hash an existing plain file for a lock approval receipt.

    Returns:
        The lowercase hex SHA-256 of the file bytes.

    Raises:
        ToolchainError: ``LOCK_MISSING_OR_LINK`` for missing or linked
            files.
    """
    if path.is_symlink() or not path.is_file():
        raise ToolchainError("LOCK_MISSING_OR_LINK")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lock_path(recipe: dict, state: Path) -> Path:
    """Locate the sole authoritative lock for this recipe kind.

    Returns:
        The lockfile path under ``state``.
    """
    return (
        state
        / {
            "python": "requirements.lock",
            "npm": "package-lock.json",
            "source_uv": "source/uv.lock",
        }[recipe["kind"]]
    )


def commands(recipe: dict, state: Path, operation: str) -> list[list[str]]:
    """Compile fixed subprocess argv; no shell or model-generated flags.

    Returns:
        One argv list per command to run.

    Raises:
        ToolchainError: ``UNKNOWN_OPERATION`` for other operations.
    """
    kind = recipe["kind"]
    if operation == "resolve":
        if kind == "python":
            return [
                [
                    "uv",
                    "pip",
                    "compile",
                    "requirements.in",
                    "--generate-hashes",
                    "--only-binary",
                    ":all:",
                    "--python-version",
                    "3.12",
                    "-o",
                    "requirements.lock",
                ]
            ]
        if kind == "npm":
            return [
                [
                    "npm",
                    "install",
                    "--package-lock-only",
                    "--ignore-scripts",
                    "--no-audit",
                    "--no-fund",
                ]
            ]
        return [
            [
                "git",
                "clone",
                "--no-checkout",
                recipe["repository"],
                "source",
            ],
            [
                "git",
                "-C",
                "source",
                "checkout",
                "--detach",
                recipe["revision"],
            ],
        ]
    if operation == "install":
        if kind == "python":
            python = (
                state
                / ".venv"
                / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            )
            return [
                ["uv", "venv", "--python", "3.12", ".venv"],
                [
                    "uv",
                    "pip",
                    "sync",
                    "--python",
                    str(python),
                    "--require-hashes",
                    "--only-binary",
                    ":all:",
                    "requirements.lock",
                ],
            ]
        if kind == "npm":
            result = ["npm", "ci", "--no-audit", "--no-fund"]
            if not recipe["requires_build_ack"]:
                result.append("--ignore-scripts")
            return [result]
        return [["uv", "sync", "--project", "source", "--frozen", "--no-dev"]]
    raise ToolchainError("UNKNOWN_OPERATION")


def check_approval(recipe: dict, state: Path) -> dict:
    """Reject a changed lock, recipe, or source before install.

    Returns:
        The parsed approval receipt.

    Raises:
        ToolchainError: ``LOCK_CHANGED``, ``RECIPE_CHANGED``, or
            ``SOURCE_CHANGED`` when any bound digest drifted.
    """
    approval = json.loads((state / "lock-approval.json").read_text())
    canonical = json.dumps(recipe, sort_keys=True).encode()
    spec = hashlib.sha256(canonical).hexdigest()
    if approval["lock_sha256"] != digest(lock_path(recipe, state)):
        raise ToolchainError("LOCK_CHANGED")
    if approval["recipe_sha256"] != spec:
        raise ToolchainError("RECIPE_CHANGED")
    if recipe["kind"] == "source_uv":
        head = subprocess.check_output(
            ["git", "-C", str(state / "source"), "rev-parse", "HEAD"],
            text=True,
            timeout=10,
        ).strip()
        dirty = subprocess.check_output(
            ["git", "-C", str(state / "source"), "status", "--porcelain"],
            text=True,
            timeout=10,
        ).strip()
        if head != recipe["revision"] or dirty:
            raise ToolchainError("SOURCE_CHANGED")
    return approval


def managed_env(state: Path) -> dict[str, str]:
    """Return a credential-free environment for managed commands.

    Only an explicit allowlist of variables is inherited; user
    package-manager config and the real HOME are replaced by paths
    inside ``state``.

    Returns:
        A minimal environment mapping; nothing is created on disk.
    """
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        in {
            "PATH",
            "SystemRoot",
            "SYSTEMROOT",
            "COMSPEC",
            "TEMP",
            "TMP",
            "LANG",
            "LC_ALL",
        }
    }
    home = state / "home"
    env.update(
        HOME=str(home),
        USERPROFILE=str(home),
        UV_CACHE_DIR=str(state / "uv-cache"),
        npm_config_cache=str(state / "npm-cache"),
        npm_config_userconfig=str(state / "empty-npmrc"),
        GIT_CONFIG_NOSYSTEM="1",
        GIT_TERMINAL_PROMPT="0",
    )
    return env


def main() -> int:
    """Perform only the requested local preparation operation.

    Returns:
        The process exit code.

    Raises:
        ToolchainError: On missing consent, approval drift, or unsafe
            state.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "operation",
        choices=[
            "plan",
            "resolve",
            "approve-lock",
            "install",
            "doctor",
        ],
    )
    parser.add_argument("--tool", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--allow-build", action="store_true")
    parser.add_argument("--ack-gpl", action="store_true")
    args = parser.parse_args()
    recipe = load_recipe(args.tool)
    state = state_path(args.tool)
    for name in [
        "home",
        "uv-cache",
        "npm-cache",
        "empty-npmrc",
        "lock-approval.json",
        "install-receipt.json",
        "last-failure.json",
        "source",
        "node_modules",
        ".venv",
    ]:
        if (state / name).is_symlink():
            raise ToolchainError("SYMLINK_MANAGED_STATE")
    if args.operation == "doctor":
        receipt = state / "install-receipt.json"
        print(
            json.dumps(
                {
                    "tool": args.tool,
                    "receipt_exists": receipt.is_file(),
                    "runtime_verified": False,
                },
                indent=2,
            )
        )
        return 0 if receipt.is_file() else 2
    if args.operation == "plan":
        print(
            json.dumps(
                {
                    "tool": recipe,
                    "state": str(state),
                    "resolve": commands(recipe, state, "resolve"),
                    "install": commands(recipe, state, "install"),
                    "network_required": True,
                    "license_review_required": args.tool == "serena",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if not args.apply:
        raise ToolchainError("EXPLICIT_APPLY_REQUIRED")
    if args.tool == "serena" and not args.ack_gpl:
        raise ToolchainError("GPL_ACK_REQUIRED")
    if args.operation != "approve-lock" and not args.allow_network:
        raise ToolchainError("NETWORK_CONSENT_REQUIRED")
    if (
        args.operation == "install"
        and recipe["requires_build_ack"]
        and not args.allow_build
    ):
        raise ToolchainError("BUILD_CONSENT_REQUIRED")
    state.mkdir(parents=True, exist_ok=True)
    lock = lock_path(recipe, state)
    if args.operation == "approve-lock":
        receipt = {
            "tool": args.tool,
            "lock_sha256": digest(lock),
            "recipe_sha256": hashlib.sha256(
                json.dumps(recipe, sort_keys=True).encode()
            ).hexdigest(),
            "authority": "explicit_local_developer_not_product_approval",
        }
        approval_path = state / "lock-approval.json"
        approval_path.write_text(json.dumps(receipt, indent=2))
        print(json.dumps(receipt, indent=2))
        return 0
    if args.operation == "resolve":
        if lock.exists() or (state / "source").exists():
            raise ToolchainError("EXISTING_RESOLUTION_USE_NEW_REVIEWED_STATE")
        if recipe["kind"] in {"python", "npm"}:
            name = (
                "requirements.in"
                if recipe["kind"] == "python"
                else "package.json"
            )
            target = state / name
            if target.is_symlink():
                raise ToolchainError("SYMLINK_INPUT")
            shutil.copyfile(ROOT / "tools/recipes" / args.tool / name, target)
    else:
        check_approval(recipe, state)
        if (state / ".venv").exists() and recipe["kind"] == "python":
            raise ToolchainError("EXISTING_ENV_REQUIRES_REVIEW")
    # Deliberately exclude credentials and package-manager user config.
    env = managed_env(state)
    (state / "home").mkdir(exist_ok=True)
    (state / "empty-npmrc").touch(exist_ok=True)
    executed = []
    for argv in commands(recipe, state, args.operation):
        completed = subprocess.run(
            argv,
            cwd=state,
            env=env,
            timeout=900,
            check=False,
        )
        executed.append({"argv": argv, "exit_code": completed.returncode})
        if completed.returncode:
            failure = state / "last-failure.json"
            failure.write_text(json.dumps(executed, indent=2))
            return completed.returncode
    result = {
        "operation": args.operation,
        "tool": args.tool,
        "lock_sha256": digest(lock),
        "commands": executed,
        "runtime_verified": False,
    }
    if args.operation == "install":
        receipt_path = state / "install-receipt.json"
        receipt_path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ToolchainError,
        OSError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ) as error:
        print(f"BLOCKED: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(2) from None
