"""Quality policy resolution.

A policy names one tool identity (``ruff``, ``ty``, ``pytest`` …), the
rule selection it enforces, and the path scope it governs. A config
that selects doc-length rules (W505/D5) without declaring
``max_doc_length`` is a contract violation, not a default.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from fnmatch import fnmatch
from typing import TYPE_CHECKING

from deepagents_code.cyrano.contracts.types import CyranoError

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey,
    )

    from deepagents_code.cyrano.kernel.approvals import SignedPermit

SUPPORTED_TOOLS = frozenset(
    {"ruff", "ruff-format", "ty", "basedpyright", "pytest"}
)
_DOC_RULE_PREFIXES = ("W505", "D5")


@dataclass(frozen=True, slots=True)
class QualityPolicy:
    """Immutable policy binding tool, rules, scope and baseline."""

    policy_id: str
    tool: str
    select: frozenset[str]
    line_length: int
    max_doc_length: int | None
    scope_patterns: tuple[str, ...]
    baseline_digest: str | None = None


def _as_str_list(value: object) -> list[str]:
    """Coerce a config list field to strings; anything else fails."""
    if not isinstance(value, (list, tuple)):
        return []
    return [str(v) for v in value]


def _as_int(value: object, default: int) -> int:
    """Coerce an int-like config field, keeping the default."""
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    raise CyranoError("POLICY_CONFIG_MISMATCH", f"non-integer field {value!r}")


def resolve_quality_policy(configs: object) -> QualityPolicy:
    """Resolve one authoritative policy; conflicting claims fail.

    Two configs that both claim authority over the same tool are a
    ``POLICY_CONFIG_MISMATCH`` — the resolver never picks silently.
    """
    if isinstance(configs, Mapping):
        config = configs
    elif isinstance(configs, list):
        authoritative = [
            c
            for c in configs
            if isinstance(c, Mapping)
            and c.get("authoritative", True) is not False
        ]
        if len(authoritative) != 1:
            raise CyranoError(
                "POLICY_CONFIG_MISMATCH",
                f"expected exactly one authoritative policy, "
                f"got {len(authoritative)}",
            )
        config = authoritative[0]
    else:
        raise CyranoError(
            "POLICY_CONFIG_MISMATCH",
            "policy config must be a mapping or list of mappings",
        )

    tool = str(config.get("tool", ""))
    if tool not in SUPPORTED_TOOLS:
        raise CyranoError(
            "POLICY_CONFIG_MISMATCH", f"unsupported tool identity: {tool!r}"
        )
    scope = tuple(_as_str_list(config.get("scope", ())))
    if not scope:
        raise CyranoError("BLOCKED", "quality policy has no governed scope")
    select = frozenset(_as_str_list(config.get("select", ())))
    max_doc_raw = config.get("max_doc_length")
    max_doc = None if max_doc_raw is None else _as_int(max_doc_raw, 0)
    if (
        any(s.startswith(p) for s in select for p in _DOC_RULE_PREFIXES)
        and max_doc is None
    ):
        raise CyranoError(
            "POLICY_CONFIG_MISMATCH",
            "doc-length rules selected without max_doc_length",
        )
    baseline = config.get("baseline_digest")
    return QualityPolicy(
        policy_id=str(config.get("policy_id") or f"{tool}-policy"),
        tool=tool,
        select=select,
        line_length=_as_int(config.get("line_length"), 79),
        max_doc_length=max_doc,
        scope_patterns=scope,
        baseline_digest=(baseline if isinstance(baseline, str) else None),
    )


def check_path_in_scope(policy: QualityPolicy, path: str) -> None:
    """A governed run only ever touches paths inside its scope.

    A path outside every scope pattern is refused before any tool
    starts — ``PATH_POLICY_VIOLATION``, never a late cleanup.
    """
    if not any(fnmatch(path, p) for p in policy.scope_patterns):
        raise CyranoError("PATH_POLICY_VIOLATION", path)


def require_run_permit(
    permit: SignedPermit | None,
    trust_root: Ed25519PublicKey,
    *,
    subject_digest: str,
    now: int,
    is_revoked: Callable[[str], bool],
) -> None:
    """A governed quality run requires a verified execute permit.

    A missing permit is ``POLICY_VIOLATION`` — never an implicit pass.
    Signature, revocation, expiry, purpose and subject checks defer to
    the kernel's ``verify_permit``.
    """
    from deepagents_code.cyrano.kernel.approvals import verify_permit

    if permit is None:
        raise CyranoError(
            "POLICY_VIOLATION",
            "quality execution requires an approved permit",
        )
    verify_permit(
        permit,
        trust_root,
        purpose="execute",
        subject_digest=subject_digest,
        now=now,
        is_revoked=is_revoked,
    )
