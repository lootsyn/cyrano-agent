"""Explicit component composition: resolve, start, reverse teardown.

The composition never discovers or imports project extensions itself;
config names must map to programmatically supplied factories, so
extension/hook/MCP trust stays a separate runtime-discovery decision.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.plugins.registry import Registry

KNOWN_COMPONENTS = frozenset(
    {
        "control",
        "dcode_bridge",
        "action_broker",
        "sandbox",
        "interview",
        "workflow",
        "memory",
        "context",
        "learning",
        "evaluation",
        "release",
        "observability",
    }
)

ALLOWED_TOP_LEVEL = {
    "schema_version",
    "mode",
    "enabled",
    "requires_runtime_compatibility",
    "components",
    "learning_enabled",
    "auto_promotion_enabled",
    "canary_percent",
    "remote_trace_export",
    "same_principal_isolation_allowed",
    "unverified_fallback_allowed",
}

DISCOVERY_KEYS = {
    "module",
    "entry_point",
    "import",
    "path",
    "plugin_dir",
    "auto_load",
}


@dataclass(frozen=True, slots=True)
class ComponentSpec:
    """One resolved component: fixed name plus declared dependencies."""

    name: str
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResolvedComposition:
    """Immutable resolution result bound to an exact config digest."""

    config_digest: str
    mode: str
    enabled: bool
    order: tuple[str, ...]
    specs: tuple[ComponentSpec, ...]


@dataclass(slots=True)
class CleanupReport:
    """Reverse-teardown outcome; errors are reported, never hidden."""

    closed: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


def _component_spec(entry: object) -> ComponentSpec:
    """Normalize one config entry; reject code/discovery references."""
    if isinstance(entry, str):
        return ComponentSpec(name=entry)
    if not isinstance(entry, Mapping):
        raise CyranoError(
            "INVALID_COMPONENT",
            "component entries must be names or {name, depends_on} objects",
        )
    unknown = set(entry) - {"name", "depends_on"}
    if unknown & DISCOVERY_KEYS:
        raise CyranoError(
            "RUNTIME_DISCOVERY_REQUIRED",
            "module/entry-point references need the separate "
            "runtime discovery step; config cannot auto-trust code",
        )
    if unknown:
        raise CyranoError(
            "PLUGIN_CONFIG", f"unknown component fields {unknown}"
        )
    name = entry.get("name")
    if not isinstance(name, str) or not name:
        raise CyranoError("PLUGIN_CONFIG", "component name must be a string")
    deps = entry.get("depends_on", [])
    if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
        raise CyranoError(
            "PLUGIN_CONFIG", "depends_on must be a list of names"
        )
    dep_names = tuple(d for d in deps if isinstance(d, str))
    return ComponentSpec(name=name, depends_on=dep_names)


def _topo_order(specs: list[ComponentSpec]) -> tuple[str, ...]:
    """Dependency order; cycles fail early and explicitly."""
    names = {s.name for s in specs}
    for spec in specs:
        for dep in spec.depends_on:
            if dep not in names:
                raise CyranoError(
                    "UNKNOWN_COMPONENT",
                    f"{spec.name} depends on unconfigured {dep}",
                )
    order: list[str] = []
    state: dict[str, int] = {}

    def visit(name: str) -> None:
        mark = state.get(name, 0)
        if mark == 1:
            raise CyranoError("PLUGIN_CYCLE", name)
        if mark == 2:
            return
        state[name] = 1
        spec = next(s for s in specs if s.name == name)
        for dep in spec.depends_on:
            visit(dep)
        state[name] = 2
        order.append(name)

    for spec in specs:
        visit(spec.name)
    return tuple(order)


def resolve_config(config: Mapping[str, object]) -> ResolvedComposition:
    """Validate a profile config into a resolved composition.

    Unknown fields, unknown components, discovery references, and
    dependency cycles all fail before anything is started.
    """
    unknown = set(config) - ALLOWED_TOP_LEVEL
    if unknown:
        raise CyranoError("PLUGIN_CONFIG", f"unknown config fields {unknown}")
    if config.get("schema_version") != "1.0":
        raise CyranoError(
            "UNSUPPORTED_CONFIG_VERSION",
            str(config.get("schema_version")),
        )
    components = config.get("components")
    if not isinstance(components, list) or not components:
        raise CyranoError(
            "PLUGIN_CONFIG", "components must be a non-empty list"
        )
    specs = [_component_spec(entry) for entry in components]
    names = [s.name for s in specs]
    if len(set(names)) != len(names):
        raise CyranoError("DUPLICATE_COMPONENT", "components")
    for spec in specs:
        if spec.name not in KNOWN_COMPONENTS:
            raise CyranoError("UNKNOWN_COMPONENT", spec.name)
    return ResolvedComposition(
        config_digest=digest(dict(config)),
        mode=str(config.get("mode", "governed")),
        enabled=bool(config.get("enabled", False)),
        order=_topo_order(specs),
        specs=tuple(specs),
    )


def start_components(
    composition: ResolvedComposition,
    factories: Mapping[str, Callable[[Registry], object]],
    registry: Registry | None = None,
) -> dict[str, object]:
    """Start components in dependency order via supplied factories.

    A mid-startup failure closes previously started handles in
    reverse order and propagates the failure (PLUGIN-PARTIAL).
    Factories are the only binding path; config never names code.
    """
    registry = registry if registry is not None else Registry()
    baseline = set(registry._loaded)
    started: dict[str, object] = {}
    try:
        for name in composition.order:
            factory = factories.get(name)
            if factory is None:
                raise CyranoError(
                    "MISSING_FACTORY", f"no factory bound for {name}"
                )
            started[name] = factory(registry)
    except BaseException:
        for prior in reversed(list(started)):
            _safe_close(started[prior])
        added = [pid for pid in registry._loaded if pid not in baseline]
        for plugin_id in reversed(added):
            registry.unload(plugin_id)
        raise
    return started


def _safe_close(handle: object) -> None:
    close = getattr(handle, "close", None)
    if callable(close):
        close()


def close_components(
    handles: Mapping[str, object],
    order: tuple[str, ...],
) -> CleanupReport:
    """Dispose in reverse order; collect all errors (PLUGIN-DISPOSE)."""
    report = CleanupReport()
    for name in reversed(order):
        handle = handles.get(name)
        if handle is None:
            continue
        try:
            _safe_close(handle)
            report.closed.append(name)
        except Exception as exc:  # noqa: BLE001 - report, don't stop
            report.errors[name] = str(exc)
    return report
