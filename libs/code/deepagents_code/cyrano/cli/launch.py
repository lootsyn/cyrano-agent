"""Governed launch, release gating, and packaging checks.

Feature availability is staged per feature
(``off`` → ``observe_only`` → ``isolated_shadow`` → ``gated_canary`` →
``enabled``); an unconfigured feature is ``off``, never implicitly
enabled. Shadow execution must not duplicate real side effects.
Reader/writer compatibility is versioned explicitly: an old reader on
a newer record is ``VERSION_CONFLICT`` and an old writer on a newer
generation is ``MIGRATION_REQUIRED``. Scorecard points require real
evidence — documents and fixtures can never award product points, and
hard failures are never offset by totals.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from deepagents_code.cyrano.contracts.types import CyranoError

FEATURE_STAGES = (
    "off",
    "observe_only",
    "isolated_shadow",
    "gated_canary",
    "enabled",
)

REAL_EFFECTS = ("write", "push", "payment", "network", "dispatch")

PACKAGE_EXCLUSIONS = (
    "tools/.state",
    "node_modules",
    "__pycache__",
    ".venv",
    ".git",
    "evidence/holdout",
)

SECRET_MARKERS = (
    "api_key",
    "secret",
    "token",
    "holdout",
    ".env",
    "credential",
)

TEST_ENV_DENYLIST = (
    "PYTEST_ADDOPTS",
    "PYTEST_PLUGINS",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
    "PYTHONPATH",
)


@dataclass(frozen=True, slots=True)
class FeatureState:
    """One feature's staged availability; never merged into a blob."""

    feature_id: str
    stage: str
    configured: bool
    blocked_reasons: tuple[str, ...]


def resolve_feature_state(
    feature_id: str, config: Mapping[str, object] | None
) -> FeatureState:
    """Resolve a feature's stage; missing config is ``off``.

    A stage outside ``FEATURE_STAGES`` is rejected rather than
    coerced, and a feature that was never configured cannot be
    enabled by absence of data.
    """
    if config is None or feature_id not in config:
        return FeatureState(feature_id, "off", False, ("not_configured",))
    raw = config[feature_id]
    stage_raw = raw.get("stage") if isinstance(raw, Mapping) else raw
    stage = stage_raw if isinstance(stage_raw, str) else ""
    if stage not in FEATURE_STAGES:
        raise CyranoError(
            "FEATURE_STAGE_UNKNOWN",
            f"feature {feature_id} stage {stage_raw!r}",
        )
    reasons: tuple[str, ...] = ()
    if isinstance(raw, Mapping):
        blocked = raw.get("blocked_reasons")
        if isinstance(blocked, (list, tuple)):
            reasons = tuple(str(r) for r in blocked)
    return FeatureState(feature_id, stage, True, reasons)


def plan_shadow_execution(
    feature: FeatureState, effects: Sequence[str]
) -> Mapping[str, object]:
    """Plan an isolated-shadow run for a feature.

    Shadow runs must not produce real side effects twice. Any real
    effect (write/push/payment/network/dispatch) requires an
    isolated or no-effect binding; otherwise the plan is refused.
    """
    if feature.stage != "isolated_shadow":
        return {
            "feature_id": feature.feature_id,
            "allowed": False,
            "reason": "feature_not_in_isolated_shadow",
        }
    real = [e for e in effects if e in REAL_EFFECTS]
    if real:
        return {
            "feature_id": feature.feature_id,
            "allowed": False,
            "reason": "real_side_effects_require_isolation",
            "effects": tuple(real),
        }
    return {
        "feature_id": feature.feature_id,
        "allowed": True,
        "effects": (),
        "mode": "isolated_no_effect",
    }


def check_enable_combination(
    requested: Sequence[str],
    individually_verified: Sequence[str],
    interaction_verified: Sequence[tuple[str, str]],
) -> Mapping[str, object]:
    """Gate enabling multiple features at once.

    Two features verified only individually need an interaction
    evaluation before both may be enabled together — effect
    attribution is otherwise ambiguous.
    """
    enabled = set(requested)
    individual = set(individually_verified)
    pairs = {frozenset(p) for p in interaction_verified}
    missing = sorted(enabled - individual)
    unpaired = []
    req = sorted(enabled)
    for i, a in enumerate(req):
        for b in req[i + 1 :]:
            if frozenset((a, b)) not in pairs:
                unpaired.append((a, b))
    blocked = bool(missing or unpaired)
    return {
        "allowed": not blocked,
        "requires_interaction_eval": unpaired,
        "unverified": missing,
    }


def check_reader_compatibility(
    reader_version: int, record_version: int
) -> None:
    """Refuse an old reader on a newer durable record."""
    if reader_version < record_version:
        raise CyranoError(
            "VERSION_CONFLICT",
            f"reader v{reader_version} cannot read record v{record_version}",
        )


def check_writer_compatibility(
    writer_version: int, generation_version: int
) -> None:
    """Refuse an old writer on a newer generation."""
    if writer_version < generation_version:
        raise CyranoError(
            "MIGRATION_REQUIRED",
            f"writer v{writer_version} requires migration for "
            f"generation v{generation_version}",
        )


@dataclass(frozen=True, slots=True)
class MigrationResult:
    """Outcome of a staged migration; partial results never commit."""

    committed: bool
    converted: int
    failed_at: int | None
    original_preserved: bool


def staged_migration(
    records: Sequence[Mapping[str, object]],
    transform: Callable[[Mapping[str, object]], Mapping[str, object]],
) -> MigrationResult:
    """Convert every record or commit none.

    A failure mid-conversion preserves the original records and
    returns an uncommitted result — partial activation is never
    reported as success.
    """
    converted = []
    for index, record in enumerate(records):
        try:
            converted.append(transform(record))
        except Exception:
            return MigrationResult(
                committed=False,
                converted=0,
                failed_at=index,
                original_preserved=True,
            )
    return MigrationResult(
        committed=True,
        converted=len(converted),
        failed_at=None,
        original_preserved=True,
    )


def restore_with_deletions(
    backup_records: Sequence[Mapping[str, object]],
    tombstones: Sequence[Mapping[str, object]],
    writer_version: int,
    generation_version: int,
) -> Mapping[str, object]:
    """Restore a backup, replaying tombstones before activation.

    Deleted memories and revoked skills must not resurrect. Old
    writers are refused before any record is activated.
    """
    check_writer_compatibility(writer_version, generation_version)
    tombstoned = {str(t.get("target")) for t in tombstones}
    restored = [
        r for r in backup_records if str(r.get("id")) not in tombstoned
    ]
    return {
        "restored": len(restored),
        "tombstones_replayed": len(tombstoned),
        "activated": True,
    }


def plan_release_package(
    files: Sequence[str],
) -> Mapping[str, object]:
    """Plan release contents, excluding state dirs and caches.

    Runtime caches, state directories and dependency trees are
    excluded; only install-contract files ship.
    """
    included, excluded = [], []
    for name in files:
        path = PurePosixPath(name)
        parts = path.parts
        hit = any(
            name == ex or ex in parts or name.startswith(ex + "/")
            for ex in PACKAGE_EXCLUSIONS
        )
        (excluded if hit else included).append(name)
    return {"included": tuple(included), "excluded": tuple(excluded)}


def scan_package_contents(
    files: Sequence[str],
) -> Mapping[str, object]:
    """Refuse secrets, dev corpora and holdout data in a wheel."""
    rejected = []
    for name in files:
        lowered = name.lower()
        if any(marker in lowered for marker in SECRET_MARKERS):
            rejected.append(name)
    return {
        "accepted": not rejected,
        "rejected": tuple(rejected),
        "evidence": "wheel_content_scan",
    }


def verify_wheel_assets(
    required_assets: Sequence[str],
    wheel_files: Sequence[str],
) -> Mapping[str, object]:
    """Check every required runtime asset exists inside the wheel.

    Missing assets are named explicitly; a source-tree fallback is
    never offered as a substitute for packaged data.
    """
    present = set(wheel_files)
    missing = [a for a in required_assets if a not in present]
    return {
        "complete": not missing,
        "missing": tuple(missing),
        "source_fallback": False,
    }


def license_inventory(
    packages: Sequence[Mapping[str, object]],
) -> Mapping[str, object]:
    """Require a license record for every shipped package.

    Unconfirmed licenses defer inclusion — process separation alone
    does not absolve a missing notice.
    """
    deferred = []
    for pkg in packages:
        license_value = pkg.get("license")
        notice = pkg.get("notice")
        if not license_value or (pkg.get("requires_notice") and not notice):
            deferred.append(str(pkg.get("name", "unknown")))
    return {
        "complete": not deferred,
        "deferred": tuple(deferred),
        "decision": "blocked" if deferred else "review",
    }


def verify_install_nonmutation(
    before: Mapping[str, str], after: Mapping[str, str]
) -> None:
    """Require a byte-identical target manifest after bootstrap."""
    if dict(before) != dict(after):
        raise CyranoError(
            "INSTALL_MUTATION",
            "target manifest changed during harness bootstrap",
        )


def validate_runtime_support(platform: str, supported: Sequence[str]) -> None:
    """Refuse unsupported platforms without shrinking guarantees."""
    if platform not in supported:
        raise CyranoError(
            "CAPABILITY_UNSUPPORTED",
            f"platform {platform!r} not in supported set",
        )


def validate_quality_config(
    formatters: Sequence[str],
) -> None:
    """Refuse simultaneous formatter registrations."""
    active = {f for f in formatters if f in {"black", "ruff-format"}}
    if len(active) > 1:
        raise CyranoError(
            "FORMATTER_CONFLICT",
            f"multiple formatters registered: {sorted(active)}",
        )


def normalize_test_outcome(
    collected: int,
    passed: int,
    skipped: int,
    required: int,
) -> Mapping[str, object]:
    """Normalize a test run; zero collection or all-skip is not pass."""
    if collected == 0:
        return {"outcome": "failed", "reason": "no_tests_collected"}
    if skipped >= collected:
        return {
            "outcome": "not_applicable",
            "reason": "all_required_skipped",
            "counts_as_required": False,
        }
    outcome = "passed" if passed == collected - skipped else "failed"
    return {"outcome": outcome, "counts_as_required": required > 0}


def split_baseline_findings(
    current: Sequence[str],
    baseline: Sequence[str],
    approved_exceptions: Sequence[str],
) -> Mapping[str, object]:
    """Separate pre-existing findings from new violations."""
    base = set(baseline)
    exceptions = set(approved_exceptions)
    new = sorted(set(current) - base)
    return {
        "existing": sorted(set(current) & base),
        "new": tuple(new),
        "excepted": sorted(set(new) & exceptions),
        "unapproved_new": tuple(n for n in new if n not in exceptions),
    }


def check_format_scope(
    recipe_targets: Sequence[str], approved_scope: Sequence[str]
) -> None:
    """Refuse a format recipe that writes outside approved scope."""
    scope = set(approved_scope)
    for target in recipe_targets:
        if target not in scope:
            raise CyranoError(
                "PATH_POLICY_VIOLATION",
                f"format target {target} outside approved scope",
            )


def find_swallowed_errors(source: str) -> tuple[int, ...]:
    """Locate ``except`` handlers that swallow failures silently.

    A bare swallow hides typed errors; each match must become a
    typed error with a failure report, never a pass.
    """
    pattern = re.compile(r"except\b[^:]*:\s*pass\b")
    return tuple(
        source[: m.start()].count("\n") + 1 for m in pattern.finditer(source)
    )


def sanitize_test_env(env: Mapping[str, str]) -> Mapping[str, str]:
    """Strip test-environment injection vectors from the allowlist."""
    return {k: v for k, v in env.items() if k not in TEST_ENV_DENYLIST}


def verify_locked_install(argv: Sequence[str]) -> None:
    """Require ``--locked``; lock rewrites during install refuse."""
    if "--locked" not in argv:
        raise CyranoError(
            "POLICY_VIOLATION",
            "dependency install must run with --locked",
        )


def aggregate_ci_results(
    jobs: Sequence[Mapping[str, object]],
) -> Mapping[str, object]:
    """Aggregate CI; a skipped or cancelled required job fails."""
    for job in jobs:
        conclusion = str(job.get("conclusion", ""))
        if job.get("required") and conclusion != "success":
            return {
                "aggregate": "failed",
                "blocking_job": job.get("name"),
                "conclusion": conclusion,
            }
    return {"aggregate": "passed", "blocking_job": None}


def guard_quality_recipe(recipe_digest: str, pinned_digest: str) -> None:
    """Refuse a quality recipe that differs from the pinned one.

    A candidate that rewrites the gate to always-pass is detected by
    digest drift and blocked before it runs.
    """
    if recipe_digest != pinned_digest:
        raise CyranoError(
            "TRUST_MISMATCH",
            "quality recipe differs from the pinned approval",
        )


def check_promotion_evidence(
    candidate_digest: str, evidence_digest: str
) -> None:
    """Refuse promotion when candidate and evidence digests diverge."""
    if candidate_digest != evidence_digest:
        raise CyranoError(
            "STALE_EVIDENCE",
            "candidate artifact hash differs from evaluated evidence",
        )


def collect_release_readiness(
    criteria: Sequence[Mapping[str, object]],
    evidence: Mapping[str, Mapping[str, object]],
) -> Mapping[str, object]:
    """Compute a scorecard from real evidence only.

    Criteria with only documents or synthetic fixtures stay
    ``not_evaluated`` at zero points — preparation artifacts never
    award product credit.
    """
    rows = []
    for criterion in criteria:
        cid = str(criterion["id"])
        ev_raw = evidence.get(cid)
        ev = ev_raw if isinstance(ev_raw, Mapping) else None
        real = bool(ev and ev.get("verified") and ev.get("reviewed"))
        max_raw = criterion.get("maximum", criterion.get("max_points", 0))
        maximum = int(max_raw) if isinstance(max_raw, int) else 0
        refs_raw = ev.get("refs", ()) if ev else ()
        refs = (
            [str(r) for r in refs_raw]
            if isinstance(refs_raw, (list, tuple))
            else []
        )
        rows.append(
            {
                "id": cid,
                "maximum": maximum,
                "status": "evaluated" if real else "not_evaluated",
                "points": maximum if real else 0,
                "evidence_refs": refs,
            }
        )
    verified = sum(r["points"] for r in rows)
    return {"criteria": rows, "verified_points": verified}


def evaluate_release_eligibility(
    scorecard: Mapping[str, object],
    hard_failures: Sequence[str],
    required_gates: Mapping[str, str] | None = None,
) -> Mapping[str, object]:
    """Decide eligibility; hard failures are never offset by totals."""
    criteria_raw = scorecard.get("criteria", ())
    criteria_list = (
        criteria_raw if isinstance(criteria_raw, (list, tuple)) else ()
    )
    unevaluated = [
        r.get("id")
        for r in criteria_list
        if isinstance(r, Mapping) and r.get("status") != "evaluated"
    ]
    gates = dict(required_gates or {})
    unmet = sorted(
        name for name, status in gates.items() if status != "passed"
    )
    eligible = not hard_failures and not unevaluated and not unmet
    return {
        "release_eligible": eligible,
        "hard_failures": tuple(hard_failures),
        "unevaluated": tuple(unevaluated),
        "unmet_gates": tuple(unmet),
        "basis": "hard failure, missing evidence or unmet gate blocks"
        if not eligible
        else "all criteria evaluated, gates passed, no hard failure",
    }


def launch_preflight(
    features: Mapping[str, object],
    sandbox_evidence: Mapping[str, object] | None,
) -> Mapping[str, object]:
    """Decide governed readiness before a launch.

    Offline demos and advisory runs without a same-UID sandbox do
    not establish governed readiness, regardless of feature states.
    """
    governed = bool(
        sandbox_evidence
        and sandbox_evidence.get("same_uid_sandbox")
        and sandbox_evidence.get("governed_run")
    )
    return {
        "governed_ready": governed,
        "advisory_only": not governed,
        "features": {
            fid: resolve_feature_state(fid, features).stage for fid in features
        },
    }


def check_tool_epoch(
    locked_version: str, observed_version: str
) -> Mapping[str, object]:
    """Pin the current tool epoch; a version swap needs a new probe.

    A tool replaced mid-use never silently rebinding the epoch —
    the locked version stays authoritative until a new probe and
    review re-locks it.
    """
    return {
        "epoch_version": locked_version,
        "changed": observed_version != locked_version,
        "requires_new_probe": observed_version != locked_version,
    }


def record_upstream_observation(
    observed_version: str, current_version: str
) -> Mapping[str, object]:
    """Record an upstream release sighting without adopting it.

    A newer upstream version is logged for separate review — the
    working base never updates itself.
    """
    return {
        "observed": observed_version,
        "current": current_version,
        "action": "record_only",
        "requires_separate_review": observed_version != current_version,
    }
