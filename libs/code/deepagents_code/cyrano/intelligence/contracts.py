"""Validate snapshot-bound indexes and read-only requests.

These checks do not implement an LSP client or an OS sandbox.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class AnalysisError(ValueError):
    """Reject an unsafe request or an index from incompatible input."""


@dataclass(frozen=True)
class IndexBinding:
    """Identify the inputs and permissions of an index."""

    workspace_id: str
    source_digest: str
    environment_digest: str
    acl_digest: str
    provider_digest: str
    schema_version: str

    def require_match(self, expected: IndexBinding) -> None:
        """Reject reuse unless every input and authz field matches."""
        if self != expected:
            raise AnalysisError("INDEX_BINDING_MISMATCH")


def safe_source_path(root: Path, relative: str) -> Path:
    """Resolve a canonical existing file without following symlinks.

    Args:
        root: A trusted immutable snapshot root, not a model path.
        relative: A slash-separated path from an analysis provider.

    Returns:
        The verified file path beneath the root.

    Raises:
        AnalysisError: The path is noncanonical or not a file.
    """
    parts = relative.split("/")
    candidate = PurePosixPath(relative)
    if (
        not relative
        or "\\" in relative
        or ":" in relative
        or candidate.is_absolute()
        or any(p in {"", ".", ".."} for p in parts)
    ):
        raise AnalysisError("INVALID_SOURCE_PATH")
    if root.is_symlink():
        raise AnalysisError("SYMLINK_ROOT")
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise AnalysisError("SYMLINK_SOURCE")
    if not current.resolve().is_relative_to(root.resolve()):
        raise AnalysisError("SOURCE_ESCAPE")
    if not current.is_file():
        raise AnalysisError("SOURCE_MISSING")
    return current


@dataclass(frozen=True)
class GraphRelation:
    """One provider-reported edge with its explicit trust grade.

    ``declared`` relations come from source facts; ``inferred``
    relations are heuristic and never authorize anything alone.
    """

    source: str
    target: str
    kind: str
    trust: str

    def require_declared(self) -> None:
        """Reject inferred edges where declared lineage is required."""
        if self.trust != "declared":
            raise AnalysisError("INFERRED_RELATION_NOT_AUTHORITY")


READ_OPERATIONS = frozenset(
    {
        "definition",
        "references",
        "document_symbols",
        "diagnostics",
        "document_search",
        "graph_neighbors",
        "scip_references",
    }
)


def require_read_operation(operation: str, supported: frozenset[str]) -> None:
    """Require an allowed operation that the provider advertises.

    Unknown operations are denied; an empty list is not a default.
    """
    if operation not in READ_OPERATIONS:
        raise AnalysisError("MUTATION_OR_UNKNOWN_OPERATION")
    if operation not in supported:
        raise AnalysisError("CAPABILITY_UNSUPPORTED")
