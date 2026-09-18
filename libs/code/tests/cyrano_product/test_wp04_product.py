"""WP04 product tests: explicit composition and lifecycle.

PLUGIN-CONFIG / PLUGIN-PARTIAL / PLUGIN-DISPOSE plus the WP04
implementation obligations run against the real Registry and
composition resolver — no skip, no stub pass.
"""

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.plugins.composition import (
    KNOWN_COMPONENTS,
    close_components,
    resolve_config,
    start_components,
)
from deepagents_code.cyrano.plugins.registry import Registry


def _config(**overrides):
    base = {
        "schema_version": "1.0",
        "mode": "governed",
        "enabled": True,
        "components": ["control", "memory"],
    }
    base.update(overrides)
    return base


class Handle:
    """Test double recording close order; real close() semantics."""

    def __init__(self, name: str, log: list[str], fail=False):
        """Bind a handle to the shared close log."""
        self.name = name
        self.log = log
        self.fail = fail

    def close(self) -> None:
        self.log.append(self.name)
        if self.fail:
            raise RuntimeError(f"{self.name} dispose failed")


class TestPluginConfig:
    """PLUGIN-CONFIG: early explicit failure at resolution."""

    def test_unknown_component_rejected(self):
        with pytest.raises(CyranoError) as exc:
            resolve_config(_config(components=["control", "nope"]))
        assert exc.value.code == "UNKNOWN_COMPONENT"

    def test_cycle_rejected(self):
        cfg = _config(
            components=[
                {"name": "control", "depends_on": ["memory"]},
                {"name": "memory", "depends_on": ["control"]},
            ]
        )
        with pytest.raises(CyranoError) as exc:
            resolve_config(cfg)
        assert exc.value.code == "PLUGIN_CYCLE"

    def test_code_expression_config_rejected(self):
        cfg = _config(
            components=[
                {"name": "control", "module": "os.system"},
            ]
        )
        with pytest.raises(CyranoError) as exc:
            resolve_config(cfg)
        assert exc.value.code == "RUNTIME_DISCOVERY_REQUIRED"

    def test_unknown_top_level_field_rejected(self):
        with pytest.raises(CyranoError) as exc:
            resolve_config(_config(hooks=["./evil.py"]))
        assert exc.value.code == "PLUGIN_CONFIG"

    def test_future_schema_rejected(self):
        with pytest.raises(CyranoError) as exc:
            resolve_config(_config(schema_version="2.0"))
        assert exc.value.code == "UNSUPPORTED_CONFIG_VERSION"

    def test_dependency_order_resolved(self):
        comp = resolve_config(
            _config(
                components=[
                    {"name": "memory", "depends_on": ["control"]},
                    "control",
                ]
            )
        )
        assert comp.order == ("control", "memory")


class TestPartialStartup:
    """PLUGIN-PARTIAL: registered effects removed on failure."""

    def test_second_setup_failure_rolls_back(self):
        registry = Registry()
        calls: list[str] = []

        def control_factory(reg: Registry):
            reg.load(
                "control",
                _Plugin(lambda r: r("svc.control", 1), calls, "control"),
            )
            return Handle("control", calls)

        def memory_factory(reg: Registry):
            reg.load(
                "memory",
                _Plugin(
                    lambda r: (
                        r("svc.memory", 2),
                        (_ for _ in ()).throw(RuntimeError("boom")),
                    )[1],
                    calls,
                    "memory",
                ),
            )
            return Handle("memory", calls)

        comp = resolve_config(_config())
        with pytest.raises(RuntimeError):
            start_components(
                comp,
                {"control": control_factory, "memory": memory_factory},
                registry,
            )
        assert registry.services == {}
        assert "control" in calls  # earlier handle closed


class _Plugin:
    """Minimal Plugin: register contributions, return a disposer."""

    def __init__(self, setup_fn, log, name):
        self._setup = setup_fn
        self._log = log
        self._name = name

    def setup(self, register):
        self._setup(register)

        def dispose():
            self._log.append(f"dispose:{self._name}")

        return dispose


class TestDispose:
    """PLUGIN-DISPOSE: remaining teardown continues; errors report."""

    def test_failed_disposer_reports_and_continues(self):
        log: list[str] = []
        comp = resolve_config(_config())
        handles = {
            "control": Handle("control", log),
            "memory": Handle("memory", log, fail=True),
        }
        report = close_components(handles, comp.order)
        assert log == ["memory", "control"]  # reverse order
        assert "memory" in report.errors
        assert report.closed == ["control"]

    def test_clean_teardown_reverse_order(self):
        log: list[str] = []
        comp = resolve_config(
            _config(components=["control", "memory", "context"])
        )
        handles = {n: Handle(n, log) for n in ("control", "memory", "context")}
        close_components(handles, comp.order)
        assert log == ["context", "memory", "control"]


class TestObligations:
    """WP04-I01/I02/I03: composite digest, no import-time work."""

    def test_exact_config_digest(self):
        a = resolve_config(_config())
        b = resolve_config(_config())
        assert a.config_digest == b.config_digest
        changed = resolve_config(_config(components=["control"]))
        assert changed.config_digest != a.config_digest

    def test_fixed_inventory(self):
        assert "control" in KNOWN_COMPONENTS
        with pytest.raises(CyranoError):
            resolve_config(_config(components=["__import__"]))

    def test_registry_unload_reverse_order(self):
        registry = Registry()
        order: list[str] = []
        for pid in ("p1", "p2", "p3"):
            registry.load(pid, _Plugin(lambda r: None, order, pid))
        registry.close()
        assert order == ["dispose:p3", "dispose:p2", "dispose:p1"]

    def test_close_reports_all_failures(self):
        registry = Registry()
        log: list[str] = []
        for pid in ("a", "b"):
            registry.load(pid, _FailingDispose(pid, log))
        with pytest.raises(ExceptionGroup):
            registry.close()
        assert log == ["dispose:b", "dispose:a"]


class _FailingDispose:
    """Plugin whose setup succeeds but whose disposer raises."""

    def __init__(self, name: str, log: list[str]):
        self._name = name
        self._log = log

    def setup(self, register):
        def dispose():
            self._log.append(f"dispose:{self._name}")
            raise RuntimeError(self._name)

        return dispose
