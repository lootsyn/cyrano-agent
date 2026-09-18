"""Sentinel matrix and launch isolation for governed dcode runs.

Every effect path — native tools, extension tools, MCP, children,
compaction, retry, remember — is mediated individually; no path
bypasses the guard. A disabled extension sentinel stops a governed
launch. Discovery never loads project extension/hook/MCP settings:
they are excluded from the launch view with a recorded manifest and
the original repository is untouched.
"""

import hashlib
import json
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from deepagents_code.cyrano.contracts.types import CyranoError

SENTINEL_PATHS = (
    "native",
    "extension",
    "mcp",
    "child",
    "compaction",
    "retry",
    "remember",
)

# Project-level settings that carry executable trust and are excluded
# from discovery launch views.
UNTRUSTED_PROJECT_CONFIGS = (
    ".dcode/extensions",
    ".dcode/hooks",
    ".dcode/mcp.json",
    ".deepagents/mcp.json",
    "mcp.json",
)

# Explicit versioned role mappings. String normalization or fuzzy
# matching never grants authority; an unknown alias or version fails.
ROLE_MAPPINGS: dict[str, dict[str, str]] = {
    "v1": {
        "interviewer": "interview",
        "planner": "plan",
        "executor": "execute",
        "reviewer": "review",
    },
}


def check_path(
    path: str,
    guard: Callable[[str], bool],
) -> str:
    """Route one sentinel path through the guard.

    Every declared path is checked individually; an unknown path or a
    guard refusal raises ``SCOPE_DENIED``.
    """
    if path not in SENTINEL_PATHS:
        raise CyranoError("SCOPE_DENIED", f"unknown sentinel path {path!r}")
    if not guard(path):
        raise CyranoError(
            "SCOPE_DENIED", f"guard refused sentinel path {path!r}"
        )
    return path


def verify_extension_sentinel(enabled: bool) -> None:
    """A disabled extension sentinel aborts governed launch."""
    if not enabled:
        raise CyranoError(
            "CAPABILITY_UNAVAILABLE",
            "extension sentinel disabled; governed launch stopped",
        )


@dataclass(frozen=True, slots=True)
class LaunchView:
    """A discovery view with untrusted configs excluded."""

    view_root: Path
    excluded: tuple[str, ...]
    manifest_digest: str


def build_launch_view(
    source_root: Path,
    view_root: Path,
) -> LaunchView:
    """Copy a workspace for discovery, excluding trust configs.

    The source tree is never modified. Every excluded path is recorded
    in the exclusion manifest digest.
    """
    excluded: list[str] = []

    def _ignore(directory: str, names: list[str]) -> set[str]:
        skip: set[str] = set()
        base = Path(directory)
        for rel in UNTRUSTED_PROJECT_CONFIGS:
            candidate = source_root / rel
            if not candidate.exists():
                continue
            try:
                if candidate.parent == base and candidate.name in names:
                    skip.add(candidate.name)
                    excluded.append(rel)
            except OSError:
                continue
        return skip

    _ = shutil.copytree(
        source_root, view_root, ignore=_ignore, dirs_exist_ok=True
    )
    # Manifest records exactly what was withheld from discovery.
    manifest = json.dumps(sorted(set(excluded)))
    digest = "sha256:" + hashlib.sha256(manifest.encode()).hexdigest()
    return LaunchView(
        view_root=view_root,
        excluded=tuple(sorted(set(excluded))),
        manifest_digest=digest,
    )


def map_role(alias: str, *, version: str = "v1") -> str:
    """Resolve a role alias through an explicit versioned table."""
    table = ROLE_MAPPINGS.get(version)
    if table is None or alias not in table:
        raise CyranoError(
            "UNKNOWN_ROLE",
            f"role {alias!r} has no mapping in {version!r}",
        )
    return table[alias]


def mediation_matrix(
    guard: Callable[[str], bool],
) -> Mapping[str, bool]:
    """Probe every sentinel path; report per-path verdicts."""
    out: dict[str, bool] = {}
    for path in SENTINEL_PATHS:
        try:
            _ = check_path(path, guard)
            out[path] = True
        except CyranoError:
            out[path] = False
    return out
