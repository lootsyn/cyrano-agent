"""WP23 study-2 candidate-arm integrity gate tests.

The first live study failed because the harness inferred candidate
readiness from a misparsed process-completion marker, so the
B1/B2/B3 candidate arms ran with empty memory — an unrecorded
baseline-vs-baseline. These tests pin the hardened behavior: the
gate proves every provisioning invariant from real runtime state
(repository rows, on-disk artifacts, digests) and never trusts
process output. A run that cannot prove provisioning aborts before
its first model call.
"""

import importlib
import json
import sys
from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.memory.repository import MemoryRepository
from deepagents_code.cyrano.memory.service import MemoryService
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

CODE = Path(__file__).resolve().parents[2]
ROOT = CODE / "cyrano"
TARGET_DDL = (ROOT / "contracts" / "sql" / "target-schema.sql").read_text()

sys.path.insert(0, str(ROOT / "scripts"))
live = importlib.import_module("run_live_study")

SCOPE = "wp23-live-study-2"
MEMORY_ID = "widgetbox-convention-r2"
AGENT = "wp23r2"
NOTE = "# widgetbox module convention\n\nregister every widget module.\n"
CONTENT_DIGEST = (
    "sha256:" + __import__("hashlib").sha256(NOTE.encode()).hexdigest()
)

RECEIPT_FIELDS = {
    "subject": "sha256:subject-1",
    "nonce": "wp23-live-2",
    "actor": "study-operator",
    "client_event_id": "wp23-live-2-approve-1",
    "purpose": "improvement_approval",
}


def _approval(**kw) -> dict[str, object]:
    """A valid approval record; kwargs override individual fields."""
    record: dict[str, object] = {
        "candidate_id": RECEIPT_FIELDS["subject"],
        "memory_id": MEMORY_ID,
        "request_id": "req-1",
        "decision": "approved",
        "content_digest": CONTENT_DIGEST,
        "receipt_digest": digest(
            {
                "subject": RECEIPT_FIELDS["subject"],
                "nonce": RECEIPT_FIELDS["nonce"],
                "actor": RECEIPT_FIELDS["actor"],
                "client_event": RECEIPT_FIELDS["client_event_id"],
                "purpose": RECEIPT_FIELDS["purpose"],
            }
        ),
        "receipt_fields": dict(RECEIPT_FIELDS),
        "memory_activated": True,
    }
    record.update(kw)
    return record


@pytest.fixture
def memory_repo(tmp_path: Path):
    """Real scoped memory repo; tests opt into activation state."""
    repo = ScopedRepository.create(tmp_path / "db.sqlite3", TARGET_DDL)
    try:
        yield repo
    finally:
        repo.close()


def _memory(repo: ScopedRepository, activate: bool = True):
    """Propose the improvement on the fixture repo."""
    service = MemoryService(MemoryRepository(repo))
    rec = service.propose_memory(
        SCOPE,
        MEMORY_ID,
        kind="procedure",
        content=NOTE.encode(),
        source_digest="sha256:subject-1",
        evidence_refs=("task-a-candidate",),
        at=1000,
    )
    if activate:
        service.activate_memory(
            SCOPE, MEMORY_ID, expected_revision=rec.revision, at=1001
        )
    return MemoryRepository(repo)


def _profiles(tmp_path: Path, note: str | None = NOTE):
    """Candidate and baseline profile trees on disk."""
    cand = tmp_path / "cand"
    base = tmp_path / "base"
    (cand / "agents" / AGENT).mkdir(parents=True)
    (base / "agents" / AGENT).mkdir(parents=True)
    if note is not None:
        (cand / "agents" / AGENT / "AGENTS.md").write_text(note)
    return cand, base


def _context(tmp_path: Path, artifact_digest: str | None) -> Path:
    """The candidate context manifest as the runner writes it."""
    ctx = {
        "run_id": "task-b4-candidate",
        "study_id": "wp23-live-effectiveness-2",
        "memory_id": MEMORY_ID,
        "candidate_id": RECEIPT_FIELDS["subject"],
        "content_digest": CONTENT_DIGEST,
        "artifact": f"agents/{AGENT}/AGENTS.md",
        "artifact_digest": artifact_digest,
    }
    path = tmp_path / "context-manifest.json"
    path.write_text(json.dumps(ctx))
    return path


def _gate(
    tmp_path: Path,
    *,
    repo=None,
    approval=None,
    cand=None,
    base=None,
    ctx=None,
    arms=True,
) -> list[str]:
    return live._candidate_integrity_gate(
        repo=repo,
        scope=SCOPE,
        approval=approval,
        candidate_profile=cand or tmp_path / "cand",
        baseline_profile=base or tmp_path / "base",
        context_manifest=ctx or tmp_path / "context-manifest.json",
        agent=AGENT,
        arms_identical=arms,
    )


def test_gate_fully_provisioned_candidate_passes(tmp_path, memory_repo):
    """Happy path: active+approved+digest-bound artifact → clean."""
    cand, base = _profiles(tmp_path)
    ctx = _context(tmp_path, CONTENT_DIGEST)
    fails = _gate(
        tmp_path,
        repo=_memory(memory_repo),
        approval=_approval(),
        cand=cand,
        base=base,
        ctx=ctx,
    )
    assert fails == []


def test_gate_process_complete_but_approval_absent(tmp_path, memory_repo):
    """Study-1 defect class: artifact exists, approval never ran."""
    cand, base = _profiles(tmp_path)
    ctx = _context(tmp_path, CONTENT_DIGEST)
    fails = _gate(
        tmp_path,
        repo=_memory(memory_repo),
        approval={
            "decision": "no_improvement",
            "reason": "improvement run produced no note",
        },
        cand=cand,
        base=base,
        ctx=ctx,
    )
    assert "approval_absent" in fails
    assert "receipt_invalid" not in fails  # nothing to validate


def test_gate_approval_missing_entirely(tmp_path, memory_repo):
    cand, base = _profiles(tmp_path)
    ctx = _context(tmp_path, CONTENT_DIGEST)
    fails = _gate(
        tmp_path,
        repo=_memory(memory_repo),
        approval=None,
        cand=cand,
        base=base,
        ctx=ctx,
    )
    assert "approval_absent" in fails
    assert "proposal_missing" in fails


def test_gate_approved_but_improvement_not_activated(tmp_path, memory_repo):
    """Approval receipt valid, memory still a mere candidate."""
    cand, base = _profiles(tmp_path)
    ctx = _context(tmp_path, CONTENT_DIGEST)
    fails = _gate(
        tmp_path,
        repo=_memory(memory_repo, activate=False),
        approval=_approval(),
        cand=cand,
        base=base,
        ctx=ctx,
    )
    assert "improvement_not_active" in fails
    assert "proposal_missing" not in fails


def test_gate_active_but_artifact_not_provisioned(tmp_path, memory_repo):
    cand, base = _profiles(tmp_path, note=None)
    ctx = _context(tmp_path, None)
    fails = _gate(
        tmp_path,
        repo=_memory(memory_repo),
        approval=_approval(),
        cand=cand,
        base=base,
        ctx=ctx,
    )
    assert "artifact_not_provisioned" in fails


def test_gate_provisioned_artifact_digest_mismatch(tmp_path, memory_repo):
    cand, base = _profiles(tmp_path, note="# tampered note\n")
    ctx = _context(tmp_path, CONTENT_DIGEST)
    fails = _gate(
        tmp_path,
        repo=_memory(memory_repo),
        approval=_approval(),
        cand=cand,
        base=base,
        ctx=ctx,
    )
    assert "artifact_digest_mismatch" in fails


def test_gate_candidate_artifact_leaks_into_baseline(tmp_path, memory_repo):
    cand, base = _profiles(tmp_path)
    (base / "agents" / AGENT / "AGENTS.md").write_text(NOTE)
    ctx = _context(tmp_path, CONTENT_DIGEST)
    fails = _gate(
        tmp_path,
        repo=_memory(memory_repo),
        approval=_approval(),
        cand=cand,
        base=base,
        ctx=ctx,
    )
    assert "baseline_contaminated" in fails


def test_gate_receipt_tampered(tmp_path, memory_repo):
    cand, base = _profiles(tmp_path)
    ctx = _context(tmp_path, CONTENT_DIGEST)
    bad = _approval(receipt_fields={**RECEIPT_FIELDS, "actor": "forged-actor"})
    fails = _gate(
        tmp_path,
        repo=_memory(memory_repo),
        approval=bad,
        cand=cand,
        base=base,
        ctx=ctx,
    )
    assert "receipt_invalid" in fails


def test_gate_context_binding_missing(tmp_path, memory_repo):
    cand, base = _profiles(tmp_path)
    missing = tmp_path / "no-such-context.json"
    fails = _gate(
        tmp_path,
        repo=_memory(memory_repo),
        approval=_approval(),
        cand=cand,
        base=base,
        ctx=missing,
    )
    assert "context_binding_missing" in fails


def test_gate_arms_diverge(tmp_path, memory_repo):
    cand, base = _profiles(tmp_path)
    ctx = _context(tmp_path, CONTENT_DIGEST)
    fails = _gate(
        tmp_path,
        repo=_memory(memory_repo),
        approval=_approval(),
        cand=cand,
        base=base,
        ctx=ctx,
        arms=False,
    )
    assert "arms_diverge" in fails


def test_extract_note_from_real_stdout_shape():
    """Note survives noise; the completion marker is not required."""
    stdout = (
        "Running task non-interactively...\n"
        "App: v0.1.70 | Agent: wp23r2 | Model: x | Thread: t\n"
        "Starting LangGraph server...\n"
        "✓ Server ready\n"
        "🔧 Calling tool: ls\n"
        "🔧 Calling tool: read_file\n"
        "\n"
        "# widgetbox module convention\n"
        "\n"
        "register every widget module.\n"
        "\n"
        "Usage Stats\n"
        "Provider    Model    Reqs\n"
        "openrouter  x          4\n"
        "\n"
        "Agent active  24.1s\n"
    )
    note = live._extract_note(stdout)
    assert "widgetbox module convention" in note
    assert "register every widget module" in note
    assert "Usage Stats" not in note
    assert "Calling tool" not in note


def test_extract_note_without_completion_marker():
    """Study-1 defect class: marker missing but note present → kept.

    The old gate keyed on the completion flag; the hardened flow
    keys on the note artifact itself, so a run whose marker landed
    on the wrong stream still yields its improvement.
    """
    stdout = (
        "Running task non-interactively...\n"
        "🔧 Calling tool: read_file\n"
        "the convention note\n"
        "Usage Stats\n"
        "openrouter  x  1  1K  1K\n"
    )
    assert live._extract_note(stdout) == "the convention note"


def test_extract_note_empty_when_no_artifact():
    stdout = (
        "Running task non-interactively...\n"
        "🔧 Calling tool: ls\n"
        "✓ Task completed\n"
        "Usage Stats\n"
        "openrouter  x  1  1K  1K\n"
        "Agent active  5s\n"
    )
    assert live._extract_note(stdout) == ""


def test_usage_reads_uppercase_k_suffix():
    """Study-1 defect class: ``45.0K`` must not parse as zero."""
    stdout = (
        "openrouter  deepseek/deepseek-v4.1-flash     4     45.3K"
        "       1.2K     —\n"
    )
    usage = live._usage(stdout)
    assert usage["requests"] == 4
    assert usage["input_tokens"] == 45300
    assert usage["output_tokens"] == 1200
