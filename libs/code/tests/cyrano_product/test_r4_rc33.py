"""WP16 R4-RC33: analysis yields hypotheses+plan, never executes."""

from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.improvement.analysis import (
    EpisodeRecord,
    analyze_patterns,
)
from deepagents_code.cyrano.improvement.candidates import (
    enqueue_review,
    propose_candidate,
    run_review,
)
from deepagents_code.cyrano.improvement.impact import assess_impact
from deepagents_code.cyrano.improvement.workplan import (
    compile_learning_plan,
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


def test_rc33_01_analysis_yields_hypotheses_and_plan_digest():
    report = analyze_patterns(
        [EpisodeRecord("e1", "failed", kind="test")],
        learning_enabled=True,
    )
    assert report.hypotheses
    assert report.eval_plan_digest
    assert report.cost_digest
    assert report.active_changed is False


def test_rc33_02_gate_skipping_lesson_never_auto_adopted():
    report = analyze_patterns(
        [
            EpisodeRecord(
                "e1",
                "failed",
                kind="test",
                lesson="skip_verification",
            )
        ],
        learning_enabled=True,
    )
    assert report.blocked_lessons
    spec = {
        "steps": [
            {
                "id": "s",
                "op": "observe",
                "deps": [],
                "flags": ["skip_verification"],
            }
        ],
        "budget": 10,
        "deadline": 100,
    }
    with pytest.raises(CyranoError, match="GEN01_VIOLATION"):
        compile_learning_plan(spec, author="a", learning_enabled=True)


def test_rc33_03_classification_independent_of_author_claim():
    # Author claims scheduling-only on a transition-changing candidate.
    candidate = propose_candidate(
        base_revision=1,
        diff="d",
        scope="t1/u1/w1",
        author="a",
        grounds="g",
        paths=("src/x.py",),
        claims={"route": "A"},
    )
    route = assess_impact(
        candidate,
        classifier="c",
        input_semantics_unchanged=False,
        policy_ir_validated=True,
    )
    assert route.route == "B"


def test_rc33_04_learning_work_and_result_are_separate(ctx):
    repo, scope = ctx
    candidate = propose_candidate(
        base_revision=1,
        diff="d",
        scope="t1/u1/w1",
        author="a",
        grounds="g",
    )
    job_id = enqueue_review(repo, scope, "run-1", candidate)
    outcome = run_review(
        repo, scope, job_id, candidate, reviewer="r", budget=5
    )
    assert outcome.dead_lettered is False
    # Learning review completes without mutating the work stream's
    # business result: the candidate stays bound to its base revision.
    assert candidate.base_revision == 1
    assert repo.job_state(job_id) == "completed"
