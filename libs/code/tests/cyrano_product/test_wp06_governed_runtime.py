"""WP06 governed-obligation runtime through the real assembly path.

These tests run the actual dcode agent graph (``create_cli_agent`` +
extension registry) with a scripted local chat model — no provider
calls — and prove the governed channel end to end:

    active scope_rule → projection → plan linkage → subject digest →
    approval desk → SignedPermit → brokered tool mediation → real
    workspace writes → deterministic checker verification → bounded
    correction → application evidence.

Revocation, staleness, supersession, expiry and budget exhaustion all
fail closed. The wire observer sits at the final request-construction
boundary (``wrap_model_call`` immediately before the provider handler)
so EVAL-WIRE-01 evidence is digest-only and honest about what it saw.
"""

import dataclasses
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver

from deepagents_code._fake_models import _ToolBindingFakeModel
from deepagents_code.cyrano.context.binding import MemoryView
from deepagents_code.cyrano.context.compiler import CompiledContext
from deepagents_code.cyrano.context.epochs import epoch_for
from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.dcode.governed_runtime import (
    FEEDBACK_MARKER,
    ApprovalGate,
    GovernedRunConfig,
    MemoryGate,
    run_governed_work,
)
from deepagents_code.cyrano.improvement.knowledge_lane import (
    validate_knowledge_candidate,
)
from deepagents_code.cyrano.kernel.actions import Grant
from deepagents_code.cyrano.kernel.approvals import (
    ApprovalDesk,
)
from deepagents_code.cyrano.memory import (
    MemoryRepository,
    MemoryService,
)
from deepagents_code.cyrano.memory.checkers import (
    TrustedCheckerRegistry,
)
from deepagents_code.cyrano.memory.obligations import (
    project_obligations,
)
from deepagents_code.cyrano.planning.subject import (
    GovernedWorkPlan,
    WorkUnitSpec,
)
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

ROOT = Path(__file__).resolve().parents[2]
TARGET_DDL = (ROOT / "cyrano/contracts/sql/target-schema.sql").read_text()

KEY = Ed25519PrivateKey.generate()
PUB = KEY.public_key()
SRC = frozenset({"src:1"})

RULE_BODY = json.dumps(
    {
        "rule_id": "widgetbox-sidecar-v2",
        "checker_id": "sidecar-check",
        "applicability": {
            "write_globs": ["meta/*.json", "widgetbox/*.py"],
            "operations": ["create", "modify"],
        },
        "exceptions": [
            {
                "exception_id": "grandfather-alpha",
                "path_globs": ["meta/alpha.json"],
            }
        ],
        "summary": "sidecars use widgetbox.sidecar/2",
    }
).encode()

CHECKER_BODY = json.dumps(
    {
        "kind": "paired_files",
        "params": {
            "trigger": "widgetbox/*.py",
            "derive": "meta/{stem}.json",
            "required": True,
            "json_fields": {
                "schema": {"equals": "widgetbox.sidecar/2"},
                "compat": {"equals": "widgetbox/2"},
                "lifecycle": {
                    "one_of": ["stable", "beta", "deprecated", "retired"]
                },
                "name": {"matches_stem": True},
                "owners": {"required": True},
            },
        },
    }
).encode()

V1_SIDECAR = json.dumps(
    {
        "name": "alpha",
        "schema": "widgetbox.sidecar/1",
        "lifecycle": "stable",
        "owners": ["w"],
    }
)


def _v2(name: str) -> str:
    return json.dumps(
        {
            "name": name,
            "schema": "widgetbox.sidecar/2",
            "lifecycle": "stable",
            "compat": "widgetbox/2",
            "owners": ["w"],
        }
    )


_PY = "def widget():\n    return 1\n"


class _ScriptedModel(_ToolBindingFakeModel):
    """Prompt-driven fake model emitting scripted tool calls."""

    script: Any = None

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,  # noqa: ARG002
        run_manager: Any = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> ChatResult:
        """Delegate to the test-supplied script over the messages."""
        assert self.script is not None
        return ChatResult(
            generations=[ChatGeneration(message=self.script(messages))]
        )

    @property
    def _llm_type(self) -> str:
        """Model type label for wire evidence."""
        return "scripted-fake"


def _abs(workspace: Path, path: str) -> str:
    """Real host path for a workspace-relative path.

    The governed backend runs ``virtual_mode=False``, so (like a real
    model told its cwd) calls carry absolute paths.
    """
    return str(workspace / path)


def _write_calls(
    workspace: Path,
    writes: dict[str, str],
    prefix: str = "w",
) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "write_file",
                "args": {
                    "file_path": _abs(workspace, path),
                    "content": content,
                },
                "id": f"{prefix}-{i}",
            }
            for i, (path, content) in enumerate(writes.items())
        ],
    )


def _read_calls(workspace: Path, paths: tuple[str, ...]) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "read_file",
                "args": {"file_path": _abs(workspace, path)},
                "id": f"r-{i}",
            }
            for i, path in enumerate(paths)
        ],
    )


def _has_tool_results(messages: list[BaseMessage]) -> bool:
    return any(isinstance(m, ToolMessage) for m in messages)


def _correction_turn(messages: list[BaseMessage]) -> bool:
    return any(
        isinstance(m, HumanMessage)
        and isinstance(m.content, str)
        and m.content.startswith(FEEDBACK_MARKER)
        for m in messages
    )


def _registry() -> TrustedCheckerRegistry:
    registry = TrustedCheckerRegistry()
    registry.register("sidecar-check", CHECKER_BODY)
    return registry


@pytest.fixture
def env(tmp_path):
    """Memory store, workspace, plan and approval inputs."""
    repo = ScopedRepository.create(tmp_path / "db.sqlite3", TARGET_DDL)
    scope = repo.register_scope("t1", "u1", "w1")
    service = MemoryService(MemoryRepository(repo))
    service.propose_memory(
        scope,
        "rule-sidecar",
        kind="scope_rule",
        content=RULE_BODY,
        source_digest="src:1",
        evidence_refs=("e:1",),
        at=1,
    )
    service.activate_memory(
        scope, "rule-sidecar", expected_revision=1, at=2
    )

    workspace = tmp_path / "ws"
    (workspace / "meta").mkdir(parents=True)
    (workspace / "widgetbox").mkdir()
    # Study-3 style: a visible legacy v1 exemplar the rule grandfathers.
    (workspace / "meta" / "alpha.json").write_text(V1_SIDECAR)

    plan = GovernedWorkPlan(
        plan_id="plan-1",
        revision=1,
        requirements=("REQ:sidecar",),
        units=(
            WorkUnitSpec(
                unit_id="u1",
                requirement_ids=("REQ:sidecar",),
                acceptance_ids=("ACC:sidecar",),
                write_paths=("widgetbox/x.py", "meta/x.json"),
                test_recipe="sidecar-check",
                test_oracle="verify_obligations",
                cost_cap=4,
            ),
        ),
        budget_cap=8,
    )
    state = {
        "clock": [10],
        "revoked": set(),
        "audit": [],
        "service": service,
        "repo": repo,
        "db_path": tmp_path / "db.sqlite3",
        "scope": scope,
        "workspace": workspace,
        "plan": plan,
    }
    yield state
    repo.close()


def _fresh_service(env) -> MemoryService:
    """A service on a fresh connection — safe from any thread.

    The fixture's main service lives on the main thread's connection;
    agent-loop callbacks run on executor threads, so cross-thread
    mutation/recheck must go through a per-call connection to the
    same SQLite file (the store, not the object, is shared state).
    """
    return MemoryService(
        MemoryRepository(ScopedRepository.open(env["db_path"]))
    )


def _records(env):
    return tuple(env["service"]._repo.list_scope(env["scope"]))


def _bodies(env) -> dict[str, bytes]:
    return {
        r.memory_id: env["service"]._repo.get_content(
            env["scope"], r.content_digest
        )
        or b""
        for r in _records(env)
    }


def _is_current(env) -> Callable[[str, int], bool]:
    def check(mid: str, rev: int) -> bool:
        service = _fresh_service(env)
        try:
            record = service.get(env["scope"], mid)
        finally:
            service._repo._repo.close()
        return (
            record is not None
            and record.revision == rev
            and record.status == "active"
        )

    return check


def _view(env) -> MemoryView:
    revoked = frozenset(sorted(env["revoked"]))
    return MemoryView(digest(sorted(revoked)), "rel-1", revoked)


def _gates(
    env,
    *,
    registry: TrustedCheckerRegistry | None = None,
    cost_cap: int | None = 4,
) -> tuple[GovernedRunConfig, MemoryGate, ApprovalGate]:
    audit: list[str] = env["audit"]
    config = GovernedRunConfig(
        plan=env["plan"],
        task_text="Implement the widget and its v2 sidecar.",
        scope_id=env["scope"],
        workspace=env["workspace"],
        grants=(
            Grant(
                path="widgetbox/x.py",
                allow=frozenset({"create", "write_existing"}),
            ),
            Grant(
                path="meta/x.json",
                allow=frozenset({"create", "write_existing"}),
            ),
            Grant(path="meta/alpha.json", allow=frozenset({"read"})),
        ),
        tools=frozenset({"write_file", "read_file", "edit_file"}),
        requirements_doc={"spec": {"REQ:sidecar": "v2 sidecar required"}},
        source_snapshot={"tree": "snap-1"},
        scope={"scope_id": env["scope"]},
        now=lambda: env["clock"][0],
        cost_cap=cost_cap,
        run_id="run-1",
    )
    memory = MemoryGate(
        records=_records(env),
        rule_bodies=_bodies(env),
        available_source_digests=SRC,
        registry=registry or _registry(),
        is_current=_is_current(env),
        memory_view=_view(env),
        view_provider=lambda: _view(env),
    )
    approval = ApprovalGate(
        desk=ApprovalDesk(),
        signing_key=KEY,
        trust_root=PUB,
        audience="operator",
        is_revoked=lambda pid: pid in env["revoked"],
        audit=audit.append,
    )
    return config, memory, approval


def _agent_factory(script, workspace: Path):
    def build(registry):
        import os

        from deepagents_code.agent import create_cli_agent

        agent, _backend = create_cli_agent(
            model=_ScriptedModel(script=script),
            assistant_id="governed-test",
            interactive=False,
            auto_approve=True,
            enable_ask_user=False,
            enable_memory=False,
            enable_skills=False,
            enable_shell=False,
            system_prompt="You write files as instructed.",
            cwd=workspace,
            checkpointer=InMemorySaver(),
            extension_registry=registry,
            enforce_model_policy=False,
            environ={
                **os.environ,
                # The native extension mechanism is experimental;
                # governed runs opt in explicitly (UH-OPS-03).
                "DEEPAGENTS_CODE_EXPERIMENTAL": "1",
            },
        )
        return agent

    return build


ALL_PROBES = {
    "extension_loading": "verified",
    "async_middleware": "verified",
    "child_observation": "verified",
    "tool_mediation": "verified",
    "sandbox_isolation": "verified",
    "trusted_approval": "verified",
    "context_manifest": "verified",
    "cancel_recovery": "verified",
}


async def _run(env, script, **overrides):
    registry = overrides.pop("registry", None) or _registry()
    config, memory, approval = _gates(env, registry=registry, **overrides)
    return await run_governed_work(
        config=config,
        memory=memory,
        approval=approval,
        probe_report=ALL_PROBES,
        agent_factory=_agent_factory(script, env["workspace"]),
    )


async def test_end_to_end_satisfied(env):
    """Full governed path: rule → plan → permit → writes → verified."""

    def script(messages):
        if _has_tool_results(messages):
            return AIMessage(content="done")
        return _write_calls(
            env["workspace"],
            {"widgetbox/x.py": _PY, "meta/x.json": _v2("x")}
        )

    evidence = await _run(env, script)
    assert evidence.status == "satisfied"
    assert (env["workspace"] / "meta" / "x.json").exists()
    assert all(r.verdict.state == "satisfied" for r in evidence.reports)
    assert all(v.state == "applied" for v in evidence.verdicts)
    assert evidence.wire
    assert all(e.wire_confirmed for e in evidence.wire)
    assert evidence.receipts[0].wire_confirmed is True
    assert evidence.permit_id is not None
    assert "widgetbox/x.py" in evidence.touched_paths
    # The grandfathered v1 exemplar was untouched: no regression.
    assert "meta/alpha.json" not in evidence.touched_paths


async def test_study3_regression_correction(env):
    """Legacy exemplar wins the first pass; the checker forces v2.

    Offline regression only — this measures the correction path, not
    live model lift.
    """

    def script(messages):
        if _correction_turn(messages):
            return _write_calls(
            env["workspace"],
                {"meta/x.json": _v2("x")}, prefix="fix"
            )
        if _has_tool_results(messages):
            return AIMessage(content="done")
        # First pass imitates the visible v1 exemplar.
        return _write_calls(
            env["workspace"],
            {
                "widgetbox/x.py": _PY,
                "meta/x.json": json.dumps(
                    {
                        "name": "x",
                        "schema": "widgetbox.sidecar/1",
                        "lifecycle": "stable",
                        "owners": ["w"],
                    }
                ),
            }
        )

    evidence = await _run(env, script)
    assert evidence.status == "corrected"
    ledger = evidence.ledgers[0]
    assert ledger.outcome == "corrected"
    assert ledger.first_failure is not None
    assert ledger.first_failure.verdict.state == "violated"
    assert ledger.attempts and ledger.attempts[-1][0].verdict.state == (
        "satisfied"
    )
    # The corrected postimage is the real v2 bytes.
    final = json.loads((env["workspace"] / "meta" / "x.json").read_text())
    assert final["schema"] == "widgetbox.sidecar/2"


async def test_revision_change_after_approval_fails(env):
    """A rule moving past the bound revision aborts the run."""

    def script(messages):
        if _has_tool_results(messages):
            return AIMessage(content="done")
        # Simulate revision bump mid-run: after the model request the
        # rule record moves (supersede bumps revision through CAS).
        service = _fresh_service(env)
        try:
            service.invalidate(env["scope"], "rule-sidecar", at=3)
        finally:
            service._repo._repo.close()
        return _write_calls(
            env["workspace"],
            {"widgetbox/x.py": _PY, "meta/x.json": _v2("x")}
        )

    evidence = await _run(env, script)
    assert evidence.status == "aborted"
    assert evidence.refusal_code in {
        "STALE_REVISION",
        "MEMORY_REVOKED",
    }


async def test_revocation_before_dispatch(env):
    """Revocation after approval but before dispatch fails closed."""
    config, memory, approval = _gates(env)
    evidence = await run_governed_work(
        config=config,
        memory=memory,
        approval=approval,
        probe_report=ALL_PROBES,
        agent_factory=_agent_factory(
            lambda messages: AIMessage(content="never runs"),
            env["workspace"],
        ),
        on_attempt_start=lambda _n: env["revoked"].add(
            "rule-sidecar"
        ),
    )
    assert evidence.status == "refused"
    assert evidence.refusal_code == "MEMORY_REVOKED"
    assert not (env["workspace"] / "meta" / "x.json").exists()
    assert evidence.obligations  # the rule projected; revocation stopped it


async def test_revocation_during_run(env):
    """Revocation after attempt 1 blocks the correction dispatch."""

    def script(messages):
        if _correction_turn(messages):
            return _write_calls(env["workspace"], {"meta/x.json": _v2("x")})
        if _has_tool_results(messages):
            env["revoked"].add("rule-sidecar")
            return AIMessage(content="done")
        return _write_calls(
            env["workspace"],
            {
                "widgetbox/x.py": _PY,
                "meta/x.json": json.dumps(
                    {
                        "name": "x",
                        "schema": "widgetbox.sidecar/1",
                        "lifecycle": "stable",
                        "owners": ["w"],
                    }
                ),
            }
        )

    evidence = await _run(env, script)
    assert evidence.status == "aborted"
    assert evidence.refusal_code == "MEMORY_REVOKED"


def _move_checker(registry: TrustedCheckerRegistry) -> None:
    """Re-register a valid-but-different spec — the digest drifts."""
    registry.register(
        "sidecar-check",
        json.dumps(
            {
                "kind": "paired_files",
                "params": {
                    "trigger": "other/*.py",
                    "derive": "meta/{stem}.yaml",
                },
            }
        ).encode(),
    )


async def test_checker_digest_change_fails(env):
    """A checker re-registered post-approval is unverifiable."""

    def script(messages):
        if _has_tool_results(messages):
            return AIMessage(content="done")
        return _write_calls(
            env["workspace"],
            {"widgetbox/x.py": _PY, "meta/x.json": _v2("x")}
        )

    registry = _registry()
    config, memory, approval = _gates(env, registry=registry)
    evidence = await run_governed_work(
        config=config,
        memory=memory,
        approval=approval,
        probe_report=ALL_PROBES,
        agent_factory=_agent_factory(script, env["workspace"]),
        on_attempt_start=lambda _n: _move_checker(registry),
    )
    assert evidence.status in {"unverifiable", "aborted"}
    assert all(
        r.verdict.state != "satisfied" for r in evidence.reports
    )


async def test_stale_view_fails(env):
    """A pinned view that no longer matches aborts the bind."""
    config, memory, approval = _gates(env)
    stale_epoch = epoch_for(
        tool_inventory_digest="t",
        model_identity="m",
        route=None,
        release_digest="r",
        profile_digest="p",
        memory_view_digest="view-other",
    )
    compiled = CompiledContext(
        stable_text="s",
        dynamic_text="",
        stable_digest="sd",
        request_digest="rd",
        stable_bytes=1,
        block_digests=(),
    )
    config = dataclasses.replace(
        config, epoch=stale_epoch, compiled=compiled
    )
    evidence = await run_governed_work(
        config=config,
        memory=memory,
        approval=approval,
        probe_report=ALL_PROBES,
        agent_factory=_agent_factory(
            lambda messages: AIMessage(content="never"),
            env["workspace"],
        ),
    )
    assert evidence.status == "refused"
    assert evidence.refusal_code == "STALE_EPOCH"


async def test_expired_rule_excluded(env):
    service, scope = env["service"], env["scope"]
    service.propose_memory(
        scope,
        "rule-expired",
        kind="scope_rule",
        content=RULE_BODY,
        source_digest="src:1",
        evidence_refs=("e:1",),
        at=1,
        expires_at=5,
    )
    # Same-kind activation needs explicit supersession — this also
    # exercises the superseded-exclusion branch on the old rule.
    service.activate_memory(
        scope,
        "rule-expired",
        expected_revision=1,
        supersedes="rule-sidecar",
        at=2,
    )
    records = _records(env)
    projection = project_obligations(
        list(records),
        scope_id=scope,
        now=10,
        available_source_digests=SRC,
        rule_bodies=_bodies(env),
        checker_digests=_registry().digests(),
    )
    excluded = dict(projection.excluded)
    assert excluded.get("rule-expired") == "expired"


async def test_unattached_obligation_refused(env):
    """A rule whose selector matches no unit refuses the run."""
    plan = GovernedWorkPlan(
        plan_id="plan-2",
        revision=1,
        requirements=("REQ:other",),
        units=(
            WorkUnitSpec(
                unit_id="u1",
                requirement_ids=("REQ:other",),
                acceptance_ids=("ACC:other",),
                write_paths=("other/out.txt",),
                test_recipe="sidecar-check",
                test_oracle="verify_obligations",
                cost_cap=4,
            ),
        ),
        budget_cap=8,
    )
    env["plan"] = plan
    evidence = await _run(
        env, lambda messages: AIMessage(content="never")
    )
    assert evidence.status == "refused"
    assert evidence.refusal_code == "UNBOUND_OBLIGATION"


async def test_correction_budget_exhaustion(env):
    """Corrections stop inside the bound; failure stays recorded."""

    def script(messages):
        if _correction_turn(messages):
            # Correction keeps producing v1 — never satisfies.
            return _write_calls(
            env["workspace"],
                {
                    "meta/x.json": json.dumps(
                        {
                            "name": "x",
                            "schema": "widgetbox.sidecar/1",
                            "lifecycle": "stable",
                            "owners": ["w"],
                        }
                    )
                },
                prefix="fix",
            )
        if _has_tool_results(messages):
            return AIMessage(content="done")
        return _write_calls(
            env["workspace"],
            {
                "widgetbox/x.py": _PY,
                "meta/x.json": json.dumps(
                    {
                        "name": "x",
                        "schema": "widgetbox.sidecar/1",
                        "lifecycle": "stable",
                        "owners": ["w"],
                    }
                ),
            }
        )

    evidence = await _run(env, script, cost_cap=1)
    assert evidence.status == "violated"
    ledger = evidence.ledgers[0]
    assert ledger.outcome == "budget_exhausted"
    assert ledger.first_failure is not None
    assert ledger.spent_units >= 1


async def test_denied_write_never_hits_disk(env):
    """A write outside the grants is refused by the broker."""

    def script(messages):
        if _has_tool_results(messages):
            denied = any(
                isinstance(m, ToolMessage)
                and "SCOPE_DENIED" in str(m.content)
                for m in messages
            )
            if denied:
                return AIMessage(content="blocked, stopping")
            return AIMessage(content="done")
        return _write_calls(
            env["workspace"],
            {"etc/evil.txt": "x", "widgetbox/x.py": _PY}
        )

    evidence = await _run(env, script)
    assert not (env["workspace"] / "etc" / "evil.txt").exists()
    assert any("SCOPE_DENIED" in d or "CREATE" in d for d in evidence.denials)


async def test_unknown_tool_denied(env):
    """An unlisted tool is denied before it can run."""

    def script(messages):
        if _has_tool_results(messages):
            return AIMessage(content="done")
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "execute",
                    "args": {"command": "rm -rf /"},
                    "id": "x-1",
                }
            ],
        )

    evidence = await _run(env, script)
    assert any("UNSUPPORTED_TOOL" in d for d in evidence.denials)


async def test_wire_evidence_is_digest_only(env):
    """Wire records carry digests and labels, never content."""

    def script(messages):
        if _has_tool_results(messages):
            return AIMessage(content="done")
        return _write_calls(env["workspace"], {"widgetbox/x.py": _PY})

    evidence = await _run(env, script)
    assert evidence.wire
    first = evidence.wire[0]
    assert first.wire_confirmed is True
    assert first.message_digest.startswith("sha256:")
    assert first.tools_digest.startswith("sha256:")
    assert first.provider == "scripted-fake"
    # No message text ever lands in the evidence record.
    assert not hasattr(first, "messages")
    assert not hasattr(first, "content")


async def test_scope_rule_subkind_prefix_no_authority(env):
    """``scope_rule.<x>`` alone never grants obligation authority."""
    service, scope = env["service"], env["scope"]
    # Admission gate rejects the unregistered sub-kind outright.
    with pytest.raises(CyranoError) as err:
        validate_knowledge_candidate(
            {
                "kind": "scope_rule.experimental",
                "scope_id": scope,
                "subject": "tester",
                "evidence_refs": ["e:1"],
                "freshness_epoch": 1,
                "content": "{}",
            }
        )
    assert err.value.code == "INPUT_INVALID"
    # A record that bypassed the lane is still excluded at projection.
    service.propose_memory(
        scope,
        "rule-sneaky",
        kind="scope_rule.experimental",
        content=RULE_BODY,
        source_digest="src:1",
        evidence_refs=("e:1",),
        at=1,
    )
    service.activate_memory(
        scope, "rule-sneaky", expected_revision=1, at=2
    )
    projection = project_obligations(
        list(_records(env)),
        scope_id=scope,
        now=10,
        available_source_digests=SRC,
        rule_bodies=_bodies(env),
        checker_digests=_registry().digests(),
    )
    excluded = dict(projection.excluded)
    assert excluded.get("rule-sneaky") == "unregistered_kind"
    assert not any(
        o.memory_id == "rule-sneaky" for o in projection.obligations
    )


# --------------------- extension startup modes ----------------------


def _load_extension():
    """Load the plugin entry point the way the host does — by path."""
    import importlib.util

    path = ROOT / "cyrano/plugins/cyrano/extension.py"
    spec = importlib.util.spec_from_file_location(
        "cyrano_extension", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _extension_api(tmp_path):
    from deepagents_code.extensions.api import (
        ExtensionAPI,
        ExtensionMode,
    )
    from deepagents_code.extensions.registry import (
        ExtensionRegistry,
        SourceInfo,
    )

    registry = ExtensionRegistry()
    api = ExtensionAPI(
        registry,
        SourceInfo(
            path=ROOT / "cyrano/plugins/cyrano/extension.py",
            source_id="cyrano",
        ),
        cwd=tmp_path,
        mode=ExtensionMode.HEADLESS,
    )
    return api, registry


def _session_manifest(tmp_path: Path) -> Path:
    """A minimally valid governed-session manifest."""
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
    )

    from deepagents_code.cyrano.kernel.approvals import issue_permit

    workspace = tmp_path / "ws"
    workspace.mkdir()
    permit = issue_permit(
        KEY,
        permit_id="permit-manifest",
        subject_digest="sd",
        shown_digest="shown",
        user_event_id="evt-1",
        scope_id="t1",
        purpose="execute",
        audience="operator",
        nonce="n-1",
        issued_at=1,
        expires_at=10_000,
    )
    manifest = {
        "permit": dataclasses.asdict(permit),
        "trust_root": PUB.public_bytes(
            Encoding.Raw, PublicFormat.Raw
        ).hex(),
        "root": str(workspace),
        "subject_digest": "sd",
        "grants": [{"path": "x.txt", "allow": ["create"]}],
        "tools": ["write_file"],
        "audit_path": str(tmp_path / "audit.log"),
        "revoked_permits": [],
    }
    path = tmp_path / "session.json"
    path.write_text(json.dumps(manifest))
    return path


async def test_extension_governed_with_manifest(
    tmp_path, monkeypatch
):
    """Governed mode + sentinel + manifest registers mediation."""
    module = _load_extension()
    manifest = _session_manifest(tmp_path)
    monkeypatch.setenv("CYRANO_MODE", "governed")
    monkeypatch.setenv("CYRANO_EXTENSION_SENTINEL", "enabled")
    monkeypatch.setenv("CYRANO_GOVERNED_SESSION", str(manifest))
    api, registry = _extension_api(tmp_path)
    await module.extension(api)
    registered = dict(
        (unit.name, kind) for kind, unit in registry.registrations()
    )
    assert (
        registered.get("cyrano_governed_obligations") == "middleware"
    )
    assert registered.get("cyrano_governed_status") == "tool"


async def test_extension_governed_no_manifest(
    tmp_path, monkeypatch
):
    """Governed mode without a declared manifest registers status."""
    module = _load_extension()
    monkeypatch.setenv("CYRANO_MODE", "governed")
    monkeypatch.setenv("CYRANO_EXTENSION_SENTINEL", "enabled")
    monkeypatch.delenv("CYRANO_GOVERNED_SESSION", raising=False)
    api, registry = _extension_api(tmp_path)
    await module.extension(api)
    kinds = {kind for kind, _u in registry.registrations()}
    assert "middleware" not in kinds
    assert "tool" in kinds


async def test_extension_governed_no_sentinel(
    tmp_path, monkeypatch
):
    """UH-OPS-03: a disabled sentinel aborts the governed launch."""
    module = _load_extension()
    manifest = _session_manifest(tmp_path)
    monkeypatch.setenv("CYRANO_MODE", "governed")
    monkeypatch.delenv("CYRANO_EXTENSION_SENTINEL", raising=False)
    monkeypatch.setenv("CYRANO_GOVERNED_SESSION", str(manifest))
    api, _registry = _extension_api(tmp_path)
    with pytest.raises(CyranoError) as err:
        await module.extension(api)
    assert err.value.code == "CAPABILITY_UNAVAILABLE"


async def test_extension_governed_bad_manifest(
    tmp_path, monkeypatch
):
    """A declared-but-invalid manifest stops governed launch."""
    module = _load_extension()
    bad = tmp_path / "session.json"
    bad.write_text(json.dumps({"unexpected": True}))
    monkeypatch.setenv("CYRANO_MODE", "governed")
    monkeypatch.setenv("CYRANO_EXTENSION_SENTINEL", "enabled")
    monkeypatch.setenv("CYRANO_GOVERNED_SESSION", str(bad))
    api, registry = _extension_api(tmp_path)
    with pytest.raises(CyranoError) as err:
        await module.extension(api)
    assert err.value.code == "INPUT_INVALID"
    assert not registry.registrations()


async def test_extension_advisory_registers_status_only(
    tmp_path, monkeypatch
):
    """Advisory mode registers a status tool and no mediation."""
    module = _load_extension()
    monkeypatch.setenv("CYRANO_MODE", "advisory_diagnostics")
    monkeypatch.delenv("CYRANO_EXTENSION_SENTINEL", raising=False)
    api, registry = _extension_api(tmp_path)
    await module.extension(api)
    kinds = {kind for kind, _u in registry.registrations()}
    assert "middleware" not in kinds
    assert "tool" in kinds


async def test_extension_missing_mode_refuses(
    tmp_path, monkeypatch
):
    """No declared mode refuses registration entirely."""
    module = _load_extension()
    monkeypatch.delenv("CYRANO_MODE", raising=False)
    api, _registry = _extension_api(tmp_path)
    with pytest.raises(RuntimeError):
        await module.extension(api)
