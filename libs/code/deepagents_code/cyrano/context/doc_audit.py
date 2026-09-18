"""Static docstring-semantics findings for Cyrano source.

A review aid only; it produces findings, not a lint verdict.
"""

from __future__ import annotations

import ast


def _returns_none(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    ret = node.returns
    return isinstance(ret, ast.Constant) and ret.value is None


def _documented_args(doc: str) -> set[str]:
    names: set[str] = set()
    in_args = False
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped.startswith("Args:"):
            in_args = True
            continue
        if in_args and stripped.endswith(":") and " " not in stripped:
            in_args = False
        if in_args and ":" in stripped:
            names.add(stripped.split(":", 1)[0].strip().lstrip("*"))
    return names


def docstring_findings(source: str) -> list[str]:
    """Flag docstrings that contradict the signature they describe.

    A function whose docstring documents a return value while being
    annotated ``-> None``, or that raises without documenting
    ``Raises:``, passes lint yet misleads reviewers; each finding is a
    stable ``CODE:function`` pair.

    Args:
        source: Python source text.

    Returns:
        Sorted finding codes.
    """
    findings: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        doc = ast.get_docstring(node)
        if not doc or node.name.startswith("_"):
            continue
        if _returns_none(node) and "Returns:" in doc:
            findings.append(f"DOCSTRING_RETURN_MISMATCH:{node.name}")
        raises = any(isinstance(inner, ast.Raise) for inner in ast.walk(node))
        if raises and "Raises:" not in doc:
            findings.append(f"DOCSTRING_MISSING_RAISES:{node.name}")
        args = (*node.args.args, *node.args.kwonlyargs)
        declared = {arg.arg for arg in args}
        declared |= {arg.arg for arg in (node.args.posonlyargs or [])}
        documented = _documented_args(doc)
        findings.extend(
            f"DOCSTRING_UNKNOWN_ARG:{node.name}:{name}"
            for name in sorted(documented - declared - {"self", "cls"})
        )
    return sorted(set(findings))
