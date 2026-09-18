"""Context and recipe candidate evaluation.

A context change that raises cache hit rates while dropping required
obligations from the summary is a correctness failure, not an
efficiency gain. A recipe change that weakens verification — for
example replacing a real check with ``echo success`` — is eval
tamper and refused outright. Evaluation bindings are recomputed when
the candidate body changes, and cached conditions are recorded as a
separate experimental condition, never merged with live evidence.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

SEQ = (list, tuple, set, frozenset)


def _as_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value)


#: Verification commands that produce output without checking.
_WEAK_COMMANDS = frozenset({"echo", "true", "exit 0", "true;"})


@dataclass(frozen=True, slots=True)
class ContextVerdict:
    """Quality/usage verdict; usage gains never offset correctness."""

    verdict: str  # improved | regressed | inconclusive
    promotable: bool
    reason: str


def evaluate_context_candidate(
    baseline: Mapping[str, object],
    candidate: Mapping[str, object],
    *,
    required_obligations: Iterable[str],
) -> ContextVerdict:
    """Evaluate a context candidate on correctness before usage.

    Every required obligation present in the baseline summary must
    still be present in the candidate summary. Cache/token gains with
    dropped obligations are a correctness/intent failure, not an
    improvement.
    """
    obligations = {str(o) for o in required_obligations}
    cand_summary_raw = candidate.get("summary_obligations", ())
    cand_summary = (
        {str(o) for o in cand_summary_raw}
        if isinstance(cand_summary_raw, SEQ)
        else set()
    )
    dropped = obligations - cand_summary
    if dropped:
        return ContextVerdict(
            "regressed",
            False,
            f"required obligations dropped: {sorted(dropped)[0]}",
        )
    base_reads = _as_int(baseline.get("cache_reads", 0))
    cand_reads = _as_int(candidate.get("cache_reads", 0))
    base_tokens = _as_int(baseline.get("tokens", 0))
    cand_tokens = _as_int(candidate.get("tokens", 0))
    if cand_reads <= base_reads and cand_tokens >= base_tokens:
        return ContextVerdict(
            "inconclusive",
            False,
            "no usage improvement and correctness unchanged",
        )
    return ContextVerdict(
        "improved", True, "obligations preserved with usage gain"
    )


def detect_eval_tamper(
    recipe: Mapping[str, object],
    *,
    baseline_commands: Iterable[str],
) -> Mapping[str, object]:
    """Detect verification-weakening changes in a recipe.

    Replacing a real verification command with a trivially passing
    one, or removing a mandatory check, is ``tamper`` — refused, not
    evaluated.
    """
    commands_raw = recipe.get("verification_commands", ())
    commands = (
        tuple(str(c) for c in commands_raw)
        if isinstance(commands_raw, SEQ)
        else ()
    )
    baseline = {str(c) for c in baseline_commands}
    weak = [
        c
        for c in commands
        if c.strip().lower().split()
        and c.strip().lower().split()[0] in _WEAK_COMMANDS
    ]
    removed = baseline - set(commands)
    if weak or removed:
        return {
            "tamper": True,
            "weak_commands": tuple(weak),
            "removed_commands": tuple(sorted(removed)),
            "verdict": "rejected",
        }
    return {"tamper": False, "verdict": "clean"}


def rebind_evaluation(
    candidate_digest: str,
    evaluation: Mapping[str, object],
) -> Mapping[str, object]:
    """Rebind evidence to the candidate it actually measured.

    An evaluation bound to a different body digest is stale for this
    candidate — the change impact and the evaluation binding differ,
    so re-evaluation is required instead of reuse.
    """
    bound = evaluation.get("candidate_digest")
    if bound != candidate_digest:
        return {
            "valid": False,
            "code": "STALE_EVIDENCE",
            "requires_reevaluation": True,
        }
    cached = bool(evaluation.get("cached_conditions", False))
    return {
        "valid": True,
        "code": "bound",
        "cached_conditions_recorded": cached,
        "condition_class": "cached" if cached else "live",
    }
