"""Runtime inspection of the installed dcode distribution.

Probe results describe the installed API *surface* only. A ``verified``
probe means the documented symbols exist with the expected shape; it
does not prove runtime semantics, isolation, or provider behavior.
Those stay ``not_tested`` until a later work package exercises them.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import inspect
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from deepagents_code.cyrano.contracts.types import CyranoError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

ProbeStatus = Literal["verified", "unsupported", "failed", "not_tested"]

PROBE_NAMES = (
    "extension_loading",
    "async_middleware",
    "child_observation",
    "tool_mediation",
    "sandbox_isolation",
    "trusted_approval",
    "context_manifest",
    "cancel_recovery",
)

STATUS_VALUES = frozenset({"verified", "unsupported", "failed", "not_tested"})


@dataclass(frozen=True, slots=True)
class DistributionInfo:
    """Installed artifact metadata; ``editable`` marks a dev install."""

    name: str
    version: str
    location: str
    editable: bool
    record_digest: str
    file_count: int


@dataclass(frozen=True, slots=True)
class ProbeReport:
    """One capability-surface observation, never a success claim."""

    name: str
    status: ProbeStatus
    detail: str
    observed: tuple[str, ...] = ()


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def inspect_installed_distribution(
    name: str = "deepagents-code",
) -> DistributionInfo:
    """Return installed artifact metadata for a distribution.

    Args:
        name: Distribution name as installed (the project name, not
            the import name).

    Returns:
        Immutable metadata binding version, location, and digest.

    Raises:
        CyranoError: ``DISTRIBUTION_MISSING`` when the distribution
            is absent.
    """
    try:
        dist = importlib.metadata.distribution(name)
    except importlib.metadata.PackageNotFoundError:
        raise CyranoError("DISTRIBUTION_MISSING", name) from None
    location = str(dist.locate_file(""))
    editable = False
    direct_url = dist.read_text("direct_url.json")
    if direct_url:
        try:
            info = json.loads(direct_url)
            editable = bool(info.get("dir_info", {}).get("editable"))
        except json.JSONDecodeError:
            editable = False
    record_bytes = dist.read_text("RECORD")
    if record_bytes is not None:
        record_digest = _sha256(record_bytes.encode("utf-8"))
    else:
        files = sorted(str(item) for item in (dist.files or []))
        record_digest = _sha256(json.dumps(files).encode("utf-8"))
    return DistributionInfo(
        name=name,
        version=dist.version,
        location=location,
        editable=editable,
        record_digest=record_digest,
        file_count=len(list(dist.files or [])),
    )


def _spec_present(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def _factory_params() -> set[str]:
    import deepagents

    return set(inspect.signature(deepagents.create_deep_agent).parameters)


def _probe_extension_loading() -> tuple[ProbeStatus, str, tuple[str, ...]]:
    observed = ("deepagents_code.skills", "skills", "middleware")
    ok = _spec_present("deepagents_code.skills") and (
        {"skills", "middleware"} <= _factory_params()
    )
    detail = "skills/middleware hooks"
    return ("verified" if ok else "unsupported", detail, observed)


def _probe_async_middleware() -> tuple[ProbeStatus, str, tuple[str, ...]]:
    observed = ("deepagents.middleware", "middleware")
    ok = _spec_present("deepagents.middleware") and (
        "middleware" in _factory_params()
    )
    detail = "agent middleware parameter"
    return ("verified" if ok else "unsupported", detail, observed)


def _probe_child_observation() -> tuple[ProbeStatus, str, tuple[str, ...]]:
    from deepagents import middleware

    observed = ("SubAgentMiddleware", "AsyncSubAgentMiddleware", "subagents")
    ok = (
        hasattr(middleware, "SubAgentMiddleware")
        and hasattr(middleware, "AsyncSubAgentMiddleware")
        and "subagents" in _factory_params()
    )
    detail = "subagent middleware surface"
    return ("verified" if ok else "unsupported", detail, observed)


def _probe_tool_mediation() -> tuple[ProbeStatus, str, tuple[str, ...]]:
    import langchain.agents.middleware as agent_middleware

    observed = (
        "HumanInTheLoopMiddleware",
        "InterruptOnConfig",
        "interrupt_on",
    )
    ok = (
        hasattr(agent_middleware, "HumanInTheLoopMiddleware")
        and hasattr(agent_middleware, "InterruptOnConfig")
        and "interrupt_on" in _factory_params()
    )
    detail = "tool-call mediation surface"
    return ("verified" if ok else "unsupported", detail, observed)


def _probe_sandbox_isolation() -> tuple[ProbeStatus, str, tuple[str, ...]]:
    observed = ("deepagents.backends", "backend")
    ok = _spec_present("deepagents.backends") and (
        "backend" in _factory_params()
    )
    detail = "backend isolation surface"
    return ("verified" if ok else "unsupported", detail, observed)


def _probe_trusted_approval() -> tuple[ProbeStatus, str, tuple[str, ...]]:
    observed = ("interrupt_on", "permissions")
    ok = {"interrupt_on", "permissions"} <= _factory_params()
    detail = "approval hook parameters"
    return ("verified" if ok else "unsupported", detail, observed)


def _not_tested(reason: str) -> tuple[ProbeStatus, str, tuple[str, ...]]:
    return ("not_tested", reason, ())


ProbeImpl = Callable[[], tuple[ProbeStatus, str, tuple[str, ...]]]

DEFAULT_PROBES: Mapping[str, ProbeImpl] = {
    "extension_loading": _probe_extension_loading,
    "async_middleware": _probe_async_middleware,
    "child_observation": _probe_child_observation,
    "tool_mediation": _probe_tool_mediation,
    "sandbox_isolation": _probe_sandbox_isolation,
    "trusted_approval": _probe_trusted_approval,
    # No installed dcode surface documents a context manifest; crash
    # recovery needs fault injection owned by a later work package.
    "context_manifest": lambda: _not_tested("no manifest surface"),
    "cancel_recovery": lambda: _not_tested("needs crash-injection harness"),
}


def run_compatibility_probe(
    name: str,
    *,
    impls: Mapping[str, ProbeImpl] = DEFAULT_PROBES,
) -> ProbeReport:
    """Run one capability probe and report its outcome truthfully.

    Args:
        name: A member of ``PROBE_NAMES``.
        impls: Probe implementations; injectable so tests exercise the
            aggregation logic rather than the ambient interpreter.

    Returns:
        A report with status verified, unsupported, failed, or
        not_tested.

    Raises:
        CyranoError: ``UNKNOWN_PROBE`` for an unregistered probe name.
    """
    if name not in PROBE_NAMES:
        raise CyranoError("UNKNOWN_PROBE", name)
    impl = impls.get(name)
    if impl is None:
        detail = "no probe implementation bound"
        return ProbeReport(name, "not_tested", detail)
    try:
        status, detail, observed = impl()
    except Exception as exc:  # noqa: BLE001 - probes degrade to reports
        detail = f"{type(exc).__name__}: {exc}"
        return ProbeReport(name, "failed", detail)
    return ProbeReport(name, status, detail, observed)


def run_all_probes(
    impls: Mapping[str, ProbeImpl] = DEFAULT_PROBES,
) -> dict[str, str]:
    """Return the status of every registered probe."""
    return {
        name: run_compatibility_probe(name, impls=impls).status
        for name in PROBE_NAMES
    }


def write_runtime_lock(
    path: Path,
    *,
    distribution: DistributionInfo,
    probes: Mapping[str, str],
    source_observation: Mapping[str, object],
) -> dict[str, object]:
    """Write an immutable runtime receipt.

    Status is computed from the probes, never asserted.

    Args:
        path: Destination JSON path such as
            ``cyrano/runtime/runtime-lock.json``.
        distribution: Installed artifact metadata.
        probes: Probe status per ``PROBE_NAMES`` member.
        source_observation: Pinned upstream source identifiers.

    Returns:
        The exact document written.

    Raises:
        CyranoError: ``RUNTIME_LOCK_INCOMPLETE`` when a probe is missing
            or carries an invalid status.
    """
    missing = [
        name for name in PROBE_NAMES if probes.get(name) not in STATUS_VALUES
    ]
    if missing:
        raise CyranoError("RUNTIME_LOCK_INCOMPLETE", ", ".join(missing))
    verified = all(probes[name] == "verified" for name in PROBE_NAMES)
    document: dict[str, object] = {
        "schema_version": "1.0",
        "status": "verified" if verified else "not_verified",
        "python": sys.version.split()[0],
        "dcode_distribution": distribution.name,
        "dcode_version": distribution.version,
        "artifact_hashes": [
            {
                "kind": "dist-info",
                "editable": distribution.editable,
                "sha256": distribution.record_digest,
            }
        ],
        "source_observation": dict(source_observation),
        "probes": {name: probes[name] for name in PROBE_NAMES},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return document


def verify_runtime_lock(
    lock: Mapping[str, object],
    *,
    distribution: DistributionInfo,
    probes: Mapping[str, str],
) -> None:
    """Reject governed execution when the installed runtime drifted.

    Args:
        lock: A previously written runtime-lock document.
        distribution: Freshly inspected artifact metadata.
        probes: Freshly computed probe statuses.

    Raises:
        CyranoError: ``RUNTIME_HASH_MISMATCH`` on artifact drift,
            ``RUNTIME_PYTHON_CHANGED`` on interpreter drift, or
            ``RUNTIME_LOCK_INCOMPLETE`` when the lock does not cover
            every required probe.
    """
    recorded = lock.get("artifact_hashes")
    digests = (
        {item.get("sha256") for item in recorded if isinstance(item, dict)}
        if isinstance(recorded, list)
        else set()
    )
    if distribution.record_digest not in digests:
        raise CyranoError("RUNTIME_HASH_MISMATCH", distribution.name)
    if lock.get("python") != sys.version.split()[0]:
        raise CyranoError("RUNTIME_PYTHON_CHANGED", str(lock.get("python")))
    missing = [
        name for name in PROBE_NAMES if probes.get(name) not in STATUS_VALUES
    ]
    recorded_probes = lock.get("probes", {})
    if (
        missing
        or not isinstance(recorded_probes, dict)
        or set(recorded_probes) != set(PROBE_NAMES)
    ):
        raise CyranoError("RUNTIME_LOCK_INCOMPLETE", ", ".join(missing))


def resolve_feature_state(
    feature: Mapping[str, object],
    probes: Mapping[str, Mapping[str, bool]],
    permits: Mapping[str, frozenset[str]],
    *,
    scope: str | None = None,
) -> dict[str, object]:
    """Resolve one feature's five independent availability conditions.

    Args:
        feature: One entry of ``capability-ownership.json`` features.
        probes: ``feature_id -> {"installed": bool, "verified": bool}``
            measured by an owning service; absent entries count as
            uninstalled.
        permits: ``feature_id -> granted scopes``; presence is
            authorization.
        scope: Optional scope being requested now.

    Returns:
        A document conforming to ``contracts/r5/feature-state``.
    """
    feature_id = str(feature.get("id", ""))
    configured = bool(
        feature_id
        and feature.get("code_owner")
        and feature.get("procedure_owner")
        and feature.get("config_owner")
    )
    measurement = probes.get(feature_id, {})
    installed = bool(measurement.get("installed"))
    probe_verified = bool(measurement.get("verified"))
    granted = permits.get(feature_id)
    authorized = granted is not None and (scope is None or scope in granted)
    enabled = bool(feature.get("default_enabled"))
    reasons: list[str] = []
    if not configured:
        reasons.append("NOT_CONFIGURED")
    if not installed:
        reasons.append("NOT_INSTALLED")
    if not probe_verified:
        reasons.append("PROBE_UNVERIFIED")
    if granted is not None and scope is not None and scope not in granted:
        reasons.append("SCOPE_EXPANSION_REQUIRES_APPROVAL")
    elif not authorized:
        reasons.append("UNAUTHORIZED")
    if not enabled:
        reasons.append("DISABLED")
    usable = (
        configured and installed and probe_verified and authorized and enabled
    )
    return {
        "feature_id": feature_id,
        "configured": configured,
        "installed": installed,
        "probe_verified": probe_verified,
        "authorized": authorized,
        "enabled": enabled,
        "usable": usable,
        "blocked_reasons": sorted(set(reasons)),
    }


def resolve_feature_states(
    manifest: Mapping[str, object],
    probes: Mapping[str, Mapping[str, bool]],
    permits: Mapping[str, frozenset[str]],
) -> list[dict[str, object]]:
    """Resolve every declared feature.

    Undeclared or malformed entries are skipped or rejected rather
    than silently enabled.

    Returns:
        One feature-state document per declared feature.

    Raises:
        CyranoError: ``INVALID_OWNERSHIP_MANIFEST`` when ``features``
            is not a list.
    """
    features = manifest.get("features", [])
    if not isinstance(features, list):
        raise CyranoError(
            "INVALID_OWNERSHIP_MANIFEST",
            "features must be an array",
        )
    return [
        resolve_feature_state(
            {str(key): item for key, item in entry.items()},
            probes,
            permits,
        )
        for entry in features
        if isinstance(entry, dict)
    ]


def validate_ownership(
    inventory: Mapping[str, object],
    *,
    exists: Callable[[str], bool] | None = None,
) -> list[str]:
    """Check that enforced responsibilities name real code.

    Args:
        inventory: Parsed ``capability-ownership`` document.
        exists: Optional checker mapping owner paths to real files.

    Returns:
        Stable error codes; empty when ownership is consistent.

    Raises:
        CyranoError: ``INVALID_OWNERSHIP_MANIFEST`` when ``features``
            is not a list.
    """
    errors: list[str] = []
    features = inventory.get("features", [])
    if not isinstance(features, list):
        raise CyranoError(
            "INVALID_OWNERSHIP_MANIFEST",
            "features must be an array",
        )
    for entry in features:
        if not isinstance(entry, dict):
            continue
        fid = str(entry.get("id", "?"))
        for field in ("code_owner", "procedure_owner", "config_owner"):
            value = entry.get(field)
            if not isinstance(value, str) or not value:
                errors.append(f"MISSING_{field.upper()}:{fid}")
            elif (
                field != "procedure_owner"
                and exists is not None
                and not exists(value)
            ):
                errors.append(f"MISSING_OWNER_FILE:{value}")
        if "code" not in str(entry.get("enforcement", "")):
            errors.append(f"PROMPT_ONLY_ENFORCEMENT:{fid}")
        if type(entry.get("default_enabled")) is not bool:
            errors.append(f"INVALID_DEFAULT_FLAG:{fid}")
    return errors


def doctor(
    *,
    distribution_name: str = "deepagents-code",
    impls: Mapping[str, ProbeImpl] = DEFAULT_PROBES,
) -> dict[str, object]:
    """Report the real installation state.

    Bootstrap verdicts stay partial; nothing is claimed as verified
    without an executed probe.

    Args:
        distribution_name: Distribution to inspect.
        impls: Probe implementations; injectable for tests.

    Returns:
        A report with ``verdict`` in ``missing``,
        ``unsupported_runtime``, ``verified``, or ``bootstrap_only``
        plus a ``governed_ready`` flag that is true only when every
        required probe is verified.

    Raises:
        CyranoError: Propagates inspection failures other than a
            missing distribution.
    """
    try:
        dist = inspect_installed_distribution(distribution_name)
        distribution: dict[str, object] = {
            "name": dist.name,
            "version": dist.version,
            "editable": dist.editable,
            "record_digest": dist.record_digest,
            "status": "installed",
        }
    except CyranoError as exc:
        if exc.code == "DISTRIBUTION_MISSING":
            return {
                "distribution": {
                    "name": distribution_name,
                    "status": "missing",
                },
                "probes": dict.fromkeys(PROBE_NAMES, "not_tested"),
                "verdict": "missing",
                "governed_ready": False,
                "install_required": True,
            }
        raise
    reports = [
        run_compatibility_probe(name, impls=impls) for name in PROBE_NAMES
    ]
    statuses = {report.name: report.status for report in reports}
    if any(report.status in {"unsupported", "failed"} for report in reports):
        verdict = "unsupported_runtime"
    elif all(report.status == "verified" for report in reports):
        verdict = "verified"
    else:
        verdict = "bootstrap_only"
    return {
        "distribution": distribution,
        "probes": statuses,
        "verdict": verdict,
        "governed_ready": verdict == "verified",
        "install_required": False,
    }
