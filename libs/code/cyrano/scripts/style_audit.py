"""Report line-length findings, not full PEP8 results."""

import ast
import io
import json
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inspect_text(text: str, filename: str) -> list[dict]:
    """Locate long code, comments and docstring lines."""
    doc_lines = set()
    syntax = ast.parse(text, filename=filename)
    for node in ast.walk(syntax):
        if (
            isinstance(
                node,
                (
                    ast.Module,
                    ast.ClassDef,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and node.body
        ):
            first = node.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                doc_lines.update(range(first.lineno, first.end_lineno + 1))
    comments = {}
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.COMMENT:
            comments[token.start[0]] = token.start[1]
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        kind = (
            "docstring"
            if number in doc_lines
            else ("comment" if number in comments else "code")
        )
        limit = 72 if kind != "code" else 79
        if len(line) > limit:
            findings.append(
                {
                    "path": filename,
                    "line": number,
                    "kind": kind,
                    "length": len(line),
                    "limit": limit,
                    "status": "requires_fix_or_reviewed_specific_exception",
                }
            )
    return findings


def main() -> int:
    """Persist real baseline findings without rewriting source files."""
    findings = []
    count = 0
    for folder in (
        ROOT.parent / "deepagents_code/cyrano",
        ROOT.parent / "tests/unit_tests/cyrano",
        ROOT / "scripts",
        ROOT / "plugins",
    ):
        for path in sorted(folder.rglob("*.py")):
            count += 1
            findings.extend(
                inspect_text(
                    path.read_text(encoding="utf-8"),
                    str(path.relative_to(ROOT.parent)),
                )
            )
    report = {
        "kind": "executed_line_length_migration_audit",
        "source_files": count,
        "finding_count": len(findings),
        "status": "findings_require_work" if findings else "no_findings",
        "success": not findings,
        "findings": findings,
        "limits": {"code": 79, "comments_and_docstrings": 72},
        "limitations": [
            "not native Ruff/ty or semantic documentation review",
            "not full PEP8 verification",
            "physical lines; reviewed URL/string exceptions not inferred",
        ],
    }
    (ROOT / "evidence/style-audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "findings"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
