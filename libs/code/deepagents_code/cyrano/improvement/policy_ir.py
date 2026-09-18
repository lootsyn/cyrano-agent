"""Bounded Path A policy IR with static validation.

A candidate policy is a list of typed rules over whitelisted
observation features plus a default action. There are no loops, no
imports, and no calls — the IR cannot express unbounded search or
escape the feature surface, so compile-time rejection is complete:
unbounded loops, imports, unknown features, unbounded literals, and
unknown actions are refused before any candidate exists.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError

#: Node kinds that would escape the bounded IR.
_FORBIDDEN_NODES = frozenset({"loop", "while", "import", "call", "exec"})

#: Observable features a rule may read; anything else is unknown.
POLICY_FEATURES = frozenset(
    {
        "attempts_used",
        "budget_remaining",
        "error_kind",
        "test_outcome",
        "verification_state",
        "scope_match",
    }
)

#: Actions a rule may select.
POLICY_ACTIONS = frozenset(
    {"proceed", "retry", "narrow_scope", "escalate", "abort"}
)

_OPS = frozenset({"==", "!=", "<", "<=", ">", ">=", "in"})
MAX_RULES = 16
_MIN_LITERAL = -1_000_000
_MAX_LITERAL = 1_000_000


@dataclass(frozen=True, slots=True)
class PolicyRule:
    """One typed condition-action rule."""

    feature: str
    op: str
    value: object
    action: str


@dataclass(frozen=True, slots=True)
class PolicyIR:
    """A validated bounded policy; digest identifies it exactly."""

    policy_id: str
    rules: tuple[PolicyRule, ...]
    default_action: str

    @property
    def ir_digest(self) -> str:
        """Seal rules and default into a comparable identity."""
        return digest(
            [[r.feature, r.op, repr(r.value), r.action] for r in self.rules]
            + [self.default_action]
        )


def _rule(spec: object) -> PolicyRule:
    if not isinstance(spec, Mapping):
        raise CyranoError("IR_SHAPE", "rule must be a mapping")
    kind = spec.get("kind", "rule")
    if not isinstance(kind, str):
        raise CyranoError("IR_SHAPE", "node kind must be a string")
    if kind in _FORBIDDEN_NODES:
        code = "IMPORT_FORBIDDEN" if kind == "import" else "UNBOUNDED_LOOP"
        raise CyranoError(code, f"node kind {kind!r} is not bounded IR")
    if kind != "rule":
        raise CyranoError("OPERATION_NOT_ALLOWED", f"node {kind!r}")
    feature = spec.get("feature")
    if feature not in POLICY_FEATURES:
        raise CyranoError("UNKNOWN_FEATURE", str(feature))
    op = spec.get("op", "==")
    if op not in _OPS:
        raise CyranoError("OPERATION_NOT_ALLOWED", f"op {op!r}")
    value = spec.get("value")
    if isinstance(value, bool):
        raise CyranoError("IR_SHAPE", "value must not be bool")
    if isinstance(value, (int, float)):
        if not _MIN_LITERAL <= value <= _MAX_LITERAL:
            raise CyranoError(
                "BOUND_REQUIRED", "literal outside the value bound"
            )
    elif isinstance(value, (list, tuple)):
        if len(value) > MAX_RULES:
            raise CyranoError("BOUND_REQUIRED", "value list too large")
    elif not isinstance(value, str):
        raise CyranoError("IR_SHAPE", "value must be a bounded literal")
    action = spec.get("then")
    if action not in POLICY_ACTIONS:
        raise CyranoError("OPERATION_NOT_ALLOWED", f"action {action!r}")
    return PolicyRule(str(feature), str(op), value, str(action))


def validate_ir(spec: Mapping[str, object]) -> PolicyIR:
    """Compile a bounded policy; unbounded input is refused.

    Loops, imports, calls, unknown features, unknown actions, and
    literals outside the value bound all fail before a candidate can
    exist. A policy without a default action is incomplete.
    """
    raw_rules = spec.get("rules")
    if not isinstance(raw_rules, (list, tuple)) or not raw_rules:
        raise CyranoError("IR_SHAPE", "a policy needs at least one rule")
    if len(raw_rules) > MAX_RULES:
        raise CyranoError("BOUND_REQUIRED", "rule count exceeds the bound")
    rules = tuple(_rule(r) for r in raw_rules)
    default = spec.get("default")
    if default not in POLICY_ACTIONS:
        raise CyranoError("OPERATION_NOT_ALLOWED", f"default {default!r}")
    return PolicyIR(
        policy_id=str(spec.get("id", "policy")),
        rules=rules,
        default_action=str(default),
    )
