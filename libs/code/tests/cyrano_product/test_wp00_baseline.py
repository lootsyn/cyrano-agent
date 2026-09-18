"""WP00 baseline: inventory, protected files, error-code hygiene."""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.dcode.package_build import (
    OWNED_ROOTS,
    PROTECTED,
    enumerate_owned_delta,
    resolve_native_checkout,
    verify_installed,
)

CODE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = CODE_ROOT.parents[1]


def test_owned_delta_inventory_is_stable_and_nonempty():
    first = enumerate_owned_delta(CODE_ROOT)
    second = enumerate_owned_delta(CODE_ROOT)
    assert first == second
    assert first.digest == second.digest
    paths = {path for path, _ in first.entries}
    for owned in OWNED_ROOTS:
        root = CODE_ROOT / owned
        if root.exists():
            assert any(
                path == owned or path.startswith(owned + "/") for path in paths
            )
    assert any(path.startswith("deepagents_code/cyrano/") for path in paths)
    assert all(
        re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
        for _, digest in first.entries
    )


def test_protected_native_files_unchanged_by_inventory():
    preimage = {rel: f"sha256:{_sha(CODE_ROOT / rel)}" for rel in PROTECTED}
    before = {rel: (CODE_ROOT / rel).read_bytes() for rel in PROTECTED}
    enumerate_owned_delta(CODE_ROOT)
    report = verify_installed(CODE_ROOT, preimage)
    assert report["protected_unchanged"] is True
    assert report["violations"] == []
    expected_origin = CODE_ROOT / "deepagents_code" / "cyrano"
    assert report["cyrano_origin"] == str(expected_origin)
    for rel, content in before.items():
        assert (CODE_ROOT / rel).read_bytes() == content


def _sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_resolve_native_checkout_binds_real_root():
    checkout = resolve_native_checkout(CODE_ROOT)
    assert checkout.root == str(CODE_ROOT.resolve())
    assert checkout.package_dir.endswith("deepagents_code")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if head.returncode == 0:
        assert checkout.head == head.stdout.strip()


def test_resolve_native_checkout_rejects_payload_dir(tmp_path):
    (tmp_path / "deepagents_code").mkdir()
    with pytest.raises(CyranoError, match="NOT_DCODE_CODE_ROOT"):
        resolve_native_checkout(tmp_path)


def _error_codes(source: Path) -> set[str]:
    codes: set[str] = set()
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CyranoError"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            codes.add(node.args[0].value)
    return codes


WP00_MODULES = {
    "deepagents_code/cyrano/dcode/adapter.py",
    "deepagents_code/cyrano/dcode/probes.py",
    "deepagents_code/cyrano/dcode/package_build.py",
    "deepagents_code/cyrano/context/document_route.py",
    "deepagents_code/cyrano/context/doc_audit.py",
}


def test_new_error_codes_do_not_collide_with_existing_modules():
    """New error IDs must not reuse a code for another meaning."""
    package = CODE_ROOT / "deepagents_code" / "cyrano"
    new_codes: set[str] = set()
    for relative in WP00_MODULES:
        new_codes |= _error_codes(package.parent.parent / relative)
    collisions = []
    for source in sorted(package.rglob("*.py")):
        relative = source.relative_to(CODE_ROOT).as_posix()
        if relative in WP00_MODULES:
            continue
        collisions.extend(
            f"{code}:{relative}" for code in _error_codes(source) & new_codes
        )
    assert collisions == []


def test_inventory_refuses_symlinked_owned_path(tmp_path):
    package = tmp_path / "deepagents_code"
    package.mkdir()
    (tmp_path / "pyproject.toml").write_text('name = "deepagents-code"\n')
    (tmp_path / "cyrano").symlink_to(
        tmp_path / "elsewhere",
        target_is_directory=True,
    )
    with pytest.raises(CyranoError, match="SYMLINK_OWNED_PATH"):
        enumerate_owned_delta(tmp_path)
