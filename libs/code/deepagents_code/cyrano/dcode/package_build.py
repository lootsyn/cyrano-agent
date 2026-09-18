"""Source inventory, additive-copy planning, and wheel resource checks.

Copy planning is fail-closed: any pre-existing file with different bytes
is a conflict that rejects the whole plan before a single write happens.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess  # noqa: S404 - wheels/git HEAD need it
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from deepagents_code.cyrano.contracts.types import CyranoError

if TYPE_CHECKING:
    from collections.abc import Mapping

PROTECTED = ("pyproject.toml", "uv.lock", "deepagents_code/__init__.py")
OWNED_ROOTS = (
    ".agents/skills/cyrano-development",
    "CYRANO_START_HERE.ko.md",
    "cyrano",
    "deepagents_code/cyrano",
    "tests/cyrano_product",
    "tests/unit_tests/cyrano",
)


@dataclass(frozen=True, slots=True)
class CodeRoot:
    """A verified native ``libs/code`` checkout, never a payload dir."""

    root: str
    package_dir: str
    head: str | None


@dataclass(frozen=True, slots=True)
class SourceInventory:
    """Ordered ``(path, sha256)`` pairs for every owned delta file."""

    entries: tuple[tuple[str, str], ...]

    @property
    def digest(self) -> str:
        """Hash the whole inventory deterministically."""
        payload = json.dumps(list(self.entries)).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class CopyEntry:
    """One planned copy: ``create``, ``identical``, or ``conflict``."""

    source: str
    relative: str
    target: str
    action: str


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_native_checkout(path: Path | str) -> CodeRoot:
    """Validate that a path is the real ``libs/code`` checkout.

    Args:
        path: Candidate directory.

    Returns:
        Bound checkout paths plus the git HEAD when readable.

    Raises:
        CyranoError: ``NOT_DCODE_CODE_ROOT`` when required anchors are
            absent.
    """
    root = Path(path).resolve()
    if root.is_symlink() or not (root / "deepagents_code").is_dir():
        raise CyranoError("NOT_DCODE_CODE_ROOT", str(path))
    pyproject = root / "pyproject.toml"
    named = (
        pyproject.is_file()
        and 'name = "deepagents-code"' in pyproject.read_text(encoding="utf-8")
    )
    if not named:
        raise CyranoError("NOT_DCODE_CODE_ROOT", str(path))
    head: str | None = None
    git = shutil.which("git")
    if git is not None:
        try:
            result = subprocess.run(  # noqa: S603 - fixed argv
                [git, "rev-parse", "HEAD"],
                cwd=root,
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                head = result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            head = None
    return CodeRoot(str(root), str(root / "deepagents_code"), head)


def enumerate_owned_delta(code_root: Path | str) -> SourceInventory:
    """List every Cyrano-owned file under a code root.

    Args:
        code_root: A directory accepted by ``resolve_native_checkout``.

    Returns:
        Sorted path/digest pairs; symlinks are rejected, never
        followed.

    Raises:
        CyranoError: ``SYMLINK_OWNED_PATH`` when an owned path is a
            link.
    """
    root = Path(code_root).resolve()
    entries: list[tuple[str, str]] = []
    for owned in OWNED_ROOTS:
        base = root / owned
        if base.is_symlink():
            raise CyranoError("SYMLINK_OWNED_PATH", owned)
        if base.is_file():
            entries.append((owned, _sha256(base)))
        elif base.is_dir():
            for item in sorted(base.rglob("*")):
                if item.is_symlink():
                    raise CyranoError("SYMLINK_OWNED_PATH", str(item))
                if item.is_file():
                    relative = str(item.relative_to(root))
                    entries.append((relative, _sha256(item)))
    return SourceInventory(tuple(sorted(entries)))


def plan_copy(
    payload_root: Path | str,
    code_root: Path | str,
) -> list[CopyEntry]:
    """Plan an additive copy without writing anything.

    Args:
        payload_root: Directory whose *contents* map onto
            ``code_root``.
        code_root: Native ``libs/code`` directory.

    Returns:
        One entry per payload file, in deterministic order.

    Raises:
        CyranoError: ``COPY_CONFLICT`` when any target exists with
            different bytes or is a symlink; nothing is written in that
            case.
    """
    payload = Path(payload_root).resolve()
    root = Path(code_root).resolve()
    if not payload.is_dir():
        raise CyranoError("PAYLOAD_MISSING", str(payload_root))
    entries: list[CopyEntry] = []
    conflicts: list[str] = []
    for source in sorted(payload.rglob("*")):
        if source.is_symlink() or not source.is_file():
            if source.is_symlink():
                conflicts.append(str(source))
            continue
        relative = source.relative_to(payload).as_posix()
        target = root / relative
        if target.is_symlink():
            conflicts.append(relative)
            action = "conflict"
        elif not target.exists():
            action = "create"
        elif target.read_bytes() == source.read_bytes():
            action = "identical"
        else:
            action = "conflict"
            conflicts.append(relative)
        entries.append(CopyEntry(str(source), relative, str(target), action))
    if conflicts:
        raise CyranoError("COPY_CONFLICT", ", ".join(sorted(conflicts)))
    return entries


def apply_copy(entries: list[CopyEntry]) -> int:
    """Apply a conflict-free plan; identical targets are left untouched.

    Args:
        entries: Output of ``plan_copy``.

    Returns:
        Number of files actually written.

    Raises:
        CyranoError: ``COPY_CONFLICT`` if a plan still carries
            conflicts.
    """
    conflicts = [
        entry.relative for entry in entries if entry.action == "conflict"
    ]
    if conflicts:
        raise CyranoError("COPY_CONFLICT", ", ".join(sorted(conflicts)))
    written = 0
    for entry in entries:
        if entry.action != "create":
            continue
        target = Path(entry.target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(entry.source, target)
        written += 1
    return written


def verify_installed(
    code_root: Path | str,
    preimage: Mapping[str, str],
) -> dict[str, object]:
    """Verify protected native files still match their recorded digests.

    Args:
        code_root: Native ``libs/code`` directory after a copy.
        preimage: ``relative path -> sha256:...`` recorded before the
            copy.

    Returns:
        Violation list plus the Cyrano package origin path when
        present.
    """
    root = Path(code_root).resolve()
    violations: list[str] = []
    for relative, expected in sorted(preimage.items()):
        target = root / relative
        if target.is_symlink() or not target.is_file():
            violations.append("PROTECTED_MISSING:" + relative)
        elif _sha256(target) != expected:
            violations.append("PROTECTED_CHANGED:" + relative)
    origin = root / "deepagents_code" / "cyrano"
    return {
        "protected_unchanged": not violations,
        "violations": violations,
        "cyrano_origin": str(origin) if origin.is_dir() else None,
    }


def check_wheel_resources(
    wheel_path: Path | str,
    required: tuple[str, ...] = ("deepagents_code/cyrano/__init__.py",),
) -> dict[str, object]:
    """Inspect a built wheel for required package resources.

    Args:
        wheel_path: Path to a ``.whl`` archive.
        required: Archive members that must be present.

    Returns:
        Present/missing lists and all packaged ``cyrano`` members.

    Raises:
        CyranoError: ``WHEEL_UNREADABLE`` for non-zip or missing
            archives.
    """
    wheel = Path(wheel_path)
    try:
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
    except (OSError, zipfile.BadZipFile) as exc:
        raise CyranoError("WHEEL_UNREADABLE", f"{wheel}: {exc}") from exc
    missing = [item for item in required if item not in names]
    return {
        "wheel": wheel.name,
        "ok": not missing,
        "present": [item for item in required if item in names],
        "missing": missing,
        "cyrano_files": sorted(
            name
            for name in names
            if name.startswith("deepagents_code/cyrano/")
        ),
    }


def build_wheel(project_root: Path | str, out_dir: Path | str) -> Path:
    """Build a wheel with the ambient toolchain.

    Build isolation stays off so the pinned build backend is used
    instead of a fresh network resolve.

    Args:
        project_root: Directory containing ``pyproject.toml``.
        out_dir: Destination directory for the wheel.

    Returns:
        Path of the produced wheel.

    Raises:
        CyranoError: ``WHEEL_BUILD_FAILED`` or ``WHEEL_MISSING``.
    """
    uv = shutil.which("uv")
    if uv is None:
        raise CyranoError("TOOL_MISSING", "uv")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    argv = [uv, "build", "--wheel", "--no-build-isolation"]
    argv += ["--out-dir", str(out)]
    result = subprocess.run(  # noqa: S603 - fixed argv, resolved binary
        argv,
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        raise CyranoError("WHEEL_BUILD_FAILED", result.stderr.strip()[-500:])
    wheels = sorted(out.glob("*.whl"))
    if not wheels:
        raise CyranoError("WHEEL_MISSING", str(out))
    return wheels[-1]
