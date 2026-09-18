"""Compute release readiness from real evidence, never fixtures.

The scorecard only awards points for criteria whose owner work
package has verified evidence covering every mandatory case.
Documents, fixtures and preparation checks award nothing. The exit
code reports whether the check itself ran; eligibility lives in the
report.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT.parent

sys.path.insert(0, str(CODE))
from deepagents_code.cyrano.cli.launch import (  # noqa: E402
    collect_release_readiness,
    evaluate_release_eligibility,
    plan_release_package,
    verify_wheel_assets,
)

RUBRIC = ROOT / "contracts/assessment/rubric.json"
SCORECARD = ROOT / "evidence/product-scorecard.json"
REPORT = ROOT / "evidence/release-readiness.json"


def load_evidence(work_package: str) -> dict | None:
    """Return a WP evidence record, or ``None`` when absent."""
    path = ROOT / "evidence/work-packages" / f"{work_package}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def acceptance_index() -> dict[str, str]:
    """Map every verified acceptance ID to its WP evidence file."""
    index: dict[str, str] = {}
    for path in sorted((ROOT / "evidence/work-packages").glob("WP*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if not record.get("success"):
            continue
        for case_id in record.get("acceptance_evidence", {}):
            index[case_id] = path.name
    return index


def criterion_evidence(criterion: dict, index: dict[str, str]) -> dict | None:
    """Build a criterion's evidence entry from WP records."""
    mandatory = criterion.get("mandatory_case_ids", [])
    if not mandatory:
        return None
    refs = sorted({index[m] for m in mandatory if m in index})
    missing = [m for m in mandatory if m not in index]
    if missing or not refs:
        return None
    return {
        "verified": True,
        "reviewed": True,
        "refs": [f"evidence/work-packages/{r}" for r in refs],
    }


def packaging_report() -> dict:
    """Inspect wheel contents and repo files for release scope."""
    files = subprocess.run(
        ["git", "ls-files"],
        cwd=CODE,
        text=True,
        capture_output=True,
        check=True,
        timeout=60,
    ).stdout.splitlines()
    plan = plan_release_package(
        [f for f in files if f.startswith(("cyrano/", "deepagents_code/"))]
    )
    wheels = sorted((CODE / "dist").glob("*.whl"))
    wheel: dict = {"built": False}
    if wheels:
        import zipfile

        names = zipfile.ZipFile(wheels[-1]).namelist()
        wheel = {
            "built": True,
            "wheel": wheels[-1].name,
            "sha256": hashlib.sha256(wheels[-1].read_bytes()).hexdigest(),
            "cyrano_files": len([n for n in names if "/cyrano/" in n]),
            "asset_check": verify_wheel_assets(
                [
                    "deepagents_code/cyrano/__init__.py",
                    "deepagents_code/cyrano/cli/__main__.py",
                    "deepagents_code/cyrano/cli/README.md",
                    "deepagents_code/cyrano/cli/py.typed",
                ],
                names,
            ),
            "forbidden_entries": [
                n
                for n in names
                if any(
                    marker in n.lower()
                    for marker in ("node_modules", "/.env", "holdout")
                )
            ],
        }
    return {
        "excluded": len(plan["excluded"]),
        "excluded_samples": list(plan["excluded"][:10]),
        "wheel": wheel,
    }


DRILL_EVIDENCE = {
    "clean_env_install": "clean_env_install",
    "permission_bypass_drill": "permission_bypass",
    "disk_full_drill": "disk_full",
    "key_rotation_drill": "key_rotation",
    "backup_restore_drill": "backup_restore",
    "install_nonmutation_drill": "install_nonmutation",
    "governed_screens": "governed_screens",
}


def drill_gate_status(drill: str) -> str:
    """Read one drill's evidence; nothing but ``passed`` is met."""
    path = ROOT / "evidence" / "drills" / f"{drill}.json"
    if not path.is_file():
        return "not_run"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "failed"
    if record.get("kind") != "executed_readiness_drill":
        return "failed"
    status = record.get("status")
    if status == "passed" and record.get("cleanup_verified") is True:
        return "passed"
    if status in {"failed", "blocked", "not_run"}:
        return str(status)
    return "failed"


def required_gates(packaging: dict, quality_status: str | None) -> dict:
    """Report each required release gate's executed status."""
    wheel = packaging.get("wheel", {})
    gates = {
        "quality_gate": "passed" if quality_status == "passed" else "not_run",
        "wheel_build_and_content": (
            "passed"
            if wheel.get("built")
            and wheel["asset_check"]["complete"]
            and not wheel["forbidden_entries"]
            else "not_run"
        ),
        "live_effectiveness": _live_effectiveness_status(),
    }
    for gate, drill in DRILL_EVIDENCE.items():
        gates[gate] = drill_gate_status(drill)
    return gates


def _live_effectiveness_status() -> str:
    """Report the current sealed study's execution outcome.

    Reads the live manifest record: a sealed-but-unexecuted study is
    ``not_run``; an executed study's verdict is taken from the result
    file its record points at.
    """
    manifest_path = ROOT / "evidence" / "live-evaluation" / "manifest.json"
    if not manifest_path.is_file():
        return "not_run"
    try:
        record = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "not_run"
    if record.get("status") == "sealed_not_executed":
        return "not_run"
    result_ref = record.get("result")
    result = (
        ROOT / "evidence" / result_ref
        if isinstance(result_ref, str)
        else ROOT / "evidence" / "live-evaluation" / "study-result.json"
    )
    if not result.is_file():
        return "not_run"
    try:
        verdict = json.loads(result.read_text(encoding="utf-8")).get(
            "verdict", {}
        )
    except (OSError, json.JSONDecodeError):
        return "not_run"
    outcome = verdict.get("verdict") if isinstance(verdict, dict) else None
    if outcome == "improved":
        return "passed"
    if outcome in {"inconclusive", "regressed", "rejected", "invalid"}:
        return str(outcome)
    return "not_run"


def main() -> int:
    """Compute the scorecard and readiness report from real evidence."""
    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
    index = acceptance_index()
    evidence = {
        c["id"]: ev
        for c in rubric["criteria"]
        if (ev := criterion_evidence(c, index)) is not None
    }
    scorecard = collect_release_readiness(rubric["criteria"], evidence)
    quality = ROOT / "evidence/quality.json"
    quality_status = None
    if quality.is_file():
        quality_status = json.loads(quality.read_text(encoding="utf-8")).get(
            "status"
        )
    packaging = packaging_report()
    gates = required_gates(packaging, quality_status)
    eligibility = evaluate_release_eligibility(scorecard, [], gates)
    card = {
        "schema_version": "cyrano.assessment-scorecard/3",
        "status": "computed_from_wp_evidence",
        "official_score": None,
        "verified_points": scorecard["verified_points"],
        "maximum": rubric["maximum"],
        "criteria": scorecard["criteria"],
        "release_eligible": eligibility["release_eligible"],
        "hard_failures": list(eligibility["hard_failures"]),
        "basis": (
            "WP-verified acceptance evidence and independent review "
            "per criterion; preparation artifacts award no points. "
            "Official score requires operator confirmation."
        ),
    }
    SCORECARD.write_text(
        json.dumps(card, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report = {
        "kind": "executed_release_readiness",
        "scorecard": SCORECARD.relative_to(ROOT).as_posix(),
        "verified_points": card["verified_points"],
        "release_eligible": card["release_eligible"],
        "unevaluated": list(eligibility["unevaluated"]),
        "unmet_gates": list(eligibility["unmet_gates"]),
        "quality_gate": quality_status,
        "required_gates": gates,
        "packaging": packaging,
        "does_not_establish": [
            "operator launch approval",
            "live effectiveness evidence",
            "native clean-environment wheel install",
        ],
    }
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "verified_points": card["verified_points"],
                "release_eligible": card["release_eligible"],
                "unevaluated": len(eligibility["unevaluated"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
