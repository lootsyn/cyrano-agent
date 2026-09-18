"""RC00 product cases: additive copy, parent import, wheel resources."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.dcode.package_build import (
    PROTECTED,
    apply_copy,
    build_wheel,
    check_wheel_resources,
    plan_copy,
    verify_installed,
)

CODE_ROOT = Path(__file__).resolve().parents[2]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fake_code_root(root: Path) -> dict[str, str]:
    """Build a real dcode-shaped checkout and return its preimage."""
    (root / "deepagents_code").mkdir(parents=True)
    (root / "deepagents_code" / "__init__.py").write_text(
        "__version__ = '0.0.0'\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        'name = "deepagents-code"\n',
        encoding="utf-8",
    )
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    return {rel: f"sha256:{_sha(root / rel)}" for rel in PROTECTED}


def _payload(root: Path) -> Path:
    payload = root / "payload"
    (payload / "deepagents_code" / "cyrano").mkdir(parents=True)
    (payload / "deepagents_code" / "cyrano" / "__init__.py").write_text(
        '"""Cyrano package."""\n',
        encoding="utf-8",
    )
    (payload / "deepagents_code" / "cyrano" / "marker.py").write_text(
        "MARKER = 1\n",
        encoding="utf-8",
    )
    (payload / "cyrano").mkdir(parents=True)
    (payload / "cyrano" / "README.md").write_text(
        "# dev resources\n",
        encoding="utf-8",
    )
    return payload


def test_rc00_01_copy_preserves_native_files_and_places_origin(tmp_path):
    """R4-RC00-01: protected bytes stay; cyrano origin under root."""
    code_root = tmp_path / "code"
    code_root.mkdir()
    preimage = _fake_code_root(code_root)
    payload = _payload(tmp_path)

    plan = plan_copy(payload, code_root)
    assert {entry.action for entry in plan} == {"create"}
    written = apply_copy(plan)
    assert written == len(plan)

    report = verify_installed(code_root, preimage)
    assert report["protected_unchanged"] is True
    expected = code_root / "deepagents_code" / "cyrano"
    assert report["cyrano_origin"] == str(expected)
    origin = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; sys.path.insert(0, sys.argv[1]);"
                "import deepagents_code.cyrano as c; print(c.__file__)"
            ),
            str(code_root),
        ],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert origin.returncode == 0, origin.stderr
    assert Path(origin.stdout.strip()).resolve().is_relative_to(code_root)


def test_rc00_02_real_parent_import_in_fresh_process():
    """R4-RC00-02: import via the real parent, no lazy-init bypass."""
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            (
                "import deepagents_code;"
                "import deepagents_code.cyrano as c;"
                "print(deepagents_code.__version__);"
                "print(c.__file__)"
            ),
        ],
        cwd=CODE_ROOT,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    origin = Path(result.stdout.splitlines()[-1]).resolve()
    assert origin.is_relative_to(CODE_ROOT)
    assert "cyrano" in origin.parts


@pytest.mark.timeout(180)
def test_rc00_03_wheel_carries_cyrano_resources(tmp_path):
    """R4-RC00-03: wheel build, fresh-venv install, resource read."""
    wheel = build_wheel(CODE_ROOT, tmp_path / "dist")
    report = check_wheel_resources(wheel)
    assert report["ok"], report["missing"]
    assert any(
        name.endswith("cyrano/dcode/probes.py")
        for name in report["cyrano_files"]
    )

    venv = tmp_path / "venv"
    subprocess.run(
        ["uv", "venv", str(venv)],
        text=True,
        capture_output=True,
        timeout=60,
        check=True,
    )
    python = venv / "bin" / "python"
    clean_env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}
    }
    install = subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python),
            "--no-deps",
            "--offline",
            str(wheel),
        ],
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
        cwd=tmp_path,
        env=clean_env,
    )
    if install.returncode != 0:  # cache miss: retry without --offline
        argv = [
            "uv",
            "pip",
            "install",
            "--python",
            str(python),
            "--no-deps",
            str(wheel),
        ]
        install = subprocess.run(
            argv,
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
            cwd=tmp_path,
            env=clean_env,
        )
    assert install.returncode == 0, install.stderr
    probe = subprocess.run(
        [
            str(python),
            "-c",
            (
                "import importlib.resources as r;"
                "import deepagents_code.cyrano as c;"
                "assert r.files('deepagents_code.cyrano')"
                ".joinpath('__init__.py').is_file();"
                "print(c.__file__)"
            ),
        ],
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
        cwd=tmp_path,
        env=clean_env,
    )
    assert probe.returncode == 0, probe.stderr
    assert Path(probe.stdout.strip()).is_relative_to(venv)


def test_rc00_04_foreign_target_content_rejects_entire_copy(tmp_path):
    """R4-RC00-04: a conflict refuses the whole plan upfront."""
    code_root = tmp_path / "code"
    code_root.mkdir()
    _fake_code_root(code_root)
    existing = code_root / "deepagents_code" / "cyrano"
    existing.mkdir(parents=True)
    foreign = existing / "marker.py"
    foreign.write_text("MARKER = 'someone else'\n", encoding="utf-8")
    payload = _payload(tmp_path)

    with pytest.raises(CyranoError, match="COPY_CONFLICT"):
        plan_copy(payload, code_root)
    assert foreign.read_text(encoding="utf-8") == "MARKER = 'someone else'\n"
    assert not (code_root / "cyrano").exists()

    stub = type("E", (), {"action": "conflict", "relative": "x"})()
    with pytest.raises(CyranoError, match="COPY_CONFLICT"):
        apply_copy([stub])


def test_rc00_wheel_rejects_garbage(tmp_path):
    bad = tmp_path / "not-a-wheel.whl"
    bad.write_bytes(b"not a zip")
    with pytest.raises(CyranoError, match="WHEEL_UNREADABLE"):
        check_wheel_resources(bad)
    empty = tmp_path / "empty.whl"
    with zipfile.ZipFile(empty, "w") as archive:
        archive.writestr("deepagents_code/__init__.py", "")
    report = check_wheel_resources(empty)
    assert report["ok"] is False
    assert "deepagents_code/cyrano/__init__.py" in report["missing"]
    assert shutil.which("uv") is not None
