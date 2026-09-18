"""WP23 study-4 arm driver — one confined run per invocation.

The harness prepares a run directory containing ``arm-input.json``
(the sealed task spec for this run), ``checkers/`` (trusted checker
specs, candidate only) and ``store.sqlite`` (the study-4 memory store
copy, candidate only). The driver assembles the arm's agent entirely
in-process: the baseline and improvement arms are a stock
``create_cli_agent`` graph; the candidate arm runs
``run_governed_work`` with ``MemoryGate.recall`` bound to the store —
no caller-staged records exist in this process.

The driver never calls the oracle and never writes outside its run
directory. Usage is captured through a provider-reported
``UsageMetadataCallbackHandler`` attached to the model instance; an
unobserved usage is recorded as missing, never zero.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import json
import shutil
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from deepagents_code.cyrano.kernel.actions import Grant

CODE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE))

TOOLS = (
    "read_file",
    "write_file",
    "edit_file",
    "delete",
    "ls",
    "glob",
    "grep",
)
RECURSION_LIMIT = 100


def _prices(arm_input: Mapping[str, Any]) -> tuple[float, float]:
    """Sealed pricing from run.json; defaults match the upstream pin."""
    pricing = arm_input.get("pricing", {})
    if isinstance(pricing, Mapping):
        try:
            return (
                float(str(pricing["prompt"])),
                float(str(pricing["completion"])),
            )
        except (KeyError, TypeError, ValueError):
            pass
    return 0.0000002, 0.0000006


def _digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


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


def _jsonable(value: object) -> object:
    """Convert evidence dataclasses to plain JSON; bytes digest only."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: _jsonable(getattr(value, f.name))
            for f in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_jsonable(v) for v in value]
    if isinstance(value, bytes):
        return _digest_bytes(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


@dataclass
class _Usage:
    """Provider-reported usage collected through the model callback."""

    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    observed: bool = False

    def record(self) -> dict[str, Any]:
        """Serialize with an honest missing marker."""
        return {
            "requests": self.requests,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "observed": self.observed,
        }


def _model(arm_input: Mapping[str, Any]):
    """Resolve the sealed model and attach the usage callback."""
    from langchain_core.callbacks.usage import (
        UsageMetadataCallbackHandler,
    )

    from deepagents_code.config import create_model

    model_spec = str(arm_input["model_spec"])
    params = dict(arm_input["model_parameters"])
    result = create_model(model_spec, extra_kwargs=params, cli_max_retries=0)
    handler = UsageMetadataCallbackHandler()
    model = result.model
    try:
        model.callbacks = [handler]
    except Exception:  # noqa: BLE001 - usage stays honestly unobserved
        pass
    return model, handler


def _usage_of(handler: Any) -> _Usage:
    usage = _Usage()
    summary = getattr(handler, "usage_metadata", None) or {}
    for entry in summary.values():
        if not isinstance(entry, Mapping):
            continue
        usage.input_tokens += int(str(entry.get("input_tokens") or 0))
        usage.output_tokens += int(str(entry.get("output_tokens") or 0))
    usage.requests = sum(
        int(str(e.get("requests") or 0))
        for e in summary.values()
        if isinstance(e, Mapping)
    )
    usage.observed = bool(summary)
    return usage


def _agent_kwargs(
    workspace: Path, arm_input: Mapping[str, Any]
) -> dict[str, Any]:
    """The stock agent assembly shared by every arm."""
    from langgraph.checkpoint.memory import InMemorySaver

    return {
        "assistant_id": str(arm_input["agent"]),
        "interactive": False,
        "auto_approve": True,
        "enable_ask_user": False,
        "enable_memory": False,
        "enable_skills": False,
        "enable_shell": False,
        "fs_tools": list(TOOLS),
        "cwd": workspace,
        "checkpointer": InMemorySaver(),
        "recursion_limit": RECURSION_LIMIT,
        "environ": {},
    }


async def _plain_run(
    arm_input: Mapping[str, Any], workspace: Path
) -> dict[str, Any]:
    """Baseline/improvement: one stock agent invocation, one attempt."""
    from langchain_core.messages import HumanMessage

    from deepagents_code.agent import create_cli_agent

    model, handler = _model(arm_input)
    agent, _backend = create_cli_agent(
        model=model,
        **_agent_kwargs(workspace, arm_input),
    )
    started = time.monotonic()
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=str(arm_input["prompt"]))]},
        {"configurable": {"thread_id": str(arm_input["run_id"])}},
    )
    wall = time.monotonic() - started
    messages = (
        result.get("messages", []) if isinstance(result, Mapping) else []
    )
    final_text = ""
    for message in reversed(list(messages)):
        if getattr(message, "type", "") == "ai":
            content = getattr(message, "content", "")
            final_text = content if isinstance(content, str) else str(content)
            break
    usage = _usage_of(handler)
    price_prompt, price_completion = _prices(arm_input)
    return {
        "completed": True,
        "wall_seconds": round(wall, 2),
        "usage": usage.record(),
        "attempts": 1,
        "final_text": final_text,
        "cost_usd": round(
            usage.input_tokens * price_prompt
            + usage.output_tokens * price_completion,
            6,
        ),
    }


def _grants(task: Mapping[str, Any]) -> "tuple[Grant, ...]":
    """Flatten the sealed per-task grant lists into Grant objects."""
    from deepagents_code.cyrano.kernel.actions import Grant

    spec = task.get("grants", {})
    merged: dict[str, set[str]] = {}
    if isinstance(spec, Mapping):
        for action in ("read", "create", "write_existing", "delete"):
            paths = spec.get(action, ())
            if not isinstance(paths, (list, tuple)):
                continue
            for path in paths:
                merged.setdefault(str(path), set()).add(action)
    return tuple(
        Grant(path=path, allow=frozenset(actions))
        for path, actions in sorted(merged.items())
    )


def _scope_id(run_dir: Path, arm_input: Mapping[str, Any]) -> str:
    """Derive the study scope id from the store's registered triple."""
    from deepagents_code.cyrano.sqlite.repository import (
        ScopedRepository,
    )

    repo = ScopedRepository.open(run_dir / "store.sqlite")
    try:
        scope = arm_input["scope"]
        return repo.register_scope(  # INSERT OR IGNORE — idempotent
            str(scope["tenant"]),
            str(scope["user"]),
            str(scope["workspace"]),
        )
    finally:
        repo.close()


def _memory_gate(run_dir: Path, arm_input: Mapping[str, Any]):
    """Recall-backed gates over the study store; nothing staged."""
    from deepagents_code.cyrano.context.binding import MemoryView
    from deepagents_code.cyrano.contracts.canonical import digest
    from deepagents_code.cyrano.dcode.governed_runtime import MemoryGate
    from deepagents_code.cyrano.dcode.recall import task_recall
    from deepagents_code.cyrano.memory.checkers import (
        TrustedCheckerRegistry,
    )
    from deepagents_code.cyrano.memory.repository import (
        MemoryRepository,
    )
    from deepagents_code.cyrano.memory.service import MemoryService
    from deepagents_code.cyrano.sqlite.repository import (
        ScopedRepository,
    )

    store = run_dir / "store.sqlite"
    scope_id = str(arm_input["scope_id"])

    def fresh_repo():
        return ScopedRepository.open(store)

    def recall(context):
        repo = fresh_repo()
        try:
            return task_recall(
                service=MemoryService(MemoryRepository(repo)),
                repository=MemoryRepository(repo),
                context=context,
            )
        finally:
            repo.close()

    def is_current(mid: str, rev: int) -> bool:
        repo = fresh_repo()
        try:
            record = MemoryRepository(repo).get(scope_id, mid)
        finally:
            repo.close()
        return (
            record is not None
            and record.revision == rev
            and record.status == "active"
        )

    def live_view() -> MemoryView:
        repo = fresh_repo()
        try:
            records = MemoryRepository(repo).list_scope(scope_id)
        finally:
            repo.close()
        revoked = frozenset(
            r.memory_id for r in records if r.status != "active"
        )
        return MemoryView(digest(sorted(revoked)), "live", revoked)

    files = arm_input.get("checker_files", {})
    registry = TrustedCheckerRegistry.from_trusted_files(
        run_dir / "checkers",
        {str(k): str(v) for k, v in dict(files).items()},
    )
    digests = arm_input.get("available_source_digests", ())
    if not isinstance(digests, (list, tuple)):
        digests = ()
    governed = arm_input.get("governed", {})
    admitted = (
        governed.get("admitted_kinds", ())
        if isinstance(governed, Mapping)
        else ()
    )
    if not isinstance(admitted, (list, tuple)):
        admitted = ()
    return MemoryGate(
        records=(),
        rule_bodies={},
        available_source_digests=frozenset(str(d) for d in digests),
        registry=registry,
        is_current=is_current,
        view_provider=live_view,
        recall=recall,
        admitted_kinds=frozenset(str(k) for k in admitted),
    )


def _epoch_and_context(
    arm_input: Mapping[str, Any],
    *,
    view_digest: str,
    profile_digest: str,
):
    """Real epoch + compiled context bound to the live view."""
    from deepagents_code.cyrano.context.compiler import (
        Block,
        compile_context,
    )
    from deepagents_code.cyrano.context.epochs import epoch_for

    epoch = epoch_for(
        tool_inventory_digest=_digest_bytes(
            json.dumps(sorted(TOOLS)).encode()
        ),
        model_identity=str(arm_input["model_spec"]),
        route="openrouter:deepinfra",
        release_digest=str(arm_input["runtime_digest"]),
        profile_digest=profile_digest,
        memory_view_digest=view_digest,
        generation=0,
    )
    compiled = compile_context(
        [Block(block_id="task", order=0, text=str(arm_input["prompt"]))],
        {"run_id": str(arm_input["run_id"])},
    )
    return epoch, compiled


async def _candidate_run(
    run_dir: Path,
    arm_input: Mapping[str, Any],
    workspace: Path,
) -> dict[str, Any]:
    """The governed path: recall -> obligations -> permit -> correct."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )

    from deepagents_code.agent import create_cli_agent
    from deepagents_code.cyrano.dcode.governed_runtime import (
        ApprovalGate,
        GovernedRunConfig,
        run_governed_work,
    )
    from deepagents_code.cyrano.dcode.probes import run_all_probes
    from deepagents_code.cyrano.kernel.approvals import ApprovalDesk
    from deepagents_code.cyrano.planning.subject import (
        GovernedWorkPlan,
        WorkUnitSpec,
    )

    task = arm_input["task"]
    task_key = str(arm_input["task_key"])
    run_id = str(arm_input["run_id"])
    scope_id = _scope_id(run_dir, arm_input)
    arm_input = dict(arm_input)
    arm_input["scope_id"] = scope_id
    memory = _memory_gate(run_dir, arm_input)
    seed_digest = _tree_digest(run_dir / "seed")

    key = Ed25519PrivateKey.generate()
    audit_events: list[str] = []
    approval = ApprovalGate(
        desk=ApprovalDesk(),
        signing_key=key,
        trust_root=key.public_key(),
        audience=str(arm_input["actor"]),
        is_revoked=lambda _pid: False,
        audit=audit_events.append,
        decide=lambda _display: "approve",
    )
    governed = arm_input["governed"]
    write_paths = tuple(str(p) for p in task["write_paths"])
    plan = GovernedWorkPlan(
        plan_id=f"plan-{task_key}",
        revision=1,
        requirements=(f"REQ:{task_key}",),
        units=(
            WorkUnitSpec(
                unit_id="impl",
                requirement_ids=(f"REQ:{task_key}",),
                acceptance_ids=(f"ACC:{task_key}",),
                write_paths=write_paths,
            ),
        ),
        budget_cap=int(governed["max_attempts"]),
    )
    view = memory.view_provider() if memory.view_provider else None
    epoch, compiled = _epoch_and_context(
        arm_input,
        view_digest="" if view is None else view.view_digest,
        profile_digest=_tree_digest(run_dir),
    )
    snapshots = run_dir / "snapshots"

    def on_attempt(attempt: int) -> None:
        if attempt >= 2:
            shutil.copytree(
                workspace,
                snapshots / f"attempt-{attempt - 1}-post",
                dirs_exist_ok=True,
            )

    config = GovernedRunConfig(
        plan=plan,
        task_text=str(arm_input["prompt"]),
        scope_id=scope_id,
        workspace=workspace,
        grants=_grants(task),
        tools=frozenset(TOOLS),
        requirements_doc={
            "spec": {f"REQ:{task_key}": "satisfy the sealed task prompt"}
        },
        source_snapshot={"tree": seed_digest},
        scope={
            "scope_id": scope_id,
            "tenant": str(arm_input["scope"]["tenant"]),
            "user": str(arm_input["scope"]["user"]),
            "workspace": str(arm_input["scope"]["workspace"]),
        },
        now=lambda: int(time.time()),
        epoch=epoch,
        compiled=compiled,
        cost_cap=int(governed["cost_cap_per_obligation"]),
        max_attempts=int(governed["max_attempts"]),
        permit_ttl=int(governed["permit_ttl_seconds"]),
        recall_limit=int(governed["recall_limit"]),
        run_id=run_id,
    )
    model, handler = _model(arm_input)

    def factory(registry):
        agent, _backend = create_cli_agent(
            model=model,
            extension_registry=registry,
            **_agent_kwargs(workspace, arm_input),
        )
        return agent

    started = time.monotonic()
    evidence = await run_governed_work(
        config=config,
        memory=memory,
        approval=approval,
        probe_report=run_all_probes(),
        agent_factory=factory,
        on_attempt_start=on_attempt,
    )
    wall = time.monotonic() - started
    usage = _usage_of(handler)
    price_prompt, price_completion = _prices(arm_input)
    return {
        "completed": evidence.status
        in {
            "satisfied",
            "corrected",
            "violated",
            "unverifiable",
        },
        "governed_status": evidence.status,
        "refusal_code": evidence.refusal_code,
        "wall_seconds": round(wall, 2),
        "usage": usage.record(),
        "attempts": evidence.attempts,
        "cost_usd": round(
            usage.input_tokens * price_prompt
            + usage.output_tokens * price_completion,
            6,
        ),
        "evidence": _jsonable(evidence),
        "audit": list(audit_events),
        "scope_id": scope_id,
    }


def main() -> int:
    """Run one arm inside its confined run directory."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--code-root",
        default=None,
        help="libs/code path — required when the driver is a confined copy",
    )
    args = parser.parse_args()
    if args.code_root:
        sys.path.insert(0, str(Path(args.code_root)))
    run_dir = Path(args.run_dir)
    arm_input = json.loads(
        (run_dir / "arm-input.json").read_text(encoding="utf-8")
    )
    workspace = run_dir / "workspace"
    out: dict[str, object] = {
        "run_id": arm_input["run_id"],
        "arm": args.arm,
        "task_key": args.task,
        "seed_digest": _tree_digest(run_dir / "seed"),
        "workspace_digest_before": _tree_digest(workspace),
    }
    try:
        if args.arm == "candidate":
            result = asyncio.run(_candidate_run(run_dir, arm_input, workspace))
        else:
            result = asyncio.run(_plain_run(arm_input, workspace))
    except Exception as exc:  # driver-level failure — run is failed
        out.update(
            {
                "completed": False,
                "driver_error": f"{type(exc).__name__}: {exc}",
            }
        )
        (run_dir / "result.json").write_text(
            json.dumps(out, indent=2, default=str)
        )
        return 1
    out.update(result)
    out["workspace_digest_after"] = _tree_digest(workspace)
    store = run_dir / "store.sqlite"
    if store.is_file():
        out["store_digest_after"] = _digest_bytes(store.read_bytes())
    (run_dir / "result.json").write_text(
        json.dumps(out, indent=2, default=str)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
