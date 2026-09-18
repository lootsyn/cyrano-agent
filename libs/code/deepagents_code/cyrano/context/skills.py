"""Skill registry: strict manifests, scope-bound load and apply.

A manifest with unbound ``__BIND_*__`` placeholders is a template —
it is refused, never silently activated. Loading returns metadata
only; applying records the grounds and refuses revoked, out-of-scope,
or wrong-role use. A direct "remember"-style promotion outside the
candidate flow is always refused.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError

_PLACEHOLDER = re.compile(r"__BIND_[A-Z_]+__")

RESOURCE_KINDS = frozenset({"markdown", "json", "script"})


@dataclass(frozen=True, slots=True)
class SkillResource:
    """One resource declared by a manifest."""

    path: str
    digest: str
    executable: bool


@dataclass(frozen=True, slots=True)
class SkillManifest:
    """A bound, validated skill manifest."""

    skill_id: str
    version: str
    entrypoint: str
    content_digest: str
    resources: tuple[SkillResource, ...]
    allowed_roles: tuple[str, ...]
    required_tools: tuple[str, ...]
    scope_tenant: str
    scope_user: str
    scope_workspace: str
    context_byte_budget: int
    status: str  # candidate | active | revoked
    release_digest: str | None
    approval_ref: str | None
    grants_execution: bool


@dataclass(frozen=True, slots=True)
class SkillMetadata:
    """The metadata-only load view; the body is not injected."""

    skill_id: str
    version: str
    entrypoint: str
    content_digest: str
    status: str


def _text(doc: Mapping[str, object], key: str) -> str:
    value = doc.get(key)
    if not isinstance(value, str) or not value:
        raise CyranoError("INVALID_MANIFEST", f"missing {key}")
    return value


def _mapping(value: object, key: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CyranoError("INVALID_MANIFEST", f"{key} must be a mapping")
    return {str(k): v for k, v in value.items()}


def _str_list(doc: Mapping[str, object], key: str) -> tuple[str, ...]:
    raw = doc.get(key)
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise CyranoError("INVALID_MANIFEST", f"{key} must be a list")
    return tuple(str(item) for item in raw)


def parse_manifest(doc: Mapping[str, object]) -> SkillManifest:
    """Parse a manifest strictly; unbound placeholders refuse."""
    if doc.get("kind") != "skill_manifest":
        raise CyranoError("INVALID_MANIFEST", "kind must be skill_manifest")
    blob = repr(sorted(doc.items(), key=lambda kv: kv[0]))
    if _PLACEHOLDER.search(blob):
        raise CyranoError(
            "TEMPLATE_UNBOUND", "manifest still has __BIND_*__ slots"
        )
    raw_resources = doc.get("resources") or []
    if not isinstance(raw_resources, list):
        raise CyranoError("INVALID_MANIFEST", "resources must be a list")
    resources: list[SkillResource] = []
    executable = False
    for item in raw_resources:
        entry = _mapping(item, "resources[]")
        res = SkillResource(
            path=_text(entry, "path"),
            digest=_text(entry, "digest"),
            executable=bool(entry.get("executable")),
        )
        executable = executable or res.executable
        resources.append(res)
    grants = bool(doc.get("grants_execution"))
    if executable and not grants:
        raise CyranoError(
            "EXECUTION_PERMISSION_REQUIRED",
            "executable resource needs a declared code lane",
        )
    scope = _mapping(doc.get("scope"), "scope")
    status = str(doc.get("status", "candidate"))
    if status not in {"candidate", "active", "revoked"}:
        raise CyranoError("INVALID_MANIFEST", f"bad status {status}")
    roles = _str_list(doc, "allowed_roles")
    tools = _str_list(doc, "required_tools")
    budget = doc.get("context_byte_budget", 0)
    if not isinstance(budget, int) or isinstance(budget, bool):
        raise CyranoError(
            "INVALID_MANIFEST", "context_byte_budget must be an int"
        )
    return SkillManifest(
        skill_id=_text(doc, "id"),
        version=_text(doc, "version"),
        entrypoint=_text(doc, "entrypoint"),
        content_digest=_text(doc, "content_digest"),
        resources=tuple(resources),
        allowed_roles=roles,
        required_tools=tools,
        scope_tenant=_text(scope, "tenant"),
        scope_user=_text(scope, "user"),
        scope_workspace=_text(scope, "workspace"),
        context_byte_budget=budget,
        status=status,
        release_digest=(
            str(doc["release_digest"]) if doc.get("release_digest") else None
        ),
        approval_ref=(
            str(doc["approval_ref"]) if doc.get("approval_ref") else None
        ),
        grants_execution=grants,
    )


class SkillRegistry:
    """Registered manifests; duplicates and bypasses are refused."""

    def __init__(self) -> None:
        """Start with an empty registry and no resolutions."""
        self._manifests: dict[str, SkillManifest] = {}
        self._resolved: dict[str, tuple[str, str]] = {}

    def register(self, manifest: SkillManifest, *, resolved_path: str) -> None:
        """Register a manifest bound to a resolved path+digest.

        A second manifest with the same id, or a same-id rebind to a
        different digest, is refused — release mixing is not allowed.
        """
        existing = self._manifests.get(manifest.skill_id)
        if existing is not None:
            raise CyranoError(
                "SKILL_DUPLICATE", f"skill {manifest.skill_id!r} exists"
            )
        prior = self._resolved.get(manifest.skill_id)
        if prior is not None and prior[1] != manifest.content_digest:
            raise CyranoError(
                "RELEASE_MIX",
                f"digest drift for {manifest.skill_id!r}",
            )
        self._manifests[manifest.skill_id] = manifest
        self._resolved[manifest.skill_id] = (
            resolved_path,
            manifest.content_digest,
        )

    def _scoped(
        self, manifest: SkillManifest, scope: tuple[str, str, str]
    ) -> None:
        bound = (
            manifest.scope_tenant,
            manifest.scope_user,
            manifest.scope_workspace,
        )
        if bound != scope:
            raise CyranoError(
                "SCOPE_DENIED", "skill is not bound to this scope"
            )

    def load(
        self, skill_id: str, scope: tuple[str, str, str]
    ) -> SkillMetadata:
        """Metadata-only load; this alone never counts as applied."""
        manifest = self._manifests.get(skill_id)
        if manifest is None:
            raise CyranoError("UNKNOWN_SKILL", skill_id)
        self._scoped(manifest, scope)
        return SkillMetadata(
            skill_id=manifest.skill_id,
            version=manifest.version,
            entrypoint=manifest.entrypoint,
            content_digest=manifest.content_digest,
            status=manifest.status,
        )

    def apply(
        self,
        skill_id: str,
        scope: tuple[str, str, str],
        *,
        role: str,
        conditions_met: bool,
    ) -> SkillManifest:
        """Apply an active skill; revoked or wrong-role use refuses."""
        manifest = self._manifests.get(skill_id)
        if manifest is None:
            raise CyranoError("UNKNOWN_SKILL", skill_id)
        self._scoped(manifest, scope)
        if manifest.status == "revoked":
            raise CyranoError("SKILL_REVOKED", skill_id)
        if manifest.status != "active":
            raise CyranoError(
                "SKILL_NOT_ACTIVE",
                f"{skill_id} is {manifest.status}",
            )
        if manifest.allowed_roles and role not in manifest.allowed_roles:
            raise CyranoError(
                "ROLE_NOT_ALLOWED", f"{role} may not apply {skill_id}"
            )
        if not conditions_met:
            raise CyranoError(
                "CONDITIONS_UNMET", f"{skill_id} conditions unmet"
            )
        return manifest

    def promote_direct(self, skill_id: str) -> None:
        """A direct write/promotion bypass is always refused."""
        raise CyranoError(
            "CANDIDATE_BYPASS",
            f"{skill_id} must go through the candidate flow",
        )

    def metadata_view(
        self, scope: tuple[str, str, str]
    ) -> tuple[SkillMetadata, ...]:
        """Metadata for in-scope skills; bodies are never injected."""
        out: list[SkillMetadata] = []
        for manifest in self._manifests.values():
            bound = (
                manifest.scope_tenant,
                manifest.scope_user,
                manifest.scope_workspace,
            )
            if bound != scope:
                continue
            out.append(
                SkillMetadata(
                    skill_id=manifest.skill_id,
                    version=manifest.version,
                    entrypoint=manifest.entrypoint,
                    content_digest=manifest.content_digest,
                    status=manifest.status,
                )
            )
        return tuple(sorted(out, key=lambda m: m.skill_id))
