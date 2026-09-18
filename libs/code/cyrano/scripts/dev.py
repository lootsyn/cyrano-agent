"""Dependency-free dev entry point; commands are explicit."""

import argparse
import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone

from bootstrap import activate

ROOT = activate()


def unit_tests() -> bool:
    """Execute shipped behavior tests; write the actual result."""
    suite = unittest.defaultTestLoader.discover(
        str(ROOT.parent / "tests/unit_tests/cyrano"), pattern="test_*.py"
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {
        "kind": "executed_foundation_tests",
        "python": sys.version,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "success": result.wasSuccessful(),
        "not_covered": [
            "live_dcode",
            "provider_cache",
            "OS_isolation",
            "product_self_improvement_effectiveness",
        ],
    }
    target = ROOT / "evidence/foundation-tests.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return (
        result.testsRun > 0 and not result.skipped and result.wasSuccessful()
    )


def main() -> int:
    """Dispatch checks or read-only demos; never installs packages."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=[
            "test",
            "check",
            "schemas",
            "docs",
            "quality",
            "status",
            "demo-context",
            "demo-impact",
        ],
    )
    args = parser.parse_args()
    if args.command in {"test", "check"}:
        ok = unit_tests()
        if args.command == "check":
            ok = (
                subprocess.call(
                    [sys.executable, str(ROOT / "scripts/check_project.py")]
                )
                == 0
                and ok
            )
            ok = (
                subprocess.call(
                    [sys.executable, str(ROOT / "scripts/check_r5.py")]
                )
                == 0
                and ok
            )
            ok = (
                subprocess.call(
                    [sys.executable, str(ROOT / "scripts/check_integrated.py")]
                )
                == 0
                and ok
            )
        return 0 if ok else 1
    if args.command in {"schemas", "docs", "quality"}:
        script = {
            "schemas": "validate_schemas.py",
            "docs": "build_docs.py",
            "quality": "quality.py",
        }[args.command]
        return subprocess.call(
            [sys.executable, str(ROOT / "scripts" / script)]
        )
    from deepagents_code.cyrano.cli.__main__ import main as cli_main

    sys.argv = ["cyrano", args.command]
    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
