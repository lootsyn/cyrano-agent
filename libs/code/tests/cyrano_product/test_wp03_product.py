"""WP03 product tests: permits, broker, sandbox, R3-24 paths."""

from dataclasses import replace

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
    issue_permit,
    verify_permit,
)

KEY = Ed25519PrivateKey.generate()
ROOT_PUB = KEY.public_key()
SUBJECT = "sha256:" + "a" * 64
NOT_REVOKED = lambda pid: False  # noqa: E731


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


def _broker(
    tools=frozenset({"write_file", "edit_file"}),
    grants=(),
    audit=lambda d: None,
):
    return ActionBroker(tools, grants, audit)


class TestAuthPermits:
    """AUTH-FAKE/PURPOSE/REVOKE: permits are cryptographic."""

    def test_auth_fake_no_authority_denied(self):
        decision = _broker().decide(
            tool="write_file",
            action="write_existing",
            path="a.py",
            permit=None,
            trust_root=ROOT_PUB,
            subject_digest=SUBJECT,
            now=1,
            is_revoked=NOT_REVOKED,
        )
        assert decision.allowed is False
        assert decision.code == "APPROVAL_REQUIRED"

    def test_forged_permit_rejected(self):
        permit = _permit()
        forged = replace(permit, shown_digest="sha256:" + "c" * 64)
        with pytest.raises(CyranoError) as exc:
            verify_permit(
                forged,
                ROOT_PUB,
                purpose="execute",
                subject_digest=SUBJECT,
                now=1,
                is_revoked=NOT_REVOKED,
            )
        assert exc.value.code == "INVALID_SIGNATURE"

    def test_auth_purpose_wrong_action(self):
        permit = _permit(purpose="plan_approval")
        with pytest.raises(CyranoError) as exc:
            verify_permit(
                permit,
                ROOT_PUB,
                purpose="execute",
                subject_digest=SUBJECT,
                now=1,
                is_revoked=NOT_REVOKED,
            )
        assert exc.value.code == "WRONG_APPROVAL_ACTION"

    def test_auth_revoke_blocks(self):
        permit = _permit()
        with pytest.raises(CyranoError) as exc:
            verify_permit(
                permit,
                ROOT_PUB,
                purpose="execute",
                subject_digest=SUBJECT,
                now=1,
                is_revoked=lambda pid: True,
            )
        assert exc.value.code == "PERMIT_REVOKED"

    def test_expired_permit(self):
        permit = _permit(expires_at=10)
        with pytest.raises(CyranoError) as exc:
            verify_permit(
                permit,
                ROOT_PUB,
                purpose="execute",
                subject_digest=SUBJECT,
                now=11,
                is_revoked=NOT_REVOKED,
            )
        assert exc.value.code == "PERMIT_EXPIRED"


class TestSandboxBoundaries:
    """AUTH-SYMLINK/PRINCIPAL/DOCKER isolation refusals."""

    def test_auth_symlink_escape_denied(self, tmp_path):
        outside = tmp_path.parent / "outside.txt"
        outside.write_text("x")
        link = tmp_path / "link"
        link.symlink_to(outside)
        with pytest.raises(CyranoError) as exc:
            plan_sandbox(
                [(str(link), "/work/link", "ro")],
                workspace_root=tmp_path,
            )
        assert exc.value.code == "PATH_ESCAPE"

    def test_auth_docker_socket_needs_approval(self, tmp_path):
        with pytest.raises(CyranoError) as exc:
            plan_sandbox(
                [("/var/run/docker.sock", "/docker.sock", "scratch")],
                workspace_root=tmp_path,
            )
        assert exc.value.code == "MOUNT_DENIED"

    def test_auth_principal_advisory_only(self):
        verdict = isolation_verdict(
            agent_reads_approval_key=False,
            agent_writes_approval_db=False,
            same_user_unrestricted_shell=True,
        )
        assert verdict.governed is False
        assert verdict.advisories

    def test_key_reachability_blocks_governed(self):
        verdict = isolation_verdict(
            agent_reads_approval_key=True,
            agent_writes_approval_db=False,
            same_user_unrestricted_shell=False,
        )
        assert verdict.governed is False


class TestBrokerEnforcement:
    """R3-24: every mutation path gated by the same broker."""

    def test_permitted_write_applies_with_receipt(self):
        audit_log: list[str] = []
        broker = _broker(
            grants=(Grant("a.py", allow=frozenset({"write_existing"})),),
            audit=audit_log.append,
        )
        permit = _permit()
        applied: list[str] = []
        broker.apply_scoped_patch(
            permit=permit,
            trust_root=ROOT_PUB,
            subject_digest=SUBJECT,
            now=1,
            is_revoked=NOT_REVOKED,
            apply_fn=lambda: applied.append("ok"),
        )
        assert applied == ["ok"]
        assert any("apply:" in e for e in audit_log)

    def test_write_without_permit_denied_and_logged(self):
        denials: list[str] = []
        broker = _broker(
            grants=(Grant("a.py", allow=frozenset({"write_existing"})),),
            audit=denials.append,
        )
        decision = broker.decide(
            tool="write_file",
            action="write_existing",
            path="a.py",
            permit=None,
            trust_root=ROOT_PUB,
            subject_digest=SUBJECT,
            now=1,
            is_revoked=NOT_REVOKED,
        )
        assert decision.code == "APPROVAL_REQUIRED"
        broker.deny_event("write_file:a.py")
        assert denials == ["denied:write_file:a.py"]

    def test_every_mutation_path_denied(self):
        broker = _broker(
            tools=frozenset(
                {
                    "write_file",
                    "edit_file",
                    "execute_python",
                    "shell",
                    "mcp_writer",
                    "child_task",
                }
            ),
            grants=(Grant("a.py", allow=frozenset({"read"})),),
        )
        for tool in (
            "write_file",
            "edit_file",
            "execute_python",
            "shell",
            "mcp_writer",
            "child_task",
        ):
            decision = broker.decide(
                tool=tool,
                action="write_existing",
                path="a.py",
                permit=None,
                trust_root=ROOT_PUB,
                subject_digest=SUBJECT,
                now=1,
                is_revoked=NOT_REVOKED,
            )
            assert decision.allowed is False, tool

    def test_revocation_rechecked_at_apply(self):
        audit: list[str] = []
        broker = _broker(audit=audit.append)
        permit = _permit()
        with pytest.raises(CyranoError) as exc:
            broker.apply_scoped_patch(
                permit=permit,
                trust_root=ROOT_PUB,
                subject_digest=SUBJECT,
                now=1,
                is_revoked=lambda pid: True,
                apply_fn=lambda: None,
            )
        assert exc.value.code == "PERMIT_REVOKED"

    def test_unsupported_mode_refused(self):
        decision = _broker().decide(
            tool="write_file",
            action="read",
            path="a.py",
            permit=None,
            trust_root=ROOT_PUB,
            subject_digest=SUBJECT,
            now=1,
            is_revoked=NOT_REVOKED,
            mode="yolo",
        )
        assert decision.code == "UNSUPPORTED_MODE"

    def test_audit_failure_blocks_side_effect(self):
        def bad_audit(detail):
            raise CyranoError("AUDIT_UNAVAILABLE", detail)

        broker = _broker(audit=bad_audit)
        with pytest.raises(CyranoError) as exc:
            broker.apply_scoped_patch(
                permit=_permit(),
                trust_root=ROOT_PUB,
                subject_digest=SUBJECT,
                now=1,
                is_revoked=NOT_REVOKED,
                apply_fn=lambda: pytest.fail("must not run"),
            )
        assert exc.value.code == "AUDIT_UNAVAILABLE"


class TestGrantIntersection:
    """UH-AUTH-06/07 shape: intersection and create rules."""

    def test_intersection_denies_expansion(self):
        parent = (Grant("a.py", allow=frozenset({"write_existing"})),)
        child = (Grant("b.py", allow=frozenset({"write_existing"})),)
        effective = intersect_grants(parent, child)
        broker = _broker(grants=effective)
        decision = broker.decide(
            tool="write_file",
            action="write_existing",
            path="b.py",
            permit=_permit(),
            trust_root=ROOT_PUB,
            subject_digest=SUBJECT,
            now=1,
            is_revoked=NOT_REVOKED,
        )
        assert decision.code == "SCOPE_DENIED"
