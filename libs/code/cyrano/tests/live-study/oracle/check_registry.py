"""Trusted evaluator for the widgetbox convention.

Every widgetbox module other than ``__init__`` and ``registry`` must
be listed in ``registry.REGISTERED`` and carry a module docstring;
every registered name must name a module that exists. This file
lives outside the agent-editable scope; the model cannot edit the
oracle. Usage: ``python check_registry.py <repo-root>`` — exit 0
pass, 1 convention violation, 2 usage error.
"""

import ast
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    """Evaluate the convention; print the violated rule, if any."""
    if len(argv) != 2:
        return 2
    root = Path(argv[1])
    tree = ast.parse((root / "widgetbox" / "registry.py").read_text())
    registered: set[str] = set()
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and getattr(node.targets[0], "id", "") == "REGISTERED"
        ):
            registered = set(ast.literal_eval(node.value))
    modules = {
        p.stem
        for p in (root / "widgetbox").glob("*.py")
        if p.stem not in {"__init__", "registry"}
    }
    missing = sorted(modules - registered)
    if missing:
        print(f"UNREGISTERED_MODULE: {missing[0]}")
        return 1
    stale = sorted(registered - modules)
    if stale:
        print(f"STALE_REGISTRATION: {stale[0]}")
        return 1
    undocumented = sorted(
        m
        for m in modules
        if not ast.get_docstring(
            ast.parse((root / "widgetbox" / f"{m}.py").read_text())
        )
    )
    if undocumented:
        print(f"UNDOCUMENTED_MODULE: {undocumented[0]}")
        return 1
    print("CONVENTION_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
