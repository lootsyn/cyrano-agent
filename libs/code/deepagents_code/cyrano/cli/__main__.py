"""Offline status and demo commands; they never launch a model."""

import argparse
import json

from deepagents_code.cyrano.context.compiler import Block, compile_context
from deepagents_code.cyrano.dcode.adapter import runtime_status
from deepagents_code.cyrano.improvement.classification import classify


def main() -> int:
    """Run a documented offline command; return an explicit status."""
    parser = argparse.ArgumentParser(prog="cyrano")
    parser.add_argument(
        "command", choices=["status", "demo-context", "demo-impact"]
    )
    args = parser.parse_args()
    if args.command == "status":
        result = runtime_status()
    elif args.command == "demo-context":
        blocks = [
            Block("constitution", 0, "Verify before reporting completion.")
        ]
        a = compile_context(blocks, {"task": "first"})
        b = compile_context(blocks, {"task": "second"})
        result = {
            "stable_prefix_equal": a.stable_digest == b.stable_digest,
            "provider_cache_hit": None,
            "wire_observed": False,
            "sample_kind": "offline_demonstration",
        }
    else:
        value = classify(
            ["skills/verify/SKILL.md"],
            input_semantics_unchanged=False,
            policy_ir_validated=False,
        )
        result = {
            "path": value.path,
            "effect_class": value.effect_class,
            "requires_live": value.requires_live,
            "sample_kind": "offline_demonstration",
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
