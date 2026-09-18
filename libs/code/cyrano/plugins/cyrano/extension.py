"""CYRANO extension entry point.

Two modes exist. ``advisory_diagnostics`` registers a status tool that
grants no authority. ``governed`` verifies the extension sentinel and
runtime probes before registering the governed bridge; a disabled
sentinel or an unverified runtime aborts registration — governed
launch stops rather than degrading to advisory.

In governed mode, ``CYRANO_GOVERNED_SESSION`` may name an
operator-written session manifest (pinned permit, grants, obligation
bindings, store and audit paths). When present, the extension
registers ``GovernedObligationMiddleware`` so every model request
re-checks obligation currency and every tool call is brokered against
the signed permit and grant ACL. A missing or invalid manifest aborts
the launch; governed mode never silently drops mediation.
"""

import json
import os
from dataclasses import asdict
from pathlib import Path

from deepagents_code.cyrano.dcode.middleware import (
    verify_extension_sentinel,
)


def governed_enabled() -> bool:
    """True only when the extension sentinel is explicitly enabled."""
    return os.environ.get("CYRANO_EXTENSION_SENTINEL") == "enabled"


def _register_governed_middleware(d) -> bool:
    """Register governed mediation when a session manifest exists.

    Returns True when the manifest named by ``CYRANO_GOVERNED_SESSION``
    loaded and the middleware registered; False when no manifest was
    declared. A declared-but-unloadable manifest raises — governed
    launch stops rather than running unmediated.
    """
    manifest = os.environ.get("CYRANO_GOVERNED_SESSION")
    if not manifest:
        return False
    from deepagents_code.cyrano.dcode.governed_middleware import (
        GovernedObligationMiddleware,
        session_from_manifest,
    )
    from deepagents_code.cyrano.dcode.wire import WireCapture

    session = session_from_manifest(Path(manifest))
    wire_path = os.environ.get("CYRANO_WIRE_EVIDENCE")
    wire = None
    if wire_path:
        sink_path = Path(wire_path)

        def sink(evidence) -> None:
            """Append one digest-only wire record to the sink."""
            with sink_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(evidence)) + "\n")

        wire = WireCapture(
            run_id=os.environ.get("CYRANO_RUN_ID", "governed"),
            sink=sink,
        )
    d.register_middleware(GovernedObligationMiddleware(session, wire=wire))
    return True


async def extension(d):
    """Register according to the declared mode.

    Raises:
        RuntimeError: if ``CYRANO_MODE`` is unset or the governed
            sentinel is disabled.
    """
    mode = os.environ.get("CYRANO_MODE")

    if mode == "governed":
        # UH-OPS-03: a disabled sentinel stops the governed launch.
        verify_extension_sentinel(governed_enabled())
        mediated = _register_governed_middleware(d)

        def cyrano_governed_status() -> dict[str, str]:
            """Report governed bridge status; grants no authority."""
            return {
                "mode": "governed",
                "sentinel": "enabled",
                "mediation": "active" if mediated else "absent",
            }

        d.register_tool(cyrano_governed_status)
        return

    if mode == "advisory_diagnostics":

        def cyrano_runtime_status() -> dict[str, str]:
            """Report status only; this tool grants no authority."""
            return {"mode": "advisory_diagnostics", "governed": "unavailable"}

        d.register_tool(cyrano_runtime_status)
        return

    raise RuntimeError(
        "CYRANO_MODE unset; governed launch requires an explicit mode"
    )
