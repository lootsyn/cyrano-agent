"""Run only the design kit's reference and template checks."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path


def main() -> int:
    """Write an honest machine-readable record of local validation."""
    root = Path(__file__).resolve().parents[1]
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    result = subprocess.run(
        command, cwd=root, capture_output=True, text=True, encoding="utf-8",
        check=False, timeout=60,
    )
    output = root / "evidence"
    output.mkdir(exist_ok=True)
    (output / "kit-validation.stdout.txt").write_text(
        result.stdout, encoding="utf-8"
    )
    (output / "kit-validation.stderr.txt").write_text(
        result.stderr, encoding="utf-8"
    )
    record = {
        "kind": "design_kit_validation_only",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "dependencies": {
            "pydantic": version("pydantic"),
            "jsonschema": version("jsonschema"),
        },
        "argv": command,
        "exit_code": result.returncode,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "not_executed": [
            "Black/Ruff/mypy/Pyright CLI validation",
            "Actual pytest adapter and test observer",
            "Native dcode / real model integration",
            "Governed sandbox and receipt authentication",
            "CI branch protection or remote repository changes",
            "Self-improvement performance experiments",
        ],
    }
    (output / "kit-validation.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
