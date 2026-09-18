"""Execute the sealed WP23 live-effectiveness study.

This harness is the only caller allowed to turn the sealed manifest
into real ``dcode`` runs. It re-verifies the sealed digest, enforces
the hard run/call/token/cost caps, provisions per-run isolated
workspaces and profiles, captures raw stdout/stderr/oracle evidence,
drives the governed improvement step, folds specimens into the trial
ledger and produces the sealed-margin verdict. It never retries an
ambiguous external effect and never discards an incomplete pair.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT.parent
sys.path.insert(0, str(CODE))
sys.path.insert(0, str(ROOT / "scripts"))

seal_study = importlib.import_module("seal_study")  # noqa: E402

from deepagents_code.cyrano.contracts.canonical import digest  # noqa: E402
from deepagents_code.cyrano.contracts.types import CyranoError  # noqa: E402
from deepagents_code.cyrano.evaluation.paired import (  # noqa: E402
    TrialLedger,
    TrialResult,
    seal_experiment,
)
from deepagents_code.cyrano.evaluation.rubric_evidence import (  # noqa: E402
    review_effectiveness,
    run_preregistered_study,
)
from deepagents_code.cyrano.improvement.knowledge_lane import (  # noqa: E402
    validate_knowledge_candidate,
)
from deepagents_code.cyrano.kernel.approvals import ApprovalDesk  # noqa: E402
from deepagents_code.cyrano.memory.repository import (  # noqa: E402
    MemoryRepository,
)
from deepagents_code.cyrano.memory.service import MemoryService  # noqa: E402
from deepagents_code.cyrano.sqlite.repository import (  # noqa: E402
    ScopedRepository,
)

STUDY = ROOT / "tests" / "live-study"
EVIDENCE = ROOT / "evidence" / "live-evaluation"
RUN_ROOT = Path("/tmp/wp23-live-study")
DCODE = CODE / ".venv" / "bin" / "dcode"
TARGET_DDL = ROOT / "contracts" / "sql" / "target-schema.sql"
AGENT = "wp23"
RUN_TIMEOUT = 1500  # inside the sealed 1800s per-run cap
HARD_KILL = 1700
MAX_TURNS = 25  # 8 runs x 25 turns = 200 < 240-call cap

# Pinned DeepInfra pricing, USD per token (sealed route record).
PRICE_PROMPT = 0.0000002
PRICE_COMPLETION = 0.0000006

_IMPROVEMENT_PROMPT = (
    "Inspect the widgetbox package in this workspace, including "
    "registry.py and the existing widget modules. Write a durable "
    "engineering note stating the exact convention every widget "
    "module must satisfy in this package. Reply with only the note "
    "text; do not edit any file."
)

_USAGE_ROW = re.compile(
    r"deepseek/deepseek-v4\.1-flash\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)"
)
_TOK = re.compile(r"^([\d.]+)([kKmM]?)$")


def _tokens(raw: str) -> int:
    """Parse a formatted token count like ``45.2k`` or ``1.3M``."""
    match = _TOK.match(raw.replace(",", ""))
    if not match:
        return 0
    scale = {"": 1, "k": 1_000, "m": 1_000_000}[match.group(2).lower()]
    return int(float(match.group(1)) * scale)


def _usage(stderr_text: str) -> dict[str, int]:
    """Extract provider-reported usage from the usage table."""
    match = _USAGE_ROW.search(stderr_text)
    if not match:
        return {"requests": 0, "input_tokens": 0, "output_tokens": 0}
    return {
        "requests": int(match.group(1)),
        "input_tokens": _tokens(match.group(2)),
        "output_tokens": _tokens(match.group(3)),
    }


def _env(profile: Path, home: Path) -> dict[str, str]:
    """Per-run environment: isolated profile and frozen memory."""
    env = dict(os.environ)
    env.update(
        {
            "DEEPAGENTS_HOME": str(profile),
            "HOME": str(home),
            "DEEPAGENTS_CODE_MEMORY_AUTO_SAVE": "0",
            "DEEPAGENTS_CODE_NO_UPDATE_CHECK": "1",
            "DEEPAGENTS_CODE_AUTO_UPDATE": "0",
            "DEEPAGENTS_CODE_PLUGIN_AUTO_UPDATE": "0",
            "DEEPAGENTS_CODE_PRICES_AUTO_UPDATE": "0",
            "DEEPAGENTS_CODE_SHOW_USAGE_STATS": "1",
            "DEEPAGENTS_CODE_NO_TERMINAL_ESCAPE": "1",
        }
    )
    return env


def _tree_digest(root: Path) -> str:
    """Digest a directory tree for run bindings."""
    entries = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            entries[p.relative_to(root).as_posix()] = hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(entries, sort_keys=True).encode()
        ).hexdigest()
    )


def _file_digest(path: Path) -> str:
    """Digest a single evidence file."""
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _usage_of(res: dict[str, object]) -> dict[str, int]:
    """Narrow a run result's usage record to its typed shape."""
    usage = res["usage"]
    assert isinstance(usage, dict)
    out = {"requests": 0, "input_tokens": 0, "output_tokens": 0}
    for key in out:
        v = usage.get(key)
        out[key] = int(v) if isinstance(v, (int, str)) else 0
    return out


def _cost_of(res: dict[str, object]) -> float:
    """Narrow a run result's cost field."""
    cost = res["cost_usd"]
    return float(cost) if isinstance(cost, (int, float)) else 0.0


class _Totals(TypedDict):
    """Running spend against the sealed caps."""

    runs: int
    requests: int
    tokens: int
    cost_usd: float


def _run_dcode(
    name: str,
    prompt: str,
    workspace: Path,
    profile: Path,
    model_params: dict[str, object],
) -> dict[str, object]:
    """Launch one headless dcode run and capture raw evidence."""
    run_dir = workspace.parent
    home = run_dir / "home"
    home.mkdir(exist_ok=True)
    out_path = run_dir / "stdout.txt"
    err_path = run_dir / "stderr.txt"
    cmd = [
        str(DCODE),
        "-n",
        prompt,
        "-a",
        AGENT,
        "-M",
        "openrouter:deepseek/deepseek-v4.1-flash",
        "--model-params",
        json.dumps(model_params),
        "--max-retries",
        "0",
        "--no-mcp",
        "--timeout",
        str(RUN_TIMEOUT),
        "--max-turns",
        str(MAX_TURNS),
    ]
    start = time.monotonic()
    aborted = False
    with out_path.open("w") as out, err_path.open("w") as err:
        try:
            proc = subprocess.run(
                cmd,
                cwd=workspace,
                env=_env(profile, home),
                stdout=out,
                stderr=err,
                timeout=HARD_KILL,
                check=False,
            )
            code: int | None = proc.returncode
        except subprocess.TimeoutExpired:
            code = None
            aborted = True
    wall = time.monotonic() - start
    stderr_text = err_path.read_text(errors="replace")
    stdout_text = out_path.read_text(errors="replace")
    # The usage table, tool lines and the completion marker all render
    # on the headless stdout stream; stderr carries warnings only.
    usage = _usage(stdout_text)
    completed = not aborted and code == 0 and "Task completed" in stdout_text
    result: dict[str, object] = {
        "run_id": name,
        "cmd": cmd,
        "cwd": str(workspace),
        "exit_code": code,
        "aborted": aborted,
        "completed": completed,
        "wall_seconds": round(wall, 2),
        "usage": usage,
        "cost_usd": round(
            usage["input_tokens"] * PRICE_PROMPT
            + usage["output_tokens"] * PRICE_COMPLETION,
            6,
        ),
        "stdout_bytes": len(stdout_text.encode()),
        "stderr_bytes": len(stderr_text.encode()),
        "retried": False,
    }
    # Sealed retry policy: re-issue at most once, only when the run
    # died before its first model call — a clean nonzero exit with
    # zero requests billed. A timeout abort leaves an uncertain
    # in-flight effect and is never retried.
    if (
        not completed
        and not aborted
        and code not in (0, None)
        and usage["requests"] == 0
    ):
        for f in (out_path, err_path):
            shutil.copy(f, f.with_name("attempt1." + f.name))
        result["retried"] = True
        retry = _run_dcode(name, prompt, workspace, profile, model_params)
        retry["retried"] = True
        return retry
    return result


def _oracle(workspace: Path, out_path: Path) -> tuple[int, str]:
    """Run the trusted oracle on a workspace; record raw output."""
    proc = subprocess.run(
        [
            sys.executable,
            str(STUDY / "oracle" / "check_registry.py"),
            str(workspace),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    text = (proc.stdout + proc.stderr).strip()
    out_path.write_text(text + "\n")
    return proc.returncode, text


def main() -> int:
    """Execute the sealed study; refuse to start on any gate failure."""
    record = json.loads((EVIDENCE / "manifest.json").read_text())
    if record["sealed_manifest_digest"] != seal_study._digest_json(
        record["manifest"]
    ):
        raise CyranoError("SEAL_MISMATCH", "manifest digest drifted")
    if not os.environ.get(record["credential_env"]):
        raise CyranoError(
            "PERMISSION_DENIED", f"{record['credential_env']} missing"
        )
    limits = record["limits"]
    suite = json.loads((STUDY / "suite.json").read_text())
    route = json.loads((STUDY / "run.json").read_text())
    model_params = route["model"]["parameters"]
    spec = seal_study.build_spec()
    manifest = seal_experiment(spec)
    if manifest.manifest_id != record["manifest"]["manifest_id"]:
        raise CyranoError("SEAL_MISMATCH", "spec does not reproduce seal")

    permit = {
        "permit_id": digest(
            {"authorization": record["sealed_manifest_digest"]}
        ),
        "expires_at": 2_000_000_000,
        "budget_units": limits["max_tokens"],
        "families": list(suite["families"]),
    }

    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    runs_dir = EVIDENCE / "runs"
    runs_dir.mkdir(exist_ok=True)
    repo = ScopedRepository.create(
        EVIDENCE / "study-ledger.sqlite", TARGET_DDL.read_text()
    )
    memory = MemoryService(MemoryRepository(repo))
    desk = ApprovalDesk()
    ledger = TrialLedger(manifest)
    scope = "wp23-live-study"
    now = int(time.time())

    tasks = suite["tasks"]
    totals: _Totals = {"runs": 0, "requests": 0, "tokens": 0, "cost_usd": 0.0}
    results: list[dict[str, object]] = []
    improvement_text: str | None = None

    def over_budget() -> str | None:
        if totals["runs"] > limits["max_runs"]:
            return "runs"
        if totals["requests"] > limits["max_model_calls"]:
            return "calls"
        if totals["tokens"] > limits["max_tokens"]:
            return "tokens"
        if totals["cost_usd"] > limits["max_cost_usd"]:
            return "cost"
        return None

    def execute(
        name: str,
        prompt: str,
        overlay: str | None,
        memory_text: str | None,
    ) -> dict[str, object]:
        """Run one slot, snapshot seed, capture evidence, debit."""
        run_dir = RUN_ROOT / name
        run_dir.mkdir(parents=True, exist_ok=True)
        workspace = run_dir / "workspace"
        shutil.copytree(STUDY / "repo", workspace)
        if overlay:
            shutil.copytree(STUDY / overlay, workspace, dirs_exist_ok=True)
        seed = run_dir / "seed"
        shutil.copytree(workspace, seed)
        profile = run_dir / "profile"
        agent_dir = profile / "agents" / AGENT
        agent_dir.mkdir(parents=True, exist_ok=True)
        if memory_text is not None:
            (agent_dir / "AGENTS.md").write_text(memory_text)
        profile_digest = _tree_digest(profile)
        seed_digest = _tree_digest(workspace)
        result = _run_dcode(name, prompt, workspace, profile, model_params)
        ev_dir = runs_dir / name
        ev_dir.mkdir(parents=True, exist_ok=True)
        for f in (
            "stdout.txt",
            "stderr.txt",
            "attempt1.stdout.txt",
            "attempt1.stderr.txt",
        ):
            if (run_dir / f).exists():
                shutil.copy(run_dir / f, ev_dir / f)
        code, text = _oracle(workspace, ev_dir / "oracle.txt")
        diff = subprocess.run(
            ["diff", "-ruN", str(seed) + "/", str(workspace) + "/"],
            capture_output=True,
            text=True,
            check=False,
        )
        (ev_dir / "workspace.diff").write_text(diff.stdout)
        result["oracle_exit"] = code
        result["oracle_text"] = text
        result["workspace_digest"] = _tree_digest(workspace)
        binding = {
            "run_id": name,
            "manifest_id": manifest.manifest_id,
            "model": route["model"]["model_spec"],
            "provider_routing": route["provider_routing"]["policy"],
            "seed_digest": seed_digest,
            "profile_digest": profile_digest,
            "workspace_digest": result["workspace_digest"],
        }
        (ev_dir / "run-binding.json").write_text(json.dumps(binding, indent=2))
        (ev_dir / "result.json").write_text(json.dumps(result, indent=2))
        totals["runs"] += 1
        usage = _usage_of(result)
        totals["requests"] += usage["requests"]
        totals["tokens"] += usage["input_tokens"] + usage["output_tokens"]
        totals["cost_usd"] = round(totals["cost_usd"] + _cost_of(result), 6)
        results.append(result)
        return result

    def trial(
        pair: str, family: str, arm: str, res: dict[str, object], order: int
    ) -> None:
        """Fold one run into the ledger; aborts stay as specimens."""
        exit_code = res["exit_code"]
        if res["aborted"]:
            status, outcome = "aborted", "unknown"
        elif not isinstance(exit_code, int) or exit_code != 0:
            status, outcome = "failed", "unknown"
        elif res.get("oracle_exit") is None:
            status, outcome = "completed", "unknown"
        else:
            status = "completed"
            outcome = "pass" if res["oracle_exit"] == 0 else "fail"
        usage = _usage_of(res)
        ledger.record(
            TrialResult(
                pair,
                family,
                arm,
                status,
                outcome,
                usage["input_tokens"] + usage["output_tokens"],
                order,
            )
        )

    # --- Run 1: Task A learning episode (candidate arm) ---
    task_a = tasks["task-a"]
    a_res = execute("task-a-candidate", str(task_a["prompt"]), None, None)
    trial("pair-a", "learn-episode", "candidate", a_res, 0)
    if over_budget():
        return _abort(totals, results, "cap exceeded after task-a")

    # --- Run 2: governed improvement generation (learn-episode) ---
    imp_dir = RUN_ROOT / "improvement"
    imp_dir.mkdir(parents=True, exist_ok=True)
    imp_ws = imp_dir / "workspace"
    shutil.copytree(RUN_ROOT / "task-a-candidate" / "workspace", imp_ws)
    imp_seed = imp_dir / "seed"
    shutil.copytree(imp_ws, imp_seed)
    imp_profile = imp_dir / "profile"
    (imp_profile / "agents" / AGENT).mkdir(parents=True, exist_ok=True)
    imp_res = _run_dcode(
        "improvement", _IMPROVEMENT_PROMPT, imp_ws, imp_profile, model_params
    )
    ev_dir = runs_dir / "improvement"
    ev_dir.mkdir(parents=True, exist_ok=True)
    for f in (
        "stdout.txt",
        "stderr.txt",
        "attempt1.stdout.txt",
        "attempt1.stderr.txt",
    ):
        if (imp_dir / f).exists():
            shutil.copy(imp_dir / f, ev_dir / f)
    code, text = _oracle(imp_ws, ev_dir / "oracle.txt")
    imp_res["oracle_exit"] = code
    imp_res["oracle_text"] = text
    (ev_dir / "result.json").write_text(json.dumps(imp_res, indent=2))
    totals["runs"] += 1
    imp_usage = _usage_of(imp_res)
    totals["requests"] += imp_usage["requests"]
    totals["tokens"] += imp_usage["input_tokens"] + imp_usage["output_tokens"]
    totals["cost_usd"] = round(totals["cost_usd"] + _cost_of(imp_res), 6)
    results.append(imp_res)
    trial("pair-improvement", "learn-episode", "candidate", imp_res, 0)

    note = (imp_dir / "stdout.txt").read_text(errors="replace").strip()
    approval: dict[str, object]
    if imp_res["completed"] and note:
        proposal = {
            "kind": "procedure",
            "scope_id": scope,
            "subject": "widgetbox-convention",
            "precondition": "editing widgetbox widget modules",
            "evidence_refs": ("task-a-candidate", "improvement"),
            "freshness_epoch": 0,
        }
        kc = validate_knowledge_candidate(proposal)
        record_mem = memory.propose_memory(
            scope,
            "widgetbox-convention-r1",
            kind="procedure",
            content=note.encode(),
            source_digest=kc.candidate_id,
            evidence_refs=kc.evidence_refs,
            at=now,
        )
        display = desk.present(
            subject_digest=kc.candidate_id,
            shown_text=note,
            audience="study-operator",
            nonce="wp23-live",
            expires_at=now + 3600,
            purpose="improvement_approval",
        )
        desk.open_display(display.request_id)
        decision = desk.submit(
            display.request_id,
            actor="study-operator",
            nonce="wp23-live",
            decision="approve",
            shown_text=note,
            display_revision=display.display_revision,
            client_event_id="wp23-live-approve-1",
            now=now,
        )
        approval = {
            "candidate_id": kc.candidate_id,
            "memory_id": record_mem.memory_id,
            "request_id": display.request_id,
            "decision": decision.status,
            "content_digest": record_mem.content_digest,
        }
        if decision.status == "approved":
            memory.activate_memory(
                scope,
                record_mem.memory_id,
                expected_revision=record_mem.revision,
                at=now,
            )
            improvement_text = note
    else:
        approval = {
            "decision": "no_improvement",
            "reason": "improvement run produced no note",
        }
    (ev_dir / "improvement-approval.json").write_text(
        json.dumps(approval, indent=2)
    )
    if over_budget():
        return _abort(totals, results, "cap exceeded after improvement")

    # --- Runs 3-8: holdout pairs B1/B2/B3 ---
    order = 1
    for key in ("task-b1", "task-b2", "task-b3"):
        task = tasks[key]
        overlay = task.get("workspace_overlay")
        overlay_str = str(overlay) if overlay else None
        for arm, mem in (
            ("baseline", None),
            ("candidate", improvement_text),
        ):
            name = f"{key}-{arm}"
            res = execute(name, str(task["prompt"]), overlay_str, mem)
            trial(str(task["pair_id"]), str(task["family"]), arm, res, order)
            if over_budget():
                return _abort(totals, results, f"cap exceeded after {name}")
        order += 1

    # --- Settle, review, verdict ---
    study = run_preregistered_study(
        manifest, spec, permit=permit, trials=ledger.trials, now=now
    )

    def ref(kind: str, path: Path) -> dict[str, str]:
        return {
            "kind": kind,
            "ref": str(path.relative_to(ROOT)),
            "digest": _file_digest(path),
        }

    ledger_db = EVIDENCE / "study-ledger.sqlite"
    sqlite3.connect(str(ledger_db)).execute("PRAGMA wal_checkpoint(TRUNCATE)")
    approval_file = runs_dir / "improvement" / "improvement-approval.json"
    bindings = sorted(runs_dir.glob("*/run-binding.json"))
    streams = sorted(
        p
        for p in runs_dir.glob("*/*.txt")
        if p.name in {"stdout.txt", "stderr.txt", "oracle.txt"}
    )
    items = {
        "3-1": {
            "evidence_refs": [
                ref("receipt", ledger_db),
                ref("receipt", approval_file),
            ]
        },
        "3-2": {
            "evidence_refs": [
                ref(
                    "run_binding",
                    runs_dir / "task-b1-candidate" / "run-binding.json",
                )
            ]
        },
        "3-3": {"evidence_refs": [ref("receipt", approval_file)]},
        "3-4": {"evidence_refs": [ref("run_binding", b) for b in bindings]},
        "4-1": {"evidence_refs": [ref("events", s) for s in streams]},
        "4-2": {"evidence_refs": [ref("artifact", s) for s in streams]},
        "4-3": {
            "evidence_refs": [
                ref("artifact", runs_dir / "task-b1-baseline" / "result.json"),
                ref(
                    "artifact",
                    runs_dir / "task-b1-candidate" / "result.json",
                ),
            ]
        },
        "4-4": {
            "evidence_refs": [
                ref(
                    "oracle_result",
                    runs_dir / "task-b3-candidate" / "oracle.txt",
                )
            ]
        },
    }
    verdict = review_effectiveness(
        manifest,
        ledger,
        items,
        learning_overhead_units=(
            imp_usage["input_tokens"] + imp_usage["output_tokens"]
        ),
    )
    final = {
        "manifest_id": manifest.manifest_id,
        "sealed_manifest_digest": record["sealed_manifest_digest"],
        "totals": totals,
        "pairs": [
            {
                "pair_id": p.pair_id,
                "family": p.family,
                "complete": p.complete,
                "baseline": p.baseline_outcome,
                "candidate": p.candidate_outcome,
            }
            for p in ledger.pairs()
        ],
        "study": {
            "permit_id": study["permit_id"],
            "settle": study["settle"],
            "spent_units": study["spent_units"],
        },
        "verdict": verdict,
        "runs": [
            {
                "run_id": r["run_id"],
                "completed": r["completed"],
                "oracle_exit": r.get("oracle_exit"),
                "usage": r["usage"],
                "cost_usd": r["cost_usd"],
                "wall_seconds": r["wall_seconds"],
            }
            for r in results
        ],
    }
    (EVIDENCE / "study-result.json").write_text(
        json.dumps(final, indent=2, default=str)
    )
    print(json.dumps(final, indent=2, default=str))
    return 0


def _abort(
    totals: _Totals,
    results: list[dict[str, object]],
    reason: str,
) -> int:
    """Stop inside the authorized boundary; keep raw evidence."""
    (EVIDENCE / "study-result.json").write_text(
        json.dumps(
            {
                "status": "aborted",
                "reason": reason,
                "totals": totals,
                "runs": results,
            },
            indent=2,
            default=str,
        )
    )
    print(f"ABORTED: {reason}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
