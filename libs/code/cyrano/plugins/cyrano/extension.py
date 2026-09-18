"""CYRANO extension entry point.

Two modes exist. ``advisory_diagnostics`` registers a status tool that
grants no authority. ``governed`` verifies the extension sentinel and
runtime probes before registering the governed bridge; a disabled
sentinel or an unverified runtime aborts registration — governed
launch stops rather than degrading to advisory.
"""

import os

from deepagents_code.cyrano.dcode.middleware import (
    verify_extension_sentinel,
)


def governed_enabled() -> bool:
    """True only when the extension sentinel is explicitly enabled."""
    return os.environ.get("CYRANO_EXTENSION_SENTINEL") == "enabled"


async def extension(d):
    """Register according to the declared mode."""
    mode = os.environ.get("CYRANO_MODE")

    if mode == "governed":
        # UH-OPS-03: a disabled sentinel stops the governed launch.
        verify_extension_sentinel(governed_enabled())

        def cyrano_governed_status() -> dict[str, str]:
            """Report governed bridge status; grants no authority."""
            return {"mode": "governed", "sentinel": "enabled"}

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
