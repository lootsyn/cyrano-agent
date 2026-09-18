"""Path A candidate generation and replay screening.

Candidates are built from the bounded IR, not chosen from a profile
menu — any combination of whitelisted features that compiles is a
genuinely new policy. Screening compares candidates on fixed
observations only: data recorded after the declared cutoff is
excluded from the policy process, never silently folded in.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.improvement.policy_ir import (
    PolicyIR,
    PolicyRule,
    validate_ir,
)


@dataclass(frozen=True, slots=True)
class PolicyCandidate:
    """A proposed policy; ``novel`` means not on the profile menu."""

    candidate_id: str
    ir: PolicyIR
    author: str
    novel: bool


def _match(rule: PolicyRule, observation: Mapping[str, object]) -> bool:
    value = observation.get(rule.feature)
    if rule.op == "in":
        options = rule.value
        if not isinstance(options, (list, tuple)):
            return False
        return value in options
    if rule.op == "==":
        return bool(value == rule.value)
    if rule.op == "!=":
        return bool(value != rule.value)
    if not isinstance(value, (int, float, str)) or not isinstance(
        rule.value, (int, float, str)
    ):
        return False
    try:
        left = float(value)
        right = float(rule.value)
    except (TypeError, ValueError):
        return False
    return {
        "<": left < right,
        "<=": left <= right,
        ">": left > right,
        ">=": left >= right,
    }[rule.op]


def decide(policy: PolicyIR, observation: Mapping[str, object]) -> str:
    """Pick an action for one observation; first matching rule wins."""
    for rule in policy.rules:
        if _match(rule, observation):
            return rule.action
    return policy.default_action


def generate_policy_candidate(
    spec: Mapping[str, object],
    *,
    author: str,
    profile_menu: Iterable[Mapping[str, object]] = (),
) -> PolicyCandidate:
    """Compile a candidate from a feature combination, not a menu.

    The search space is bounded IR — a combination satisfying static
    validation is expressible even when no existing profile matches
    it. ``novel`` reports whether the result differs from every menu
    profile; duplication is reported, not hidden.
    """
    if not isinstance(author, str) or not author:
        raise CyranoError("PLAN_SHAPE", "author required")
    ir = validate_ir(spec)
    menu_digests = {
        validate_ir(profile).ir_digest
        for profile in profile_menu
        if isinstance(profile, Mapping)
    }
    return PolicyCandidate(
        candidate_id=digest([ir.policy_id, ir.ir_digest, author]),
        ir=ir,
        author=author,
        novel=ir.ir_digest not in menu_digests,
    )


@dataclass(frozen=True, slots=True)
class ScreenResult:
    """Replay screening over fixed observations only."""

    support: int
    excluded_future: int
    score: float | None
    sufficient: bool


def screen_replay(
    candidate: PolicyCandidate,
    observations: Iterable[Mapping[str, object]],
    *,
    cutoff_seq: int,
    min_support: int = 1,
    reward_actions: Iterable[str] = ("proceed",),
) -> ScreenResult:
    """Screen a candidate on observations at or before the cutoff.

    Anything recorded after ``cutoff_seq`` is excluded and counted —
    future data never enters the policy process. A zero-support screen
    is ``sufficient=False`` with ``score=None``, not a zero.
    """
    if not isinstance(cutoff_seq, int) or cutoff_seq < 0:
        raise CyranoError("INPUT_INVALID", "cutoff must be nonnegative")
    rewards = frozenset(str(a) for a in reward_actions)
    support = 0
    excluded = 0
    hits = 0
    for obs in observations:
        seq = obs.get("seq", 0)
        if not isinstance(seq, int):
            raise CyranoError("INPUT_INVALID", "observation seq required")
        if seq > cutoff_seq:
            excluded += 1
            continue
        support += 1
        if decide(candidate.ir, obs) in rewards:
            hits += 1
    return ScreenResult(
        support=support,
        excluded_future=excluded,
        score=hits / support if support else None,
        sufficient=support >= min_support,
    )


def screen_report(candidate: PolicyCandidate) -> Mapping[str, object]:
    """Stable identity record for downstream evidence bundles."""
    return {
        "candidate_id": candidate.candidate_id,
        "ir_digest": candidate.ir.ir_digest,
        "novel": candidate.novel,
        "author": candidate.author,
    }
