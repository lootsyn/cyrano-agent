"""Interview scenario evaluation under wording changes.

A historical answer is bound to the question text it answered. When
the question wording changes, replaying the stored answer is a
simulation — it is labelled as such and never presented as an actual
answer, because a different prompt is a different measurement.
"""

from __future__ import annotations

from collections.abc import Mapping

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError


def _question_digest(question: str) -> str:
    return digest([question])


def evaluate_interview_scenario(
    scenario: Mapping[str, object],
    *,
    current_questions: Mapping[str, str],
    stored_answers: Mapping[str, Mapping[str, object]],
) -> Mapping[str, object]:
    """Score an interview scenario against its question digests.

    Each stored answer carries the digest of the question it answered.
    A wording change means the answer is a simulation of the current
    question — reported honestly and never counted as an actual
    answer.
    """
    answers: list[Mapping[str, object]] = []
    simulated = 0
    actual = 0
    for qid, text in sorted(current_questions.items()):
        stored = stored_answers.get(qid)
        if stored is None:
            continue
        bound = stored.get("question_digest")
        if bound == _question_digest(text):
            actual += 1
            answers.append({**dict(stored), "status": "actual"})
        else:
            simulated += 1
            answers.append({**dict(stored), "status": "simulation"})
    return {
        "scenario": str(scenario.get("id", "")),
        "actual_answers": actual,
        "simulated_answers": simulated,
        "answers": tuple(answers),
        "all_actual": simulated == 0,
    }


def bind_answer(question: str, answer: str) -> Mapping[str, object]:
    """Seal an answer to the exact question text it answered."""
    if not question or not answer:
        raise CyranoError("INPUT_INVALID", "question and answer are required")
    return {
        "question_digest": _question_digest(question),
        "answer": answer,
    }
