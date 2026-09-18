"""Semantic review of docstrings and comments.

Compares documented names, returns, and raises clauses against the
actual function body — lint-clean docstrings can still lie. Private
helpers enter the inventory when they carry docstrings; the manifest
records the inclusion rule rather than a comment-count target.
"""

import ast
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from deepagents_code.cyrano.context.doc_audit import _documented_args
from deepagents_code.cyrano.contracts.types import CyranoError


@dataclass(frozen=True, slots=True)
class SymbolEntry:
    """One inventoried callable with its declared interface facts."""

    path: str
    name: str
    public: bool
    has_docstring: bool
    params: tuple[str, ...]
    returns_none: bool
    raises: bool


@dataclass(frozen=True, slots=True)
class SymbolInventory:
    """Digest-bound inventory of symbols selected for review."""

    entries: tuple[SymbolEntry, ...]
    inclusion_rule: str


@dataclass(frozen=True, slots=True)
class DocFinding:
    """One contradiction between a docstring and its body."""

    path: str
    symbol: str
    code: str
    detail: str


@dataclass(frozen=True, slots=True)
class IndependentReview:
    """Semantic-review artifact over an inventory."""

    findings: tuple[DocFinding, ...]
    symbol_count: int
    inclusion_rule: str


def inventory_public_symbols(
    paths: Iterable[Path],
) -> SymbolInventory:
    """Collect public functions plus documented private helpers.

    Inclusion rule: every public ``def``, and any private ``def`` that
    carries a docstring. No comment-count target exists.
    """
    entries: list[SymbolEntry] = []
    for path in sorted(paths):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            public = not node.name.startswith("_")
            doc = ast.get_docstring(node)
            if not public and not doc:
                continue
            args = (*node.args.args, *node.args.kwonlyargs)
            params = tuple(a.arg for a in args if a.arg not in {"self", "cls"})
            ret = node.returns
            returns_none = isinstance(ret, ast.Constant) and (
                ret.value is None
            )
            raises = any(
                isinstance(inner, ast.Raise) for inner in ast.walk(node)
            )
            entries.append(
                SymbolEntry(
                    path=str(path),
                    name=node.name,
                    public=public,
                    has_docstring=doc is not None,
                    params=params,
                    returns_none=returns_none,
                    raises=raises,
                )
            )
    rule = "public defs + documented private defs"
    return SymbolInventory(tuple(entries), rule)


def check_docstring_signature(path: Path) -> tuple[DocFinding, ...]:
    """Flag docstrings contradicting the signature they describe."""
    findings: list[DocFinding] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        raise CyranoError(
            "INPUT_INVALID", f"unparseable source {path}: {exc}"
        ) from exc
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        doc = ast.get_docstring(node)
        if not doc:
            if not node.name.startswith("_"):
                findings.append(
                    DocFinding(
                        str(path),
                        node.name,
                        "DOCSTRING_MISSING",
                        "public function without a docstring",
                    )
                )
            continue
        first = doc.strip().splitlines()[0].strip().lower()
        if first in {"todo", node.name.lower(), f"{node.name.lower()}."}:
            findings.append(
                DocFinding(
                    str(path),
                    node.name,
                    "DOCSTRING_PLACEHOLDER",
                    "docstring is a placeholder or repeats the name",
                )
            )
        if "noqa" in doc:
            findings.append(
                DocFinding(
                    str(path),
                    node.name,
                    "SUPPRESSION_IN_TEXT",
                    "docstring text contains a suppression directive",
                )
            )
        args = (*node.args.args, *node.args.kwonlyargs)
        declared = {a.arg for a in args}
        declared |= {a.arg for a in (node.args.posonlyargs or [])}
        documented = _documented_args(doc)
        for name in sorted(documented - declared - {"self", "cls"}):
            findings.append(
                DocFinding(
                    str(path),
                    node.name,
                    "DOCSTRING_UNKNOWN_ARG",
                    f"documents unknown parameter {name!r}",
                )
            )
        ret = node.returns
        if (
            isinstance(ret, ast.Constant)
            and ret.value is None
            and "Returns:" in doc
        ):
            findings.append(
                DocFinding(
                    str(path),
                    node.name,
                    "DOCSTRING_RETURN_MISMATCH",
                    "annotated -> None but documents a return",
                )
            )
        has_raise = any(
            isinstance(inner, ast.Raise) for inner in ast.walk(node)
        )
        if has_raise and "Raises:" not in doc:
            findings.append(
                DocFinding(
                    str(path),
                    node.name,
                    "DOCSTRING_MISSING_RAISES",
                    "raises without a Raises: section",
                )
            )
    return tuple(findings)


def run_semantic_review(
    paths: Iterable[Path],
) -> IndependentReview:
    """Inventory the paths, then check each symbol's docstring."""
    path_list = sorted(paths)
    inventory = inventory_public_symbols(path_list)
    findings: list[DocFinding] = []
    reviewed = {e.path for e in inventory.entries}
    for path in path_list:
        if str(path) in reviewed:
            findings.extend(check_docstring_signature(path))
    return IndependentReview(
        tuple(findings), len(inventory.entries), inventory.inclusion_rule
    )


_AMBIGUOUS = re.compile(r"^(data|stuff|thing|obj|temp|tmp)\d*$")


def ambiguous_name_findings(path: Path) -> tuple[DocFinding, ...]:
    """Flag form-valid but meaningless names lint cannot see.

    ``data1`` and ``do_stuff`` pass every naming rule yet carry no
    domain meaning; the semantic review names them explicitly.
    """
    findings: list[DocFinding] = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _AMBIGUOUS.match(node.name) or node.name == "do_stuff":
            findings.append(
                DocFinding(
                    str(path),
                    node.name,
                    "AMBIGUOUS_NAME",
                    f"name {node.name!r} carries no domain meaning",
                )
            )
    return tuple(findings)
