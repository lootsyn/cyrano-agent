"""Seal the WP23 live-effectiveness study inputs into a manifest.

Computes real digests over the frozen fixture repo, suite, arm
configurations, route spec, runtime identity and policy, then binds
them through ``seal_experiment`` and writes
``evidence/live-evaluation/manifest.json``. No provider call is made
here — this is preparation, not execution.
"""

import hashlib
import json
import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT.parent
STUDY = ROOT / "tests" / "live-study"
EVIDENCE = ROOT / "evidence" / "live-evaluation"

sys.path.insert(0, str(CODE))
from deepagents_code.cyrano.evaluation.paired import (  # noqa: E402
    seal_experiment,
)


def _digest_bytes(data: bytes) -> str:
    """Hash raw bytes into a sha256:-prefixed digest."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _digest_json(value: object) -> str:
    """Hash a canonical JSON encoding of a mapping."""
    raw = json.dumps(value, sort_keys=True).encode()
    return _digest_bytes(raw)


def _tree_digest(root: Path) -> str:
    """Digest a directory tree by path and content."""
    entries = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            entries[rel] = _digest_bytes(path.read_bytes())
    return _digest_json(entries)


def _runtime_digest() -> str:
    """Pin the runtime identity: python, platform, dcode release."""
    try:
        dcode_version = version("deepagents-code")
    except PackageNotFoundError:
        dcode_version = "editable-workspace"
    wheel = next(
        iter(sorted((CODE / "dist").glob("deepagents_code-*.whl"))),
        None,
    )
    return _digest_json(
        {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "deepagents_code": dcode_version,
            "wheel": wheel.name if wheel else None,
            "wheel_sha256": (
                _digest_bytes(wheel.read_bytes()) if wheel else None
            ),
        }
    )


def build_spec() -> dict[str, object]:
    """Assemble the sealed spec from real input digests."""
    suite = json.loads((STUDY / "suite.json").read_text(encoding="utf-8"))
    route = json.loads((STUDY / "run.json").read_text(encoding="utf-8"))
    baseline = json.loads(
        (STUDY / "arms" / "baseline.json").read_text(encoding="utf-8")
    )
    candidate = json.loads(
        (STUDY / "arms" / "candidate.json").read_text(encoding="utf-8")
    )
    policy_path = ROOT / "configs" / "broker-policy.json"
    return {
        "baseline_digest": _digest_json(baseline),
        "candidate_digest": _digest_json(candidate),
        "suite_digest": _digest_json(
            {
                "suite": suite,
                "repo": _tree_digest(STUDY / "repo"),
                "oracle": _tree_digest(STUDY / "oracle"),
                "overlays": _tree_digest(STUDY / "overlays"),
            }
        ),
        "runtime_digest": _runtime_digest(),
        "plan_digest": _digest_json(route),
        "policy_digest": _digest_bytes(policy_path.read_bytes()),
        "model_digest": _digest_json(route["model"]),
        "route_digest": _digest_json(route["invocation"]),
        "families": list(suite["families"]),
        "holdout": list(suite["holdout"]),
        "budget_units": int(suite["budget"]["budget_units"]),
        "quality_margin": float(suite["quality_margin"]),
        "min_pairs": int(suite["min_pairs"]),
        "nondeterministic_provider": True,
        "changes": [
            "memory/service",
            "improvement/knowledge_lane",
            "kernel/actions",
        ],
    }


def main() -> int:
    """Seal the manifest and write it under live-evaluation."""
    spec = build_spec()
    manifest = seal_experiment(spec)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    suite = json.loads((STUDY / "suite.json").read_text(encoding="utf-8"))
    route = json.loads((STUDY / "run.json").read_text(encoding="utf-8"))
    provider = str(route["model"]["provider"])
    previous = EVIDENCE / "manifest.json"
    supersedes = None
    if previous.is_file():
        old = json.loads(previous.read_text(encoding="utf-8"))
        if old.get("status") == "sealed_not_executed":
            old["status"] = "superseded"
            old["superseded_by"] = "manifest.json"
            archive = EVIDENCE / (
                "manifest.superseded-"
                + str(old["manifest"]["manifest_id"])[:15]
                + ".json"
            )
            archive.write_text(
                json.dumps(old, indent=2) + "\n", encoding="utf-8"
            )
            supersedes = {
                "manifest_id": old["manifest"]["manifest_id"],
                "sealed_manifest_digest": old["sealed_manifest_digest"],
                "archived": archive.name,
            }
    record = {
        "kind": "sealed_experiment_manifest",
        "status": "sealed_not_executed",
        "manifest": {
            field: getattr(manifest, field)
            for field in manifest.__dataclass_fields__
        },
        "inputs": {
            "suite": "tests/live-study/suite.json",
            "route": "tests/live-study/run.json",
            "baseline_arm": "tests/live-study/arms/baseline.json",
            "candidate_arm": "tests/live-study/arms/candidate.json",
            "fixture_repo": "tests/live-study/repo/",
            "overlays": "tests/live-study/overlays/",
            "oracle": "tests/live-study/oracle/",
            "policy": "configs/broker-policy.json",
        },
        "credential_env": str(route["credential_env"]),
        "provider_routing": route.get("provider_routing"),
        "external_effects": [f"paid model calls to provider {provider} only"],
        "limits": {
            "max_runs": int(route["caps"]["max_runs"]),
            "max_model_calls": int(suite["budget"]["max_model_calls"]),
            "max_tokens": int(suite["budget"]["budget_units"]),
            "max_cost_usd": float(suite["budget"]["max_cost_usd"]),
            "timeout_seconds_per_run": int(
                route["caps"]["timeout_seconds_per_run"]
            ),
        },
    }
    if supersedes is not None:
        record["supersedes"] = supersedes
    record["sealed_manifest_digest"] = _digest_json(record["manifest"])
    path = EVIDENCE / "manifest.json"
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"manifest_id: {manifest.manifest_id}")
    print(f"sealed_manifest_digest: {record['sealed_manifest_digest']}")
    print(f"written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
