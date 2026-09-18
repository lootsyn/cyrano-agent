"""WP12 product tests: skill registry, release projection, controls."""

import json
from pathlib import Path

import pytest

from deepagents_code.cyrano.context.projection import ReleaseProjection
from deepagents_code.cyrano.context.run_controls import (
    GOVERNED_CAPABILITIES,
    RunControls,
)
from deepagents_code.cyrano.context.skills import (
    SkillRegistry,
    parse_manifest,
)
from deepagents_code.cyrano.contracts.types import CyranoError

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "cyrano/configs/skills"
SCOPE = ("t1", "u1", "w1")

SKILL_NAMES = [
    "blind-handoff",
    "cache-context",
    "candidate-authoring",
    "decision-interview",
    "evidence-scout",
    "exploration-policy",
    "learning-analysis",
    "paired-evaluation-review",
    "plan-and-review",
    "release-review",
    "runtime-code-change",
    "safe-implementation",
    "scoped-memory",
    "verification-recipe",
]


def _bound_doc(name: str, status: str = "active") -> dict:
    doc = json.loads(
        (TEMPLATES / f"{name}.template.json").read_text()
    )
    doc["scope"] = {
        "tenant": "t1",
        "user": "u1",
        "workspace": "w1",
    }
    doc["status"] = status
    return doc


def _register(reg: SkillRegistry, name: str, status: str = "active"):
    manifest = parse_manifest(_bound_doc(name, status))
    reg.register(manifest, resolved_path=f"skills/{name}/SKILL.md")
    return manifest


@pytest.mark.parametrize(
    "name",
    SKILL_NAMES,
    ids=[f"skill_{n.replace('-', '_')}_positive" for n in SKILL_NAMES],
)
def test_skill_positive(name):
    """A bound active skill loads metadata and applies in scope."""
    reg = SkillRegistry()
    _register(reg, name)
    meta = reg.load(name, SCOPE)
    assert meta.entrypoint == "SKILL.md"
    manifest = reg.apply(
        name, SCOPE, role=_first_role(name), conditions_met=True
    )
    assert manifest.skill_id == name


def _first_role(name: str) -> str:
    doc = _bound_doc(name)
    roles = doc.get("allowed_roles") or []
    return roles[0] if roles else "implementer"


@pytest.mark.parametrize(
    "name",
    SKILL_NAMES,
    ids=[f"skill_{n.replace('-', '_')}_negative" for n in SKILL_NAMES],
)
def test_skill_negative(name):
    """A revoked or out-of-scope skill refuses to apply."""
    reg = SkillRegistry()
    _register(reg, name, status="revoked")
    with pytest.raises(CyranoError) as exc:
        reg.apply(
            name, SCOPE, role=_first_role(name), conditions_met=True
        )
    assert exc.value.code == "SKILL_REVOKED"
    with pytest.raises(CyranoError) as exc2:
        reg.load(name, ("t2", "u2", "w2"))
    assert exc2.value.code == "SCOPE_DENIED"


def test_skill_duplicate():
    """The same skill id from two roots is refused."""
    reg = SkillRegistry()
    _register(reg, "plan-and-review")
    with pytest.raises(CyranoError) as exc:
        _register(reg, "plan-and-review")
    assert exc.value.code == "SKILL_DUPLICATE"


def test_skill_executable_requires_lane():
    """A manifest with an executable resource needs a code lane."""
    doc = _bound_doc("plan-and-review")
    doc["resources"] = [
        {"path": "run.sh", "digest": "sha256:" + "0" * 64,
         "executable": True}
    ]
    with pytest.raises(CyranoError) as exc:
        parse_manifest(doc)
    assert exc.value.code == "EXECUTION_PERMISSION_REQUIRED"
    doc["grants_execution"] = True
    assert parse_manifest(doc).grants_execution is True


def test_skill_load_is_metadata_only():
    """Loading never injects the body; it is not an application."""
    reg = SkillRegistry()
    _register(reg, "cache-context")
    meta = reg.load("cache-context", SCOPE)
    assert not hasattr(meta, "body")
    assert meta.status == "active"


def test_skill_template_unbound_refused():
    """A manifest with __BIND_*__ placeholders is refused."""
    doc = json.loads(
        (TEMPLATES / "plan-and-review.template.json").read_text()
    )
    with pytest.raises(CyranoError) as exc:
        parse_manifest(doc)
    assert exc.value.code == "TEMPLATE_UNBOUND"


def test_uh_mem_08_remember_bypass_refused():
    """Direct promotion outside the candidate flow is blocked."""
    reg = SkillRegistry()
    _register(reg, "scoped-memory")
    with pytest.raises(CyranoError) as exc:
        reg.promote_direct("scoped-memory")
    assert exc.value.code == "CANDIDATE_BYPASS"


def test_uh_mem_14_metadata_only_exposure():
    """Many irrelevant skills expose metadata only, no bodies."""
    reg = SkillRegistry()
    for name in SKILL_NAMES:
        _register(reg, name)
    view = reg.metadata_view(SCOPE)
    assert len(view) == len(SKILL_NAMES)
    assert all(not hasattr(m, "body") for m in view)
    foreign = reg.metadata_view(("t9", "u9", "w9"))
    assert foreign == ()


def test_peq_py_t44_budget_stagnation_abort():
    """Three identical errors or two stagnant attempts abort."""
    controls = RunControls(max_same_error=3, max_stagnant=2)
    assert controls.record_attempt("e1", changed=True) == "continue"
    assert controls.record_attempt("e1", changed=True) == "continue"
    assert controls.record_attempt("e1", changed=True) == "abort"
    fresh = RunControls(max_same_error=3, max_stagnant=2)
    assert fresh.record_attempt("e1", changed=False) == "continue"
    assert fresh.record_attempt("e2", changed=False) == "abort"


def test_peq_py_t45_cancel_terminates():
    """User cancel ends the run; further attempts refuse."""
    controls = RunControls()
    assert controls.cancel() == "CANCELLED"
    assert controls.cancelled is True
    with pytest.raises(CyranoError) as exc:
        controls.record_attempt("e1", changed=True)
    assert exc.value.code == "RUN_CANCELLED"


def test_peq_py_t46_complete_needs_implementation():
    """A bare 'done' claim never transitions to COMPLETE."""
    controls = RunControls()
    with pytest.raises(CyranoError) as exc:
        controls.request_complete(implemented=False)
    assert exc.value.code == "COMPLETE_WITHOUT_EVIDENCE"
    controls.request_complete(implemented=True)


def test_peq_py_t47_stop_hook_absent_no_complete():
    """Missing or timed-out hook allows exit, never COMPLETE."""
    controls = RunControls()
    v = controls.evaluate_stop_hook(
        hook_installed=False, hook_timed_out=False
    )
    assert v.native_exit_allowed is True
    assert v.complete_allowed is False
    v2 = controls.evaluate_stop_hook(
        hook_installed=True, hook_timed_out=True
    )
    assert v2.complete_allowed is False


def test_peq_py_t48_prompt_only_lacks_governed():
    """A prompt-only subagent is detected as ungoverned."""
    controls = RunControls()
    assert controls.governed_capability_met(frozenset()) is False
    assert (
        controls.governed_capability_met(GOVERNED_CAPABILITIES) is True
    )


def test_peq_py_t49_release_mix_refused():
    """One skill id resolving twice in a release is refused."""
    proj = ReleaseProjection()
    proj.pin_skill("r1", "s1", resolved_path="p/a", digest="d1")
    with pytest.raises(CyranoError) as exc:
        proj.pin_skill("r1", "s1", resolved_path="p/b", digest="d2")
    assert exc.value.code == "RELEASE_MIX"


def test_peq_py_t50_resume_keeps_pin():
    """Resume under a new release keeps the pin unless restarted."""
    proj = ReleaseProjection()
    proj.pin_skill("r1", "s1", resolved_path="p/a", digest="d1")
    proj.pin_skill("r2", "s1", resolved_path="p/a", digest="d2")
    proj.pin_attempt("att1", "r1")
    resumed = proj.resume("att1", offered_release="r2")
    assert resumed.release_id == "r1"
    restarted = proj.resume(
        "att1", offered_release="r2", explicit_restart=True
    )
    assert restarted.release_id == "r2"
