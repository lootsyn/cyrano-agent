"""Plugin contributions with rollback and reverse-order teardown."""

from collections.abc import Callable
from typing import Protocol

from deepagents_code.cyrano.contracts.types import CyranoError


class Plugin(Protocol):
    """Trusted plugin setup receives a scoped registration function."""

    def setup(
        self, register: Callable[[str, object], None]
    ) -> Callable[[], None]:
        """Register contributions; return an idempotent disposer."""
        ...


class Registry:
    """Minimal boot-time plugin host; not a sandbox or reloader."""

    def __init__(self) -> None:
        """Start with no services or loaded plugins."""
        self.services: dict[str, object] = {}
        self._loaded: dict[str, tuple[list[str], Callable[[], None]]] = {}

    def load(self, plugin_id: str, plugin: Plugin) -> None:
        """Roll back on setup failure; plugins own cleanup."""
        if plugin_id in self._loaded:
            raise CyranoError("DUPLICATE_PLUGIN", plugin_id)
        names: list[str] = []

        def register(name: str, value: object) -> None:
            if name in self.services:
                raise CyranoError("DUPLICATE_SERVICE", name)
            self.services[name] = value
            names.append(name)

        try:
            disposer = plugin.setup(register)
        except BaseException:
            for name in reversed(names):
                del self.services[name]
            raise
        self._loaded[plugin_id] = (names, disposer)

    def unload(self, plugin_id: str) -> None:
        """Remove contributions; disposal failure propagates."""
        record = self._loaded.pop(plugin_id, None)
        if record is None:
            return
        names, dispose = record
        try:
            dispose()
        finally:
            for name in reversed(names):
                self.services.pop(name, None)

    def close(self) -> None:
        """Run disposers in reverse order; report failures."""
        errors: list[Exception] = []
        for plugin_id in reversed(list(self._loaded)):
            try:
                self.unload(plugin_id)
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise ExceptionGroup("plugin teardown failed", errors)
