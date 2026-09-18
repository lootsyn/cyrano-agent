"""WP16 R5-RF05: skill evaluation, CAS apply, restart, consolidation."""

from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.improvement.candidates import (
    enqueue_review,
    propose_candidate,
)
from deepagents_code.cyrano.improvement.skill_evaluation import (
    SkillLane,
    SkillVersion,
    consolidate,
    resume_learning,
)
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

ROOT = Path(__file__).resolve().parents[2]
TARGET_DDL = (ROOT / "cyrano/contracts/sql/target-schema.sql").read_text()


@pytest.fixture()
def ctx(tmp_path):
    repo = ScopedRepository.create(tmp_path / "db.sqlite3", TARGET_DDL)
    scope = repo.register_scope("t1", "u1", "w1")
    repo.create_stream(scope, "run-1", "request")
    yield repo, scope
    repo.close()


def _lane() -> SkillLane:
    return SkillLane(
        SkillVersion("skill-1", 1, "sha256:v1", "active", "origin")
    )


def test_rf05_01_protected_candidate_leaves_active_bytes():
    lane = _lane()
    before = lane.active
    candidate = propose_candidate(
        base_revision=1,
        diff="d",
        scope="t1/u1/w1",
        author="a",
        grounds="g",
    )
    evaluation = lane.evaluate(
        candidate,
        paths=["policies/trust/x"],
        input_semantics_unchanged=True,
        policy_ir_validated=True,
        classifier="independent",
    )
    assert evaluation.route == "manual"
    assert evaluation.active_changed is False
    assert lane.active == before


def test_rf05_02_refinement_opens_new_candidate_revision():
    lane = _lane()
    candidate = lane.refine(
        {"diff": "d", "scope": "t1/u1/w1", "grounds": "g"},
        author="a",
    )
    assert candidate.base_revision == lane.active.revision
    assert lane.active.revision == 1
    assert lane.active.content_digest == "sha256:v1"


def test_rf05_03_second_apply_requires_rebase():
    lane = _lane()
    candidate = lane.refine(
        {"diff": "d", "scope": "t1/u1/w1", "grounds": "g"},
        author="a",
    )
    applied = lane.apply(candidate, approver="r", new_digest="sha256:v2")
    assert applied.revision == 2
    with pytest.raises(CyranoError, match="REBASE_REQUIRED"):
        _ = lane.apply(candidate, approver="r", new_digest="sha256:v3")
    assert lane.active.content_digest == "sha256:v2"


def test_rf05_04_restart_recovers_one_learning_job(ctx):
    repo, scope = ctx
    candidate = propose_candidate(
        base_revision=1,
        diff="d",
        scope="t1/u1/w1",
        author="a",
        grounds="g",
    )
    job_id = enqueue_review(repo, scope, "run-1", candidate)
    first = repo.claim_outbox(scope, "w1", 0, 10)
    assert first is not None and first.job_id == job_id
    # Worker restarts after the lease expires; the same job resumes.
    resumed = resume_learning(repo, scope, "w2", 200, 10)
    assert resumed == job_id
    assert resume_learning(repo, scope, "w3", 200, 10) is None


def test_rf05_05_consolidation_refuses_missing_exception():
    records = [{"id": "r1"}, {"id": "r2"}]
    with pytest.raises(CyranoError, match="CONSOLIDATION_INCOMPLETE"):
        _ = consolidate(records, required_exceptions={"r1", "r9"})
    merged = consolidate(records, required_exceptions={"r1"})
    assert merged.destroyed == ()
    assert merged.kept == ("r1", "r2")


def test_rf05_06_transition_change_routes_to_actual_not_replay():
    lane = _lane()
    candidate = propose_candidate(
        base_revision=1,
        diff="d",
        scope="t1/u1/w1",
        author="a",
        grounds="g",
    )
    evaluation = lane.evaluate(
        candidate,
        paths=["src/x.py"],
        input_semantics_unchanged=False,
        policy_ir_validated=True,
        classifier="independent",
    )
    assert evaluation.route == "B"
    assert evaluation.requires_live is True
