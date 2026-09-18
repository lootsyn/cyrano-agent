"""WP10 runner/settle/apply: durable attempts, patches, reconcile."""

from hashlib import sha256
from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.kernel import patches as kernel_patches
from deepagents_code.cyrano.kernel.patches import (
    ApplyGrant,
    ExpectedChain,
    FilePatch,
    apply_to_target,
    authorize_publish,
    deliver_result,
    rollback_source,
)
from deepagents_code.cyrano.sqlite.repository import ScopedRepository
from deepagents_code.cyrano.workflow.execution import (
    AttemptRunner,
    WorkOutcome,
)
from deepagents_code.cyrano.workflow.verification import (
    CheckResult,
    require_fresh_verification,
    verify_artifact,
)

ROOT = Path(__file__).resolve().parents[2]
TARGET_DDL = (ROOT / "cyrano/contracts/sql/target-schema.sql").read_text()


@pytest.fixture()
def ctx(tmp_path):
    repo = ScopedRepository.create(tmp_path / "db.sqlite3", TARGET_DDL)
    scope = repo.register_scope("t1", "u1", "w1")
    repo.create_stream(scope, "s1", "request")
    runner = AttemptRunner(repo, scope)
    yield repo, scope, runner
    repo.close()


def _digest(data: bytes) -> str:
    return "sha256:" + sha256(data).hexdigest()


def _verified(digest_str: str = "sha256:post"):
    return verify_artifact(
        artifact_digest=digest_str,
        results=(CheckResult("c1", "passed", "ev"),),
        mandatory=("c1",),
        raw_evidence_ref="junit.xml",
    )


def test_work_merge_merged_digest_needs_revalidation():
    report = _verified("sha256:branch-b")
    with pytest.raises(CyranoError) as exc:
        require_fresh_verification(
            report,
            "sha256:merged",
            code="MERGE_REVALIDATION_REQUIRED",
        )
    assert exc.value.code == "MERGE_REVALIDATION_REQUIRED"


def test_work_unknown_preserved_no_blind_retry(ctx):
    repo, scope, runner = ctx

    def timeout_worker(task_id: str) -> WorkOutcome:
        raise TimeoutError("peer did not answer")

    receipt = runner.run_work("s1", "t-task", worker=timeout_worker, now=100)
    assert receipt.outcome == "unknown"
    assert repo.job_state(receipt.job_id) == "unknown"
    with pytest.raises(CyranoError) as exc:
        runner.run_work("s1", "t-task", worker=timeout_worker, now=200)
    assert exc.value.code == "UNKNOWN_OUTCOME"
    assert runner.reconcile_attempt(receipt.job_id, "requeue") == "requeue"


def test_work_source_copy_change_is_not_source_change(tmp_path):
    delivery = deliver_result(
        "patch_only", patch_ref="artifact:p1", journal=None
    )
    assert delivery.source_changed is False
    assert delivery.applied_paths == ()


def test_work_test_oracle_removal_is_tamper():
    # The approved oracle says c2 must run; the candidate's run
    # dropped it — a tamper finding, not a missing pass.
    report = verify_artifact(
        artifact_digest="sha256:cand",
        results=(CheckResult("c1", "passed", "ev"),),
        mandatory=("c1", "c2"),
        raw_evidence_ref="junit.xml",
        expected_oracle={"c1": "ev", "c2": "ev2"},
    )
    assert report.verdict == "tampered"
    assert any("TEST_TAMPERED" in f for f in report.findings)


def test_uh_plan_09_approved_apply_advances_expected_chain(tmp_path):
    root = tmp_path / "src"
    root.mkdir()
    (root / "a.py").write_bytes(b"old-a")
    grant = ApplyGrant("source_apply", "subj", ("a.py",))
    journal = apply_to_target(
        root=root,
        patches=[
            FilePatch("a.py", _digest(b"old-a"), b"new-a"),
        ],
        grant=grant,
        journal_dir=tmp_path / "journal",
    )
    chain = ExpectedChain({"a.py": _digest(b"old-a")})
    chain.advance(journal, grant)
    assert chain.check("a.py", _digest(b"new-a"))
    # The dependent unit's patch now validates against the new
    # preimage without re-approving the whole spec.
    followup = apply_to_target(
        root=root,
        patches=[
            FilePatch("a.py", _digest(b"new-a"), b"newer-a"),
        ],
        grant=ApplyGrant("source_apply", "subj-b", ("a.py",)),
        journal_dir=tmp_path / "journal",
    )
    assert followup.status == "applied"


def test_uh_plan_09_out_of_grant_advance_refused(tmp_path):
    root = tmp_path / "src"
    root.mkdir()
    (root / "a.py").write_bytes(b"old-a")
    journal = apply_to_target(
        root=root,
        patches=[FilePatch("a.py", _digest(b"old-a"), b"new-a")],
        grant=ApplyGrant("source_apply", "subj"),
        journal_dir=tmp_path / "journal",
    )
    chain = ExpectedChain({"a.py": _digest(b"old-a")})
    narrow = ApplyGrant("source_apply", "subj", ("other.py",))
    with pytest.raises(CyranoError) as exc:
        chain.advance(journal, narrow)
    assert exc.value.code == "ACL_DENIED"
    assert chain.check("a.py", _digest(b"old-a"))


def test_uh_ops_07_preimage_conflict_blocks_overwrite(tmp_path):
    root = tmp_path / "src"
    root.mkdir()
    target = root / "f.py"
    target.write_bytes(b"approved-preimage")
    grant = ApplyGrant("source_apply", "subj", ("f.py",))
    target.write_bytes(b"external-edit")
    with pytest.raises(CyranoError) as exc:
        apply_to_target(
            root=root,
            patches=[FilePatch("f.py", _digest(b"approved-preimage"), b"x")],
            grant=grant,
            journal_dir=tmp_path / "journal",
        )
    assert exc.value.code == "PREIMAGE_CONFLICT"
    assert target.read_bytes() == b"external-edit"


def test_uh_ops_08_partial_apply_journals_recovery(tmp_path, monkeypatch):
    root = tmp_path / "src"
    root.mkdir()
    (root / "a.py").write_bytes(b"a1")
    (root / "b.py").write_bytes(b"b1")

    def fail_second(target: Path, data: bytes) -> None:
        if target.name == "b.py":
            raise OSError("simulated rename failure")
        target.write_bytes(data)

    monkeypatch.setattr(kernel_patches, "_write_file", fail_second)
    journal = apply_to_target(
        root=root,
        patches=[
            FilePatch("a.py", _digest(b"a1"), b"a2"),
            FilePatch("b.py", _digest(b"b1"), b"b2"),
        ],
        grant=ApplyGrant("source_apply", "subj", ("a.py", "b.py")),
        journal_dir=tmp_path / "journal",
    )
    assert journal.status == "partial"
    assert (root / "a.py").read_bytes() == b"a2"
    assert (root / "b.py").read_bytes() == b"b1"
    body = Path(journal.path).read_text()
    assert '"partial"' in body and "preimage_b64" in body
    with pytest.raises(CyranoError) as exc:
        deliver_result("apply_to_source", patch_ref=None, journal=journal)
    assert exc.value.code == "APPLY_INCOMPLETE"


def test_uh_run_04_started_then_restart_reconciles_unknown(ctx):
    repo, scope, runner = ctx
    revision = repo.read_scoped_entity(scope, "s1")
    receipt = repo.execute_command(
        scope,
        "runner",
        "run_work",
        "attempt-x",
        {"task_id": "t1"},
        "s1",
        expected_revision=revision,
        enqueue=True,
    )
    lease = repo.claim_job(scope, receipt.event_id, "w1", 0, 300)
    assert lease is not None
    unknown = runner.recover_inflight("s1")
    assert receipt.event_id in unknown
    assert repo.job_state(receipt.event_id) == "unknown"


def test_uh_run_08_cancel_blocks_dispatch_reports_partial(ctx):
    repo, scope, runner = ctx
    done = runner.run_work(
        "s1",
        "t-done",
        worker=lambda tid: WorkOutcome(
            "completed", result_ref="r1", usage_units=3
        ),
        now=10,
    )
    assert done.outcome == "completed"
    rev = repo.read_scoped_entity(scope, "s1")
    leased_job = repo.execute_command(
        scope,
        "runner",
        "run_work",
        "attempt-long",
        {"task_id": "t-long"},
        "s1",
        expected_revision=rev,
        enqueue=True,
    ).event_id
    assert repo.claim_job(scope, leased_job, "w1", 20, 300) is not None
    rev = repo.read_scoped_entity(scope, "s1")
    pending_job = repo.execute_command(
        scope,
        "runner",
        "run_work",
        "attempt-wait",
        {"task_id": "t-wait"},
        "s1",
        expected_revision=rev,
        enqueue=True,
    ).event_id
    report = runner.cancel_run("s1", generation=2)
    assert report.state == "reconciling"
    assert pending_job in report.cancelled
    assert leased_job in report.unknown
    assert done.job_id in report.partial_results
    with pytest.raises(CyranoError) as exc:
        runner.run_work(
            "s1",
            "t-new",
            worker=lambda tid: WorkOutcome("completed"),
            now=30,
        )
    assert exc.value.code == "RUN_CANCELLED"


def test_integ_partial_undo_preserves_user_edit(tmp_path):
    root = tmp_path / "src"
    root.mkdir()
    (root / "a.py").write_bytes(b"a1")
    (root / "b.py").write_bytes(b"b1")
    journal = apply_to_target(
        root=root,
        patches=[
            FilePatch("a.py", _digest(b"a1"), b"a2"),
            FilePatch("b.py", _digest(b"b1"), b"b2"),
        ],
        grant=ApplyGrant("source_apply", "subj", ("a.py", "b.py")),
        journal_dir=tmp_path / "journal",
    )
    assert journal.status == "applied"
    # User edited a.py after the apply crashed mid-work.
    (root / "a.py").write_bytes(b"a2-user-edit")
    report = rollback_source(root=root, journal=journal)
    assert report.status == "reconciling"
    assert report.needs_human_decision is True
    assert "a.py" in report.conflict_preserved
    assert "b.py" in report.restored
    assert (root / "a.py").read_bytes() == b"a2-user-edit"
    assert (root / "b.py").read_bytes() == b"b1"


def test_integ_cancel_unknown_report_keeps_unknown(ctx):
    repo, scope, runner = ctx
    rev = repo.read_scoped_entity(scope, "s1")
    job = repo.execute_command(
        scope,
        "runner",
        "run_work",
        "attempt-remote",
        {"task_id": "t-remote"},
        "s1",
        expected_revision=rev,
        enqueue=True,
    ).event_id
    assert repo.claim_job(scope, job, "w1", 0, 300) is not None
    report = runner.cancel_run("s1", generation=1)
    assert report.state == "reconciling"
    assert job in report.unknown
    assert runner.run_state("s1") == "reconciling"
    with pytest.raises(CyranoError) as exc:
        runner.mark_reconciled("s1")
    assert exc.value.code == "UNKNOWN_OUTCOME"
    runner.reconcile_attempt(job, "discard")
    runner.mark_reconciled("s1")
    assert runner.run_state("s1") == "reconciled"


def test_apply_requires_source_apply_purpose(tmp_path):
    root = tmp_path / "src"
    root.mkdir()
    (root / "a.py").write_bytes(b"a1")
    with pytest.raises(CyranoError) as exc:
        apply_to_target(
            root=root,
            patches=[FilePatch("a.py", _digest(b"a1"), b"a2")],
            grant=None,
            journal_dir=tmp_path / "j",
        )
    assert exc.value.code == "APPROVAL_REQUIRED"
    with pytest.raises(CyranoError) as exc:
        apply_to_target(
            root=root,
            patches=[FilePatch("a.py", _digest(b"a1"), b"a2")],
            grant=ApplyGrant("plan_approval", "subj", ("a.py",)),
            journal_dir=tmp_path / "j",
        )
    assert exc.value.code == "PURPOSE_MISMATCH"
    with pytest.raises(CyranoError) as exc:
        authorize_publish(ApplyGrant("acceptance", "subj"))
    assert exc.value.code == "PURPOSE_MISMATCH"
