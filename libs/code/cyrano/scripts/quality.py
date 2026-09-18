"""Run native quality checks without installs or silent passes."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT.parent


def main() -> int:
    """Write actual results; unavailable pinned tools remain blocked."""
    audit_run = subprocess.run(
        [sys.executable, str(ROOT / "scripts/style_audit.py")],
        text=True,
        capture_output=True,
        check=False,
    )
    audit = audit_run.returncode
    (ROOT / "evidence/style-audit.stdout.txt").write_text(
        audit_run.stdout, encoding="utf-8"
    )
    (ROOT / "evidence/style-audit.stderr.txt").write_text(
        audit_run.stderr, encoding="utf-8"
    )
    found = {name: shutil.which(name) for name in ("ruff", "ty")}
    missing = [name for name, value in found.items() if value is None]
    report = {
        "kind": "source_native_quality_preparation",
        "status": "blocked",
        "missing": missing,
        "results": [],
        "tools": [],
        "line_audit_exit": audit,
        "full_PEP8_compliance_claimed": False,
        "note": "Executable identities require WP00 runtime-lock review.",
    }
    for name, value in found.items():
        if value:
            path = Path(value).resolve()
            ver = subprocess.run(
                [str(path), "--version"],
                text=True,
                capture_output=True,
                check=False,
            )
            report["tools"].append(
                {
                    "name": name,
                    "path": str(path),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "version": ver.stdout.strip(),
                }
            )
    if not missing:
        scope = [
            "deepagents_code/cyrano",
            "tests/unit_tests/cyrano",
            "cyrano/scripts",
            "cyrano/plugins",
        ]
        config = "cyrano/configs/quality/ruff.toml"
        commands = [
            [found["ruff"], "format", "--check", "--config", config, *scope],
            [found["ruff"], "check", "--config", config, *scope],
            [found["ty"], "check", "deepagents_code/cyrano"],
        ]
        for number, argv in enumerate(commands):
            run = subprocess.run(
                argv, cwd=CODE, text=True, capture_output=True, check=False
            )
            stdout = ROOT / f"evidence/quality-{number}.stdout.txt"
            stderr = ROOT / f"evidence/quality-{number}.stderr.txt"
            stdout.write_text(run.stdout, encoding="utf-8")
            stderr.write_text(run.stderr, encoding="utf-8")
            report["results"].append(
                {
                    "argv": argv,
                    "cwd": str(CODE),
                    "exit_code": run.returncode,
                    "stdout_sha256": hashlib.sha256(
                        run.stdout.encode()
                    ).hexdigest(),
                    "stderr_sha256": hashlib.sha256(
                        run.stderr.encode()
                    ).hexdigest(),
                }
            )
        report["status"] = (
            "passed"
            if audit == 0
            and all(r["exit_code"] == 0 for r in report["results"])
            else "failed"
        )
    (ROOT / "evidence/quality.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 2 if missing else (0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
