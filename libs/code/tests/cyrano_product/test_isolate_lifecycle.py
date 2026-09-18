"""WP03 isolation lifecycle cases ISOLATE-001..012."""

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.dcode.sandbox import (
    isolation_verdict,
    plan_sandbox,
)
from deepagents_code.cyrano.kernel.actions import (
    ActionBroker,
    Grant,
    check_payload_budget,
    intersect_grants,
    reject_ambiguous_path,
)
from deepagents_code.cyrano.kernel.approvals import issue_permit

KEY = Ed25519PrivateKey.generate()
PUB = KEY.public_key()
SUBJECT = "sha256:" + "a" * 64
NO_REVOKE = lambda pid: False  # noqa: E731


def _permit(**over):
    fields = {
        "permit_id": "p1",
        "subject_digest": SUBJECT,
        "shown_digest": "sha256:" + "b" * 64,
        "user_event_id": "ue1",
        "scope_id": "s1",
        "purpose": "execute",
        "audience": "user1",
        "nonce": "n1",
        "issued_at": 0,
        "expires_at": 1000,
    }
    fields.update(over)
    return issue_permit(KEY, **fields)


def _broker(**kw):
    kw.setdefault("tools", frozenset({"write_file"}))
    kw.setdefault("grants", ())
    kw.setdefault("audit", lambda d: None)
    return ActionBroker(**kw)


def test_isolate_001_unpermitted_native_write_denied():
    denials: list[str] = []
    broker = _broker(audit=denials.append)
    decision = broker.decide(
        tool="write_file",
        action="write_existing",
        path="a.py",
        permit=None,
        trust_root=PUB,
        subject_digest=SUBJECT,
        now=1,
        is_revoked=NO_REVOKE,
    )
    assert decision.allowed is False
    broker.deny_event("write_file:a.py")
    assert denials  # denial is on the ledger


def test_isolate_002_unpermitted_shell_write_denied():
    broker = _broker(tools=frozenset({"shell"}))
    decision = broker.decide(
        tool="shell",
        action="write_existing",
        path="protected",
        permit=None,
        trust_root=PUB,
        subject_digest=SUBJECT,
        now=1,
        is_revoked=NO_REVOKE,
    )
    assert decision.allowed is False


def test_isolate_003_unapproved_mcp_denied():
    broker = _broker(tools=frozenset())
    decision = broker.decide(
        tool="external_mcp",
        action="write_existing",
        path="a.py",
        permit=_permit(),
        trust_root=PUB,
        subject_digest=SUBJECT,
        now=1,
        is_revoked=NO_REVOKE,
    )
    assert decision.code == "UNKNOWN_TOOL"


def test_isolate_004_child_scope_is_intersection():
    parent = (Grant("src", allow=frozenset({"read"})),)
    child = (
        Grant("src", allow=frozenset({"read", "write_existing"})),
        Grant("secrets", allow=frozenset({"read"})),
    )
    effective = intersect_grants(parent, child)
    broker = _broker(grants=effective)
    d1 = broker.decide(
        tool="write_file",
        action="write_existing",
        path="src",
        permit=_permit(),
        trust_root=PUB,
        subject_digest=SUBJECT,
        now=1,
        is_revoked=NO_REVOKE,
    )
    d2 = broker.decide(
        tool="write_file",
        action="read",
        path="secrets",
        permit=_permit(),
        trust_root=PUB,
        subject_digest=SUBJECT,
        now=1,
        is_revoked=NO_REVOKE,
    )
    assert d1.code == "SCOPE_DENIED"
    assert d2.code == "SCOPE_DENIED"


def test_isolate_005_headless_without_policy_blocked():
    broker = _broker()
    decision = broker.decide(
        tool="write_file",
        action="read",
        path="a.py",
        permit=_permit(),
        trust_root=PUB,
        subject_digest=SUBJECT,
        now=1,
        is_revoked=NO_REVOKE,
        mode="headless",
        headless_policy=False,
    )
    assert decision.code == "BLOCKED"


def test_isolate_006_forged_actor_denied():
    broker = _broker()
    decision = broker.decide(
        tool="write_file",
        action="read",
        path="a.py",
        permit=_permit(),
        trust_root=PUB,
        subject_digest=SUBJECT,
        now=1,
        is_revoked=NO_REVOKE,
        actor="mallory",
        authenticated_actor="user1",
    )
    assert decision.code == "ACL_DENIED"


def test_isolate_007_unvetted_recipe_refused():
    broker = _broker(tools=frozenset({"execute_recipe"}))
    decision = broker.decide(
        tool="execute_recipe",
        action="write_existing",
        path="setup.py",
        permit=_permit(),
        trust_root=PUB,
        subject_digest=SUBJECT,
        now=1,
        is_revoked=NO_REVOKE,
        recipe_approved=False,
    )
    assert decision.code == "UNVERIFIED_RECIPE"


def test_isolate_008_symlinked_intermediate_denied(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    secret = tmp_path / "secret"
    secret.mkdir()
    linkdir = real / "linkdir"
    linkdir.symlink_to(secret)
    with pytest.raises(CyranoError) as exc:
        plan_sandbox(
            [(str(linkdir / "f.txt"), "/w/f", "ro")],
            workspace_root=real,
        )
    assert exc.value.code == "PATH_ESCAPE"


def test_isolate_009_case_ambiguous_path_denied():
    with pytest.raises(CyranoError) as exc:
        reject_ambiguous_path(["A.py", "a.py"])
    assert exc.value.code == "PATH_AMBIGUOUS"


def test_isolate_010_agent_writable_approval_db_not_governed():
    verdict = isolation_verdict(
        agent_reads_approval_key=False,
        agent_writes_approval_db=True,
        same_user_unrestricted_shell=False,
    )
    assert verdict.governed is False


def test_isolate_011_oversize_decompressed_rejected():
    with pytest.raises(CyranoError) as exc:
        check_payload_budget(b"z", b"x" * 2048, cap=1024)
    assert exc.value.code == "PAYLOAD_TOO_LARGE"


def test_isolate_012_permission_module_failure_closes():
    def exploding_audit(detail):
        raise RuntimeError("module import failed")

    broker = _broker(audit=exploding_audit)
    with pytest.raises(CyranoError) as exc:
        broker.apply_scoped_patch(
            permit=_permit(),
            trust_root=PUB,
            subject_digest=SUBJECT,
            now=1,
            is_revoked=NO_REVOKE,
            apply_fn=lambda: pytest.fail("no side effect"),
        )
    assert exc.value.code == "AUDIT_UNAVAILABLE"
