"""Execute the sealed WP23 live-effectiveness study (study 4).

This harness is the only caller allowed to turn the sealed study-4
manifest into real runs. It re-verifies the sealed digest, enforces
the hard run/call/token/cost caps, provisions per-run isolated
workspaces inside private mount namespaces, drives Task A plus the
governed improvement lifecycle (propose -> approve -> activate ->
persisted store), runs the holdout pairs — baseline as a stock
``create_cli_agent`` graph, candidate through ``run_governed_work``
with ``task_recall`` bound to the live store — and folds specimens
into the trial ledger. It never retries an ambiguous external effect
and never discards an incomplete pair.

Study 4 versus study 3: the candidate no longer receives a provisioned
AGENTS.md artifact. Memory reaches the run only through the product
recall path — ``MemoryGate`` is built with ``records=()`` and
``rule_bodies={}``, so the sealed store and ``task_recall`` are the
sole knowledge channel. Every candidate holdout passes a fail-closed
pre-dispatch gate covering store freshness, active revisions, the
approval receipt, checker digests, seed digests, baseline cleanliness
and arm parity.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import shlex
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import TypedDict

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.evaluation.paired import (
    TrialLedger,
    TrialResult,
    seal_experiment,
)
from deepagents_code.cyrano.evaluation.rubric_evidence import (
    review_effectiveness,
    run_preregistered_study,
)
from deepagents_code.cyrano.improvement.knowledge_lane import (
    validate_knowledge_candidate,
)
from deepagents_code.cyrano.kernel.approvals import ApprovalDesk
from deepagents_code.cyrano.memory.repository import MemoryRepository
from deepagents_code.cyrano.memory.service import MemoryService
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT.parent
sys.path.insert(0, str(CODE))
sys.path.insert(0, str(ROOT / "scripts"))

seal_study4 = importlib.import_module("seal_study4")

STUDY = ROOT / "tests" / "live-study-4"
EVIDENCE = ROOT / "evidence" / "live-evaluation"
EVDIR = EVIDENCE / "study-4"
RUN_ROOT = Path("/tmp/wp23-live-study-4")
TARGET_DDL = ROOT / "contracts" / "sql" / "target-schema.sql"
DRIVER = ROOT / "scripts" / "study4_arm.py"

# Fresh lane for study 4 — no study-1/2/3 memory record carries over;
# the store is a new SQLite ledger under the study-4 evidence dir.
STUDY_ID = "wp23-live-effectiveness-4"
AGENT = "wp23r4"
TENANT = "wp23-live-study-4"
SCOPE_WS = "sentinel"
NONCE = "wp23-live-4"
CLIENT_EVENT = "wp23-live-4-approve-1"
ACTOR = "study-operator"
PURPOSE = "improvement_approval"

HARD_KILL = 1700  # inside the sealed 1800s per-run cap


def _improvement_prompt(
    task_a_prompt: str, workspace_diff: str, oracle_text: str
) -> str:
    """Improvement prompt built only from Task A evidence.

    The governed note must be derivable from the learning episode —
    the attempted instruction, the changes the model actually made,
    and the trusted evaluator's violation report — never from the
    holdout inputs or the oracle implementation.
    """
    return (
        "A previous task attempted this instruction:\n"
        f"{task_a_prompt}\n\n"
        "Its workspace changes were:\n"
        f"{workspace_diff or '(no changes)'}\n\n"
        "The package's packaging evaluator then reported:\n"
        f"{oracle_text}\n\n"
        "Inspect the sentinel package in this workspace, then write a "
        "durable engineering note stating the exact convention every "
        "sentinel module and its cap metadata must satisfy in this "
        "package. Reply with only the note text; do not edit any file."
    )


def _env(home: Path) -> dict[str, str]:
    """Per-run environment: isolated HOME and frozen dcode state."""
    env = dict(os.environ)
    env.update(
        {
            "DEEPAGENTS_HOME": str(home / "deepagents"),
            "HOME": str(home),
            "DEEPAGENTS_CODE_MEMORY_AUTO_SAVE": "0",
            "DEEPAGENTS_CODE_NO_UPDATE_CHECK": "1",
            "DEEPAGENTS_CODE_AUTO_UPDATE": "0",
            "DEEPAGENTS_CODE_PLUGIN_AUTO_UPDATE": "0",
            "DEEPAGENTS_CODE_PRICES_AUTO_UPDATE": "0",
            "DEEPAGENTS_CODE_NO_TERMINAL_ESCAPE": "1",
        }
    )
    return env


def _tree_digest(root: Path) -> str:
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
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _usage_of(res: dict[str, object]) -> dict[str, int]:
    usage = res["usage"]
    assert isinstance(usage, dict)
    out = {"requests": 0, "input_tokens": 0, "output_tokens": 0}
    for key in out:
        v = usage.get(key)
        out[key] = int(v) if isinstance(v, (int, str)) else 0
    return out


def _cost_of(res: dict[str, object]) -> float:
    cost = res["cost_usd"]
    return float(cost) if isinstance(cost, (int, float)) else 0.0


class _Totals(TypedDict):
    """Running spend against the sealed caps."""

    runs: int
    requests: int
    tokens: int
    cost_usd: float


def _receipt_valid(approval: dict[str, object]) -> bool:
    """Recompute the approval receipt from its bound fields."""
    fields = approval.get("receipt_fields")
    expected = approval.get("receipt_digest")
    if not isinstance(fields, dict) or not isinstance(expected, str):
        return False
    return expected == digest(
        {
            "subject": fields.get("subject"),
            "nonce": fields.get("nonce"),
            "actor": fields.get("actor"),
            "client_event": fields.get("client_event_id"),
            "purpose": fields.get("purpose"),
        }
    )


def _candidate_integrity_gate(
    *,
    store: Path,
    scope_id: str,
    approval: dict[str, object] | None,
    run_dir: Path,
    baseline_dir: Path,
    seed_digest: str,
    expected_seed_digest: str,
    checker_root: Path,
    memory_ids: tuple[str, ...],
    arms_identical: bool,
) -> list[str]:
    """Fail-closed pre-dispatch gate over real runtime state.

    Every invariant is checked against on-disk artifacts and the
    scoped memory repository — never against process output. An empty
    list means the candidate may proceed to its first model call.
    """
    fails: list[str] = []
    if not arms_identical:
        fails.append("arms_diverge")
    if seed_digest != expected_seed_digest:
        fails.append("seed_digest_mismatch")
    approved = (
        isinstance(approval, dict) and approval.get("decision") == "approved"
    )
    if not approved:
        fails.append("approval_absent")
    if (
        approved
        and isinstance(approval, dict)
        and not _receipt_valid(approval)
    ):
        fails.append("receipt_invalid")
    approved_digests = (
        approval.get("content_digests") if isinstance(approval, dict) else None
    )
    if not isinstance(approved_digests, dict):
        fails.append("release_unbound")
        approved_digests = {}
    if not store.is_file():
        fails.append("store_missing")
    else:
        repo = ScopedRepository.open(store)
        try:
            memory_repo = MemoryRepository(repo)
            all_ids = {r.memory_id for r in memory_repo.list_scope(scope_id)}
            extras = all_ids - set(memory_ids)
            if extras:
                # Any record beyond the two approved rules is
                # contamination — a prior-study or foreign memory.
                fails.append(f"unexpected_records:{sorted(extras)}")
            for mid in memory_ids:
                record = memory_repo.get(scope_id, mid)
                if record is None:
                    fails.append(f"proposal_missing:{mid}")
                    continue
                if record.status != "active":
                    fails.append(f"improvement_not_active:{mid}")
                if record.content_digest != approved_digests.get(mid):
                    fails.append(f"release_unbound:{mid}")
        finally:
            repo.close()
    checkers = run_dir / "checkers"
    for rel in sorted(checker_root.glob("*.json")):
        staged = checkers / rel.name
        if not staged.is_file():
            fails.append(f"checker_missing:{rel.name}")
        elif _file_digest(staged) != _file_digest(rel):
            fails.append(f"checker_digest_mismatch:{rel.name}")
    # Baseline confinement: no governed artifacts may exist in the
    # baseline run directory — no store, no checkers, no snapshots.
    for forbidden in ("store.sqlite", "checkers", "snapshots"):
        if (baseline_dir / forbidden).exists():
            fails.append(f"baseline_contaminated:{forbidden}")
    return fails


def _confined(run_dir: Path, cmd: list[str]) -> list[str]:
    """Wrap a run in a mount namespace hiding contract-bearing paths.

    Same mechanism as study 3: the Cyrano fixture/evidence tree, the
    repository git objects and the whole run root are masked by tmpfs;
    only this run's own directory is rebound at its real path. The
    dcode venv and editable sources stay visible so the in-process
    driver imports the real product code.
    """
    stage = Path("/tmp") / f".ns-stage-{run_dir.name}"
    stage.mkdir(exist_ok=True)
    git_dir = ROOT.parents[2] / ".git"
    masks = [str(ROOT)]
    if git_dir.is_dir():
        masks.append(str(git_dir))
    script = (
        f"mount --bind {shlex.quote(str(run_dir))} {shlex.quote(str(stage))}"
        + "".join(f" && mount -t tmpfs tmpfs {shlex.quote(m)}" for m in masks)
        + f" && mount -t tmpfs tmpfs {shlex.quote(str(RUN_ROOT))}"
        + f" && mkdir -p {shlex.quote(str(run_dir))}"
        + f" && mount --bind {shlex.quote(str(stage))} "
        + shlex.quote(str(run_dir))
        + ' && exec "$@"'
    )
    return [
        "unshare",
        "-rm",
        "--propagation",
        "private",
        "bash",
        "-c",
        script,
        "bash",
        *cmd,
    ]


def _run_arm(run_dir: Path, arm: str, task_key: str) -> dict[str, object]:
    """Launch one confined in-process arm run and capture evidence."""
    out_path = run_dir / "stdout.txt"
    err_path = run_dir / "stderr.txt"
    cmd = _confined(
        run_dir,
        [
            sys.executable,
            str(run_dir / "driver.py"),
            "--arm",
            arm,
            "--task",
            task_key,
            "--run-dir",
            str(run_dir),
            "--code-root",
            str(CODE),
        ],
    )
    start = time.monotonic()
    aborted = False
    with out_path.open("w") as out, err_path.open("w") as err:
        try:
            proc = subprocess.run(
                cmd,
                cwd=run_dir,
                env=_env(run_dir / "home"),
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
    result_path = run_dir / "result.json"
    result: dict[str, object] = {"run_id": run_dir.name}
    if result_path.is_file():
        loaded = json.loads(result_path.read_text())
        if isinstance(loaded, dict):
            result = dict(loaded)
    result.setdefault(
        "usage",
        {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "observed": False,
        },
    )
    result["exit_code"] = code
    result["aborted"] = aborted
    result["harness_wall_seconds"] = round(wall, 2)
    result["completed"] = bool(
        not aborted and code == 0 and result.get("completed")
    )
    result["retried"] = False
    if (
        not result["completed"]
        and not aborted
        and code not in (0, None)
        and _usage_of(result)["requests"] == 0
    ):
        for f in (out_path, err_path):
            shutil.copy(f, f.with_name("attempt1." + f.name))
        result["retried"] = True
        retry = _run_arm(run_dir, arm, task_key)
        retry["retried"] = True
        return retry
    return result


def _oracle(
    workspace: Path, out_path: Path, oracle_rel: str, task_key: str
) -> tuple[int, str]:
    """Run the task's trusted oracle; record raw output."""
    proc = subprocess.run(
        [
            sys.executable,
            str(STUDY / oracle_rel),
            str(workspace),
            task_key,
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
    if record["sealed_manifest_digest"] != seal_study4._digest_json(
        record["manifest"]
    ):
        raise CyranoError("SEAL_MISMATCH", "manifest digest drifted")
    if record["study_id"] != STUDY_ID:
        raise CyranoError("SEAL_MISMATCH", "manifest is not study-4")
    if not os.environ.get(record["credential_env"]):
        raise CyranoError(
            "PERMISSION_DENIED", f"{record['credential_env']} missing"
        )
    limits = record["limits"]
    suite = json.loads((STUDY / "suite.json").read_text())
    route = json.loads((STUDY / "run.json").read_text())
    baseline_arm = json.loads((STUDY / "arms" / "baseline.json").read_text())
    candidate_arm = json.loads((STUDY / "arms" / "candidate.json").read_text())
    spec = seal_study4.build_spec()
    manifest = seal_experiment(spec)
    if manifest.manifest_id != record["manifest"]["manifest_id"]:
        raise CyranoError("SEAL_MISMATCH", "spec does not reproduce seal")
    arms_identical = (
        baseline_arm["model"] == candidate_arm["model"]
        and baseline_arm["provider_routing"]
        == candidate_arm["provider_routing"]
        and baseline_arm["tools"] == candidate_arm["tools"]
        and baseline_arm["dcode_release"] == candidate_arm["dcode_release"]
        and baseline_arm["workspace"] == candidate_arm["workspace"]
        and baseline_arm["system_prompt"] == candidate_arm["system_prompt"]
    )
    permit = {
        "permit_id": digest(
            {"authorization": record["sealed_manifest_digest"]}
        ),
        "expires_at": 2_000_000_000,
        "budget_units": limits["max_tokens"],
        "families": list(suite["families"]),
    }

    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    runs_dir = EVDIR / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    ledger_db = EVDIR / "study-ledger.sqlite"
    repo = ScopedRepository.create(ledger_db, TARGET_DDL.read_text())
    scope_id = repo.register_scope(TENANT, AGENT, SCOPE_WS)
    memory = MemoryService(MemoryRepository(repo))
    desk = ApprovalDesk()
    ledger = TrialLedger(manifest)
    now = int(time.time())

    tasks = suite["tasks"]
    identity = suite["identity"]
    governed_cfg = suite["governed_candidate"]
    memory_ids = tuple(identity["memory_ids"])
    totals: _Totals = {"runs": 0, "requests": 0, "tokens": 0, "cost_usd": 0.0}
    results: list[dict[str, object]] = []
    approval: dict[str, object] | None = None
    source_digests: list[str] = []

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

    def _collect(run_dir: Path, ev_dir: Path) -> None:
        ev_dir.mkdir(parents=True, exist_ok=True)
        for pattern in (
            "stdout.txt",
            "stderr.txt",
            "attempt1.stdout.txt",
            "attempt1.stderr.txt",
            "result.json",
            "arm-input.json",
            "audit.json",
            "note.txt",
        ):
            f = run_dir / pattern
            if f.exists():
                shutil.copy(f, ev_dir / f.name)
        evidence = run_dir / "evidence.json"
        if evidence.exists():
            shutil.copy(evidence, ev_dir / evidence.name)
        for snap in sorted((run_dir / "snapshots").glob("*")):
            if snap.is_dir():
                shutil.copytree(
                    snap,
                    ev_dir / "snapshots" / snap.name,
                    dirs_exist_ok=True,
                )

    def _debit(result: dict[str, object]) -> None:
        totals["runs"] += 1
        usage = _usage_of(result)
        totals["requests"] += usage["requests"]
        totals["tokens"] += usage["input_tokens"] + usage["output_tokens"]
        totals["cost_usd"] = round(totals["cost_usd"] + _cost_of(result), 6)
        results.append(result)

    expected_digests: dict[str, str] = {}

    def expected_seed(task_key: str) -> str:
        """Independently materialize repo+overlay and digest it."""
        if task_key not in expected_digests:
            task = tasks[task_key]
            staging = RUN_ROOT / ".expected" / task_key
            if staging.exists():
                shutil.rmtree(staging)
            shutil.copytree(STUDY / "repo", staging)
            overlay = task.get("workspace_overlay")
            if overlay:
                shutil.copytree(
                    STUDY / str(overlay), staging, dirs_exist_ok=True
                )
            expected_digests[task_key] = _tree_digest(staging)
        return expected_digests[task_key]

    def _prepare(name: str, task_key: str, arm: str) -> tuple[Path, Path, str]:
        """Provision a run dir; return (run_dir, workspace, oracle)."""
        task = tasks[task_key]
        run_dir = RUN_ROOT / name
        run_dir.mkdir(parents=True, exist_ok=True)
        workspace = run_dir / "workspace"
        shutil.copytree(STUDY / "repo", workspace)
        overlay = task.get("workspace_overlay")
        if overlay:
            shutil.copytree(
                STUDY / str(overlay), workspace, dirs_exist_ok=True
            )
        seed = run_dir / "seed"
        shutil.copytree(workspace, seed)
        (run_dir / "home").mkdir(exist_ok=True)
        driver_copy = run_dir / "driver.py"
        shutil.copy(DRIVER, driver_copy)
        if _file_digest(driver_copy) != _file_digest(DRIVER):
            raise CyranoError("SEAL_MISMATCH", "driver copy digest drifted")
        arm_input: dict[str, object] = {
            "run_id": name,
            "task_key": task_key,
            "arm": arm,
            "task": task,
            "prompt": str(task["prompt"]),
            "model_spec": route["model"]["model_spec"],
            "model_parameters": route["model"]["parameters"],
            "pricing": route["provider_routing"]["policy"]["pinned_upstream"][
                "pricing"
            ],
            "agent": AGENT,
        }
        if arm == "candidate":
            arm_input.update(
                {
                    "actor": ACTOR,
                    "scope": identity["scope"],
                    "scope_id": scope_id,
                    "runtime_digest": str(manifest.runtime_digest),
                    "governed": governed_cfg,
                    "available_source_digests": source_digests,
                    "checker_files": {
                        cid: Path(rel).name
                        for cid, rel in suite["learning"][
                            "checker_files"
                        ].items()
                    },
                }
            )
            shutil.copy(ledger_db, run_dir / "store.sqlite")
            checkers = run_dir / "checkers"
            checkers.mkdir(exist_ok=True)
            for rel in suite["learning"]["checker_files"].values():
                src = STUDY / "oracle" / "checkers" / Path(rel).name
                shutil.copy(src, checkers / src.name)
        (run_dir / "arm-input.json").write_text(
            json.dumps(arm_input, indent=2)
        )
        return run_dir, workspace, str(task["oracle"])

    def execute(
        name: str,
        task_key: str,
        arm: str,
        gated_candidate: bool,
    ) -> dict[str, object]:
        """Run one slot; gate candidates before any model call."""
        run_dir, workspace, oracle_rel = _prepare(name, task_key, arm)
        ev_dir = runs_dir / name
        ev_dir.mkdir(parents=True, exist_ok=True)
        seed_digest = expected_seed(task_key)
        if gated_candidate:
            baseline_dir = RUN_ROOT / name.replace("-candidate", "-baseline")
            fails = _candidate_integrity_gate(
                store=run_dir / "store.sqlite",
                scope_id=scope_id,
                approval=approval,
                run_dir=run_dir,
                baseline_dir=baseline_dir,
                seed_digest=_tree_digest(workspace),
                expected_seed_digest=seed_digest,
                checker_root=STUDY / "oracle" / "checkers",
                memory_ids=memory_ids,
                arms_identical=arms_identical,
            )
            gate_ev = {
                "run_id": name,
                "gate": "failed" if fails else "passed",
                "failures": fails,
            }
            (ev_dir / "integrity-gate.json").write_text(
                json.dumps(gate_ev, indent=2)
            )
            if fails:
                result: dict[str, object] = {
                    "run_id": name,
                    "exit_code": None,
                    "aborted": True,
                    "completed": False,
                    "integrity_gate": "failed",
                    "gate_failures": fails,
                    "wall_seconds": 0.0,
                    "usage": {
                        "requests": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "observed": False,
                    },
                    "cost_usd": 0.0,
                    "retried": False,
                }
                _collect(run_dir, ev_dir)
                (ev_dir / "result.json").write_text(
                    json.dumps(result, indent=2)
                )
                results.append(result)
                return result
        store_digest_before = (
            _file_digest(run_dir / "store.sqlite")
            if (run_dir / "store.sqlite").is_file()
            else None
        )
        result = _run_arm(run_dir, arm, task_key)
        if store_digest_before is not None:
            result["store_digest_before"] = store_digest_before
            result["store_digest_unchanged"] = (
                _file_digest(run_dir / "store.sqlite") == store_digest_before
            )
        _collect(run_dir, ev_dir)
        code, text = _oracle(
            workspace, ev_dir / "oracle.txt", oracle_rel, task_key
        )
        result["oracle_exit"] = code
        result["oracle_text"] = text
        # First-pass oracle: for candidates the snapshot taken at the
        # start of attempt 2 is the post-attempt-1 state; for baselines
        # and single-attempt candidates first pass equals final.
        snapshot = run_dir / "snapshots" / "attempt-1-post"
        if arm == "candidate" and snapshot.is_dir():
            fp_code, fp_text = _oracle(
                snapshot,
                ev_dir / "oracle-first-pass.txt",
                oracle_rel,
                task_key,
            )
            result["first_pass_oracle_exit"] = fp_code
            result["first_pass_oracle_text"] = fp_text
        else:
            result["first_pass_oracle_exit"] = code
        diff = subprocess.run(
            [
                "diff",
                "-ruN",
                str(run_dir / "seed") + "/",
                str(workspace) + "/",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        (ev_dir / "workspace.diff").write_text(diff.stdout)
        result["workspace_digest"] = _tree_digest(workspace)
        binding = {
            "run_id": name,
            "manifest_id": manifest.manifest_id,
            "arm": arm,
            "model": route["model"]["model_spec"],
            "provider_routing": route["provider_routing"]["policy"],
            "seed_digest": seed_digest,
            "workspace_digest": result["workspace_digest"],
            "store_digest_before": store_digest_before,
        }
        (ev_dir / "run-binding.json").write_text(json.dumps(binding, indent=2))
        (ev_dir / "result.json").write_text(json.dumps(result, indent=2))
        _debit(result)
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
        usage_map = res.get("usage")
        observed = bool(
            isinstance(usage_map, dict) and usage_map.get("observed")
        )
        ledger.record(
            TrialResult(
                pair,
                family,
                arm,
                status,
                outcome,
                (
                    usage["input_tokens"] + usage["output_tokens"]
                    if observed
                    else None
                ),
                order,
            )
        )

    # --- Run 1: Task A learning episode on the governed path ---
    # The store is empty: recall runs, returns nothing, and the
    # governed attempt completes with zero obligations. The external
    # oracle then reports the hidden contract the attempt missed.
    fresh_check = {
        "scope_id": scope_id,
        "records_at_task_a": len(MemoryRepository(repo).list_scope(scope_id)),
        "store_digest": _file_digest(ledger_db),
    }
    (runs_dir / "store-freshness.json").write_text(
        json.dumps(fresh_check, indent=2)
    )
    if fresh_check["records_at_task_a"]:
        return _abort(totals, results, "study-4 store not fresh at task-a")
    a_res = execute("task-a-candidate", "task-a", "candidate", False)
    trial("pair-a", "learn-episode", "candidate", a_res, 0)
    if over_budget():
        return _abort(totals, results, "cap exceeded after task-a")

    # --- Run 2: governed improvement generation (learn-episode) ---
    a_ev = runs_dir / "task-a-candidate"
    a_diff = (a_ev / "workspace.diff").read_text(errors="replace")
    a_oracle_text = (a_ev / "oracle.txt").read_text(errors="replace")
    imp_dir = RUN_ROOT / "improvement"
    imp_dir.mkdir(parents=True, exist_ok=True)
    imp_ws = imp_dir / "workspace"
    shutil.copytree(RUN_ROOT / "task-a-candidate" / "workspace", imp_ws)
    shutil.copytree(imp_ws, imp_dir / "seed")
    (imp_dir / "home").mkdir(exist_ok=True)
    shutil.copy(DRIVER, imp_dir / "driver.py")
    imp_input = {
        "run_id": "improvement",
        "task_key": "improvement",
        "arm": "improvement",
        "task": {},
        "prompt": _improvement_prompt(
            str(tasks["task-a"]["prompt"]), a_diff, a_oracle_text.strip()
        ),
        "model_spec": route["model"]["model_spec"],
        "model_parameters": route["model"]["parameters"],
        "pricing": route["provider_routing"]["policy"]["pinned_upstream"][
            "pricing"
        ],
        "agent": AGENT,
    }
    (imp_dir / "arm-input.json").write_text(json.dumps(imp_input, indent=2))
    imp_res = _run_arm(imp_dir, "improvement", "improvement")
    ev_dir = runs_dir / "improvement"
    ev_dir.mkdir(parents=True, exist_ok=True)
    _collect(imp_dir, ev_dir)
    imp_res["oracle_exit"] = None
    _debit(imp_res)
    trial("pair-improvement", "learn-episode", "candidate", imp_res, 0)

    note = str(imp_res.get("final_text") or "").strip()
    (ev_dir / "note.txt").write_text(note + "\n")
    if note and imp_res.get("completed"):
        proposal = {
            "kind": "procedure",
            "scope_id": scope_id,
            "subject": "sentinel-cap-convention",
            "precondition": "editing sentinel modules or caps metadata",
            "evidence_refs": ("task-a-candidate", "improvement"),
            "freshness_epoch": 0,
        }
        kc = validate_knowledge_candidate(proposal)
        source_digests.append(kc.candidate_id)
        display = desk.present(
            subject_digest=kc.candidate_id,
            shown_text=note,
            audience=ACTOR,
            nonce=NONCE,
            expires_at=now + 3600,
            purpose=PURPOSE,
        )
        desk.open_display(display.request_id)
        decision = desk.submit(
            display.request_id,
            actor=ACTOR,
            nonce=NONCE,
            decision="approve",
            shown_text=note,
            display_revision=display.display_revision,
            client_event_id=CLIENT_EVENT,
            now=now,
        )
        content_digests: dict[str, str] = {}
        activated: dict[str, bool] = {}
        lifecycle_error = None
        if decision.status == "approved" and decision.receipt_digest:
            for template in suite["learning"]["rule_templates"]:
                body = dict(template["body"])
                body["summary"] = note
                mid = str(template["memory_id"])
                try:
                    record_mem = memory.propose_memory(
                        scope_id,
                        mid,
                        kind=str(template["kind"]),
                        content=json.dumps(body, sort_keys=True).encode(),
                        source_digest=kc.candidate_id,
                        evidence_refs=kc.evidence_refs,
                        at=now,
                    )
                    content_digests[mid] = record_mem.content_digest
                    activated[mid] = (
                        memory.activate_memory(
                            scope_id,
                            mid,
                            expected_revision=record_mem.revision,
                            at=now,
                        ).status
                        == "active"
                    )
                except CyranoError as exc:
                    # Lifecycle failures are evidence, not crashes: the
                    # pre-dispatch gate will mark affected pairs
                    # incomplete rather than repair or replace them.
                    activated[mid] = False
                    lifecycle_error = f"{exc.code}: {exc}"
                    break
        approval = {
            "candidate_id": kc.candidate_id,
            "memory_ids": list(memory_ids),
            "request_id": display.request_id,
            "decision": decision.status,
            "content_digests": content_digests,
            "activated": activated,
            "lifecycle_error": lifecycle_error,
            "receipt_digest": decision.receipt_digest,
            "receipt_fields": {
                "subject": kc.candidate_id,
                "nonce": NONCE,
                "actor": ACTOR,
                "client_event_id": CLIENT_EVENT,
                "purpose": PURPOSE,
            },
        }
    else:
        approval = {
            "decision": "no_improvement",
            "reason": "improvement run produced no note artifact",
        }
    (ev_dir / "improvement-approval.json").write_text(
        json.dumps(approval, indent=2)
    )
    with sqlite3.connect(str(ledger_db)) as _ckpt:
        _ckpt.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    if over_budget():
        return _abort(totals, results, "cap exceeded after improvement")

    # --- Runs 3-14: holdout pairs; candidates are integrity-gated ---
    holdout_keys = [
        k[: -len("-baseline")]
        for k in suite["ordering"]
        if k.endswith("-baseline")
    ]
    order = 1
    for key in holdout_keys:
        b_res = execute(f"{key}-baseline", key, "baseline", False)
        trial(
            str(tasks[key]["pair_id"]),
            str(tasks[key]["family"]),
            "baseline",
            b_res,
            order,
        )
        if over_budget():
            return _abort(
                totals, results, f"cap exceeded after {key}-baseline"
            )
        c_res = execute(f"{key}-candidate", key, "candidate", True)
        trial(
            str(tasks[key]["pair_id"]),
            str(tasks[key]["family"]),
            "candidate",
            c_res,
            order,
        )
        if over_budget():
            return _abort(
                totals, results, f"cap exceeded after {key}-candidate"
            )
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

    with sqlite3.connect(str(ledger_db)) as _ckpt:
        _ckpt.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    approval_file = runs_dir / "improvement" / "improvement-approval.json"
    bindings = sorted(runs_dir.glob("*/run-binding.json"))
    gates = sorted(runs_dir.glob("*/integrity-gate.json"))
    streams = sorted(
        p
        for p in runs_dir.glob("*/*.txt")
        if p.name
        in {
            "stdout.txt",
            "stderr.txt",
            "oracle.txt",
            "oracle-first-pass.txt",
            "note.txt",
        }
    )
    first_holdout = holdout_keys[0]
    last_holdout = holdout_keys[-1]
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
                    runs_dir
                    / f"{first_holdout}-candidate"
                    / "run-binding.json",
                )
            ]
        },
        "3-3": {"evidence_refs": [ref("receipt", approval_file)]},
        "3-4": {"evidence_refs": [ref("run_binding", b) for b in bindings]},
        "4-1": {"evidence_refs": [ref("events", s) for s in streams]},
        "4-2": {"evidence_refs": [ref("artifact", s) for s in streams]},
        "4-3": {
            "evidence_refs": [
                ref(
                    "artifact",
                    runs_dir / f"{first_holdout}-baseline" / "result.json",
                ),
                ref(
                    "artifact",
                    runs_dir / f"{first_holdout}-candidate" / "result.json",
                ),
                *[ref("review", g) for g in gates[:1]],
            ]
        },
        "4-4": {
            "evidence_refs": [
                ref(
                    "oracle_result",
                    runs_dir / f"{last_holdout}-candidate" / "oracle.txt",
                )
            ]
        },
    }
    imp_usage = _usage_of(imp_res)
    verdict = review_effectiveness(
        manifest,
        ledger,
        items,
        learning_overhead_units=(
            imp_usage["input_tokens"] + imp_usage["output_tokens"]
        ),
    )

    # Pre-registered cost-regression rule (suite.statistics): if the
    # candidate's observed spend exceeds 3.0x baseline, the verdict is
    # capped at inconclusive regardless of the quality delta. The rule
    # only tightens a verdict — it can never promote one.
    def _units(value: object) -> int:
        return value if isinstance(value, int) else 0

    cost_section = verdict.get("cost")
    baseline_units = (
        _units(cost_section.get("baseline_units", 0))
        if isinstance(cost_section, dict)
        else 0
    )
    candidate_units = (
        _units(cost_section.get("candidate_units", 0))
        if isinstance(cost_section, dict)
        else 0
    )
    candidate_total_units = candidate_units + (
        imp_usage["input_tokens"] + imp_usage["output_tokens"]
    )
    cost_regression = (
        baseline_units > 0 and candidate_total_units > 3.0 * baseline_units
    )
    if cost_regression and verdict.get("verdict") == "improved":
        verdict = dict(verdict)
        verdict["verdict"] = "inconclusive"
        verdict["reason"] = (
            "cost_regression: candidate spend exceeded 3.0x baseline"
        )
    first_pass_pairs = []
    for key in holdout_keys:
        b = next((r for r in results if r["run_id"] == f"{key}-baseline"), {})
        c = next((r for r in results if r["run_id"] == f"{key}-candidate"), {})
        first_pass_pairs.append(
            {
                "pair_id": tasks[key]["pair_id"],
                "baseline_first_pass": b.get("first_pass_oracle_exit") == 0,
                "candidate_first_pass": c.get("first_pass_oracle_exit") == 0,
                "candidate_final": c.get("oracle_exit") == 0,
                "candidate_attempts": c.get("attempts"),
                "candidate_governed_status": c.get("governed_status"),
                "correction_assisted": (
                    c.get("oracle_exit") == 0
                    and c.get("first_pass_oracle_exit") != 0
                ),
            }
        )
    final = {
        "study_id": STUDY_ID,
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
        "first_pass": first_pass_pairs,
        "study": {
            "permit_id": study["permit_id"],
            "settle": study["settle"],
            "spent_units": study["spent_units"],
        },
        "verdict": verdict,
        "cost_regression": cost_regression,
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
    (EVDIR / "study-result.json").write_text(
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
    (EVDIR / "study-result.json").write_text(
        json.dumps(
            {
                "study_id": STUDY_ID,
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
