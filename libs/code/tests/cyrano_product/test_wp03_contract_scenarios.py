"""WP03 contract scenarios UH-AUTH-01..14 and INTEG-ONLY-WRITE."""

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
    intersect_grants,
)
from deepagents_code.cyrano.kernel.approvals import (
    ApprovalDesk,
    issue_permit,
    verify_permit,
)

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
    kw.setdefault("tools", frozenset({"write_file", "mcp_tool"}))
    kw.setdefault("grants", ())
    kw.setdefault("audit", lambda d: None)
    return ActionBroker(**kw)


def test_uh_auth_01_worker_token_denied_on_user_endpoint():
    desk = ApprovalDesk()
    rec = desk.present(
        subject_digest=SUBJECT,
        shown_text="approve?",
        audience="user1",
        nonce="n1",
        expires_at=100,
    )
    desk.open_display(rec.request_id)
    with pytest.raises(CyranoError) as exc:
        desk.submit(
            rec.request_id,
            actor="worker-token",
            nonce="n1",
            decision="approve",
            shown_text="approve?",
            display_revision=1,
            client_event_id="e1",
            now=1,
        )
    assert exc.value.code == "ACL_DENIED"


def test_uh_auth_02_tampered_permit_invalid_signature():
    from dataclasses import replace

    permit = _permit()
    tampered = replace(permit, subject_digest="sha256:" + "9" * 64)
    with pytest.raises(CyranoError) as exc:
        verify_permit(
            tampered,
            PUB,
            purpose="execute",
            subject_digest="sha256:" + "9" * 64,
            now=1,
            is_revoked=NO_REVOKE,
        )
    assert exc.value.code == "INVALID_SIGNATURE"


def test_uh_auth_03_plan_receipt_not_execution():
    permit = _permit(purpose="plan_approval")
    with pytest.raises(CyranoError) as exc:
        verify_permit(
            permit,
            PUB,
            purpose="execute",
            subject_digest=SUBJECT,
            now=1,
            is_revoked=NO_REVOKE,
        )
    assert exc.value.code == "WRONG_APPROVAL_ACTION"


def test_uh_auth_04_expired_permit_denied():
    permit = _permit(expires_at=50)
    with pytest.raises(CyranoError) as exc:
        verify_permit(
            permit,
            PUB,
            purpose="execute",
            subject_digest=SUBJECT,
            now=60,
            is_revoked=NO_REVOKE,
        )
    assert exc.value.code == "PERMIT_EXPIRED"


def test_uh_auth_05_revoked_parent_blocks_dispatch():
    broker = _broker()
    permit = _permit()
    applied: list[str] = []
    with pytest.raises(CyranoError) as exc:
        broker.apply_scoped_patch(
            permit=permit,
            trust_root=PUB,
            subject_digest=SUBJECT,
            now=1,
            is_revoked=lambda pid: True,
            apply_fn=lambda: applied.append("x"),
        )
    assert exc.value.code == "PERMIT_REVOKED"
    assert applied == []


def test_uh_auth_06_intersection_only():
    session = (Grant("a.py", allow=frozenset({"write_existing"})),)
    role = (Grant("b.py", allow=frozenset({"write_existing"})),)
    effective = intersect_grants(session, role)
    broker = _broker(grants=effective)
    decision = broker.decide(
        tool="write_file",
        action="write_existing",
        path="b.py",
        permit=_permit(),
        trust_root=PUB,
        subject_digest=SUBJECT,
        now=1,
        is_revoked=NO_REVOKE,
    )
    assert decision.code == "SCOPE_DENIED"


def test_uh_auth_07_create_needs_create_grant():
    broker = _broker(
        grants=(Grant("a.py", allow=frozenset({"write_existing"})),)
    )
    decision = broker.decide(
        tool="write_file",
        action="create",
        path="new.py",
        permit=_permit(),
        trust_root=PUB,
        subject_digest=SUBJECT,
        now=1,
        is_revoked=NO_REVOKE,
        preexisting=False,
    )
    assert decision.code == "CREATE_APPROVAL_REQUIRED"


def test_uh_auth_08_symlink_to_protected_denied(tmp_path):
    protected = tmp_path / "protected.txt"
    protected.write_text("secret")
    link = tmp_path / "allowed.txt"
    # symlink inside root pointing outside the workspace root
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    (outside / "file").write_text("x")
    link.symlink_to(outside / "file")
    with pytest.raises(CyranoError) as exc:
        plan_sandbox(
            [(str(link), "/w/allowed.txt", "ro")],
            workspace_root=tmp_path,
        )
    assert exc.value.code == "PATH_ESCAPE"


def test_uh_auth_09_hardlink_to_protected_inode(tmp_path):
    protected = tmp_path / "protected.txt"
    protected.write_text("secret")
    st = protected.stat()
    alias = tmp_path / "alias.txt"
    alias.hardlink_to(protected)
    with pytest.raises(CyranoError) as exc:
        plan_sandbox(
            [(str(alias), "/w/alias.txt", "ro")],
            workspace_root=tmp_path,
            protected_inodes={(st.st_dev, st.st_ino)},
        )
    assert exc.value.code == "PROTECTED_ALIAS"


def test_uh_auth_10_and_integ_only_write_deny_read():
    grants = (
        Grant("out.log", allow=frozenset({"only_write"})),
        Grant("out.log", allow=frozenset({"read"})),
    )
    broker = _broker(grants=grants)
    decision = broker.decide(
        tool="write_file",
        action="read",
        path="out.log",
        permit=_permit(),
        trust_root=PUB,
        subject_digest=SUBJECT,
        now=1,
        is_revoked=NO_REVOKE,
    )
    assert decision.allowed is False
    assert decision.code == "DENIED"


def test_uh_auth_11_ro_source_and_scratch(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    (source / "f.py").write_text("x")
    plan = plan_sandbox(
        [(str(source), "/src", "ro"), (str(tmp_path), "/scratch", "scratch")],
        workspace_root=tmp_path,
    )
    modes = {m.target: m.mode for m in plan.mounts}
    assert modes == {"/src": "ro", "/scratch": "scratch"}


def test_uh_auth_12_unregistered_tool_denied():
    broker = _broker()
    decision = broker.decide(
        tool="brand_new_mcp",
        action="write_existing",
        path="a.py",
        permit=_permit(),
        trust_root=PUB,
        subject_digest=SUBJECT,
        now=1,
        is_revoked=NO_REVOKE,
    )
    assert decision.code == "UNKNOWN_TOOL"


def test_uh_auth_13_audit_failure_blocks_mutation():
    def failing(detail):
        raise RuntimeError("disk full")

    broker = _broker(audit=failing)
    touched: list[str] = []
    with pytest.raises(CyranoError) as exc:
        broker.apply_scoped_patch(
            permit=_permit(),
            trust_root=PUB,
            subject_digest=SUBJECT,
            now=1,
            is_revoked=NO_REVOKE,
            apply_fn=lambda: touched.append("x"),
        )
    assert exc.value.code == "AUDIT_UNAVAILABLE"
    assert touched == []


def test_uh_auth_14_key_reachability_fails_isolation():
    verdict = isolation_verdict(
        agent_reads_approval_key=True,
        agent_writes_approval_db=True,
        same_user_unrestricted_shell=False,
    )
    assert verdict.governed is False
