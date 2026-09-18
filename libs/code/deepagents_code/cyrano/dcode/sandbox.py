"""Sandbox mount planning and isolation verdicts.

Mounts are validated against the real filesystem before dispatch:
symlinks that escape the workspace, hardlinks to protected inodes,
and unapproved device/socket mounts are denied. Isolation checks
report advisory limits honestly; an agent that can reach the
approval key material is never called governed.
"""

import stat
from dataclasses import dataclass
from pathlib import Path

from deepagents_code.cyrano.contracts.types import CyranoError

MOUNT_MODES = frozenset({"ro", "scratch", "only_write"})


@dataclass(frozen=True, slots=True)
class Mount:
    """A validated mount: resolved host path, target, and mode."""

    source: Path
    target: str
    mode: str


@dataclass(slots=True)
class SandboxPlan:
    """Validated mounts plus the governed verdict and advisories."""

    mounts: tuple[Mount, ...]
    advisories: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class IsolationVerdict:
    """Whether the environment actually isolates the agent."""

    governed: bool
    advisories: tuple[str, ...]


def _has_symlink_ancestor(path: Path, root: Path) -> bool:
    """True when any component of path beneath root is a symlink."""
    current = root
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def plan_sandbox(
    specs: list[tuple[str, str, str]],
    *,
    workspace_root: Path,
    protected_inodes: set[tuple[int, int]] | None = None,
    allow_docker_socket: bool = False,
) -> SandboxPlan:
    """Validate requested mounts; every violation fails closed.

    Args:
        specs: (host_path, target, mode) triples to validate.
        workspace_root: trusted root all sources must stay under.
        protected_inodes: (st_dev, st_ino) pairs that must never be
            aliased into the sandbox, catching hardlink escapes.
        allow_docker_socket: host Docker socket mounts require this
            explicit approval flag.

    Returns:
        The validated plan; raises a typed CyranoError otherwise.
    """
    protected = protected_inodes or set()
    root = workspace_root.resolve()
    mounts: list[Mount] = []
    targets: set[str] = set()
    for source_s, target, mode in specs:
        if mode not in MOUNT_MODES:
            raise CyranoError("MOUNT_DENIED", f"bad mode {mode}")
        source = Path(source_s)
        if source == Path("/var/run/docker.sock"):
            if not allow_docker_socket:
                raise CyranoError(
                    "MOUNT_DENIED", "docker socket needs approval"
                )
        resolved = source.resolve()
        if source.exists() or source.is_symlink():
            if not resolved.is_relative_to(root):
                raise CyranoError("PATH_ESCAPE", source_s)
            if _has_symlink_ancestor(source, root):
                raise CyranoError("PATH_ESCAPE", source_s)
        elif _has_symlink_ancestor(source.parent, root):
            raise CyranoError("PATH_ESCAPE", source_s)
        if source.exists():
            try:
                st = source.stat()
            except OSError as exc:
                raise CyranoError(
                    "MOUNT_DENIED", f"stat failed: {exc}"
                ) from exc
            if (st.st_dev, st.st_ino) in protected:
                raise CyranoError("PROTECTED_ALIAS", source_s)
            if not (stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode)):
                raise CyranoError(
                    "MOUNT_DENIED", f"unsupported type {source_s}"
                )
        if mode == "only_write" and target in targets:
            raise CyranoError("DENIED", f"{target} cannot also be readable")
        targets.add(target)
        mounts.append(Mount(source=source, target=target, mode=mode))
    return SandboxPlan(mounts=tuple(mounts))


def isolation_verdict(
    *,
    agent_reads_approval_key: bool,
    agent_writes_approval_db: bool,
    same_user_unrestricted_shell: bool,
) -> IsolationVerdict:
    """Report the real isolation boundary; no silent governed."""
    advisories: list[str] = []
    governed = True
    if agent_reads_approval_key:
        governed = False
        advisories.append("agent can read approval key material")
    if agent_writes_approval_db:
        governed = False
        advisories.append("agent can write the approval ledger")
    if same_user_unrestricted_shell:
        governed = False
        advisories.append("same-OS-user shell is advisory only, not isolation")
    return IsolationVerdict(governed=governed, advisories=tuple(advisories))
