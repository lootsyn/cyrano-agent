"""WP10 scenarios: real runner evidence, delivery, and reconcile."""

from hashlib import sha256
from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.kernel import patches as kernel_patches
from deepagents_code.cyrano.kernel.patches import (
    ApplyGrant,
    FilePatch,
    apply_to_target,
    deliver_result,
    rollback_source,
)
from deepagents_code.cyrano.sqlite.repository import ScopedRepository
from deepagents_code.cyrano.workflow.execution import (
    AttemptRunner,
    WorkOutcome,
)
from deepagents_code.cyrano.workflow.verification import (
    assess_run,
    report_from_run,
    run_test_recipe,
)

ROOT = Path(__file__).resolve().parents[2]
TARGET_DDL = (ROOT / "cyrano/contracts/sql/target-schema.sql").read_text()


@pytest.fixture()
def ctx(tmp_path):
    repo = ScopedRepository.create(tmp_path / "db.sqlite3", TARGET_DDL)
    scope = repo.register_scope("t1", "u1", "w1")
    repo.create_stream(scope, "s1", "request")
    yield repo, scope, AttemptRunner(repo, scope)
    repo.close()


def _digest(data: bytes) -> str:
    return "sha256:" + sha256(data).hexdigest()


# -- WP10-I01: real pytest runs separated by outcome ----------------


def test_wp10_i01_red_suite_is_failed(tmp_path):
    suite = tmp_path / "red"
    suite.mkdir()
    (suite / "test_x.py").write_text("def test_x():\n    assert False\n")
    run = run_test_recipe(suite, junit_path=tmp_path / "red.xml")
    report = report_from_run(run, artifact_digest="sha256:red", mandatory=())
    assert run.exit_code != 0
    assert report.verdict == "failed"


def test_wp10_i01_empty_collection_is_not_run(tmp_path):
    suite = tmp_path / "empty"
    suite.mkdir()
    (suite / "test_none.py").write_text("X = 1\n")
    run = run_test_recipe(suite, junit_path=tmp_path / "empty.xml")
    report = report_from_run(run, artifact_digest="sha256:empty", mandatory=())
    assert run.exit_code == 5
    assert report.verdict == "not_run"


def test_wp10_i01_all_skipped_mandatory_is_blocked(tmp_path):
    suite = tmp_path / "skip"
    suite.mkdir()
    (suite / "test_s.py").write_text(
        "import pytest\n\n"
        "@pytest.mark.skip(reason='env')\n"
        "def test_s():\n    assert True\n"
    )
    run = run_test_recipe(suite, junit_path=tmp_path / "skip.xml")
    assert run.results and all(r.status == "skipped" for r in run.results)
    report = report_from_run(
        run,
        artifact_digest="sha256:skip",
        mandatory=tuple(r.check_id for r in run.results),
    )
    assert report.verdict == "not_run"


def test_wp10_i01_runner_error_is_not_test_failure(tmp_path):
    suite = tmp_path / "broken"
    suite.mkdir()
    (suite / "test_bad.py").write_text("def test_bad(:\n")
    run = run_test_recipe(suite, junit_path=tmp_path / "broken.xml")
    report = report_from_run(
        run, artifact_digest="sha256:broken", mandatory=()
    )
    assert run.exit_code >= 2
    assert report.verdict == "unverifiable"
    assert "RUNNER_ERROR" in report.findings


def test_wp10_i01_verification_binds_postimage(tmp_path):
    suite = tmp_path / "green"
    suite.mkdir()
    (suite / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    run = run_test_recipe(suite, junit_path=tmp_path / "green.xml")
    report = report_from_run(
        run,
        artifact_digest="sha256:postimage",
        mandatory=tuple(r.check_id for r in run.results),
    )
    assert report.verdict == "verified"
    assert Path(run.raw_ref).exists()
    assessment = assess_run(
        request_kind="change",
        delivery_mode="apply_to_source",
        verification=report,
        reviewed_digest="sha256:postimage",
        current_digest="sha256:postimage",
        source_changed=True,
    )
    assert assessment.status == "complete"
    assert assessment.may_apply is True


# -- WP10-I02: patch_only vs apply_to_source ------------------------


def test_wp10_i02_patch_only_then_approved_apply(tmp_path):
    root = tmp_path / "src"
    root.mkdir()
    (root / "f.py").write_bytes(b"v1")
    # patch_only: the candidate is delivered, source untouched.
    delivery = deliver_result(
        "patch_only", patch_ref="artifact:p", journal=None
    )
    assert delivery.source_changed is False
    assert (root / "f.py").read_bytes() == b"v1"
    # apply_to_source needs the separate grant, then applies for real.
    journal = apply_to_target(
        root=root,
        patches=[FilePatch("f.py", _digest(b"v1"), b"v2")],
        grant=ApplyGrant("source_apply", "subj", ("f.py",)),
        journal_dir=tmp_path / "journal",
    )
    assert journal.status == "applied"
    final = deliver_result("apply_to_source", patch_ref=None, journal=journal)
    assert final.source_changed is True
    assert (root / "f.py").read_bytes() == b"v2"


def test_wp10_i02_unapproved_mutation_refused(tmp_path):
    root = tmp_path / "src"
    root.mkdir()
    target = root / "f.py"
    target.write_bytes(b"v1")
    before = target.read_bytes()
    with pytest.raises(CyranoError):
        apply_to_target(
            root=root,
            patches=[FilePatch("f.py", _digest(b"v1"), b"v2")],
            grant=None,
            journal_dir=tmp_path / "journal",
        )
    assert target.read_bytes() == before


# -- WP10-I03: partial / external modify / cancel reconcile --------


def test_wp10_i03_partial_then_reconcile_no_blind_rollback(
    tmp_path, monkeypatch, ctx
):
    root = tmp_path / "src"
    root.mkdir()
    (root / "a.py").write_bytes(b"a1")
    (root / "b.py").write_bytes(b"b1")

    def fail_b(target: Path, data: bytes) -> None:
        if target.name == "b.py":
            raise OSError("io failure mid-apply")
        target.write_bytes(data)

    monkeypatch.setattr(kernel_patches, "_write_file", fail_b)
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
    # External/user edit on the applied file blocks blind undo.
    (root / "a.py").write_bytes(b"a2-user")
    report = rollback_source(root=root, journal=journal)
    assert report.status == "reconciling"
    assert (root / "a.py").read_bytes() == b"a2-user"
    # Cancel keeps unknown outcomes; no blind rerun.
    _, _, runner = ctx
    rev_repo, scope = ctx[0], ctx[1]
    rev = rev_repo.read_scoped_entity(scope, "s1")
    job = rev_repo.execute_command(
        scope,
        "runner",
        "run_work",
        "attempt-p",
        {"task_id": "tp"},
        "s1",
        expected_revision=rev,
        enqueue=True,
    ).event_id
    assert rev_repo.claim_job(scope, job, "w", 0, 300) is not None
    cancel = runner.cancel_run("s1", generation=1)
    assert job in cancel.unknown
    with pytest.raises(CyranoError) as exc:
        runner.run_work(
            "s1",
            "tp",
            worker=lambda tid: WorkOutcome("completed"),
            now=5,
        )
    assert exc.value.code == "RUN_CANCELLED"
