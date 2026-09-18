"""R3-24 governed-integration cases: criterion 2-4 write boundary.

Each test composes the real approval, broker, and sandbox surfaces.
A mutation is applied only through ``apply_scoped_patch`` after a
signed permit verifies; every other path must deny before any side
effect. Denials are proven by unchanged file bytes, not only by
returned codes.
"""

import os

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.dcode.sandbox import plan_sandbox
from deepagents_code.cyrano.kernel.actions import (
    ActionBroker,
    Grant,
)
from deepagents_code.cyrano.kernel.approvals import (
    issue_permit,
)

KEY = Ed25519PrivateKey.generate()
ROOT_PUB = KEY.public_key()
SUBJECT = "sha256:" + "a" * 64
NOT_REVOKED = lambda pid: False  # noqa: E731


def _permit(**over):
    fields = {
        "permit_id": "p-r3",
        "subject_digest": SUBJECT,
        "shown_digest": "sha256:" + "b" * 64,
        "user_event_id": "ue1",
        "scope_id": "s1",
        "purpose": "execute",
        "audience": "user1",
        "nonce": "n1",
        "issued_at": 0,
        "expires_at": 10_000,
    }
    fields.update(over)
    return issue_permit(KEY, **fields)


class GovernedRunner:
    """Minimal governed dispatch: every tool call passes the broker."""

    ALL_TOOLS = frozenset(
        {
            "write_file",
            "edit_file",
            "execute_python",
            "shell",
            "mcp_writer",
            "child_task",
        }
    )

    def __init__(self, grants, audit):
        """Bind the real broker and the durable audit sink."""
        self.broker = ActionBroker(self.ALL_TOOLS, grants, audit)
        self.audit = audit

    def dispatch(self, tool, action, path, permit, **kw):
        decision = self.broker.decide(
            tool=tool,
            action=action,
            path=path,
            permit=permit,
            trust_root=ROOT_PUB,
            subject_digest=SUBJECT,
            now=kw.pop("now", 1),
            is_revoked=kw.pop("is_revoked", NOT_REVOKED),
            **kw,
        )
        if not decision.allowed:
            self.broker.deny_event(f"{tool}:{path}:{decision.code}")
        return decision


def test_r3_24_01(tmp_path):
    """Approved edit changes only the granted file, with receipts."""
    target = tmp_path / "a.py"
    target.write_text("old\n")
    other = tmp_path / "b.py"
    other.write_text("keep\n")
    audit: list[str] = []
    runner = GovernedRunner(
        (Grant("a.py", allow=frozenset({"write_existing"})),),
        audit.append,
    )
    permit = _permit()
    decision = runner.dispatch("edit_file", "write_existing", "a.py", permit)
    assert decision.allowed

    def apply():
        target.write_text("new\n")

    runner.broker.apply_scoped_patch(
        permit=permit,
        trust_root=ROOT_PUB,
        subject_digest=SUBJECT,
        now=1,
        is_revoked=NOT_REVOKED,
        apply_fn=apply,
    )
    assert target.read_text() == "new\n"
    assert other.read_text() == "keep\n"
    assert any(e.startswith("apply:") for e in audit)
    assert any(e.startswith("applied:") for e in audit)


def test_r3_24_02(tmp_path):
    """Unapproved file tools deny; bytes and audit prove no effect."""
    target = tmp_path / "a.py"
    target.write_text("old\n")
    audit: list[str] = []
    runner = GovernedRunner(
        (Grant("a.py", allow=frozenset({"write_existing"})),),
        audit.append,
    )
    for tool in ("write_file", "edit_file"):
        decision = runner.dispatch(tool, "write_existing", "a.py", None)
        assert decision.code == "APPROVAL_REQUIRED"
    assert target.read_text() == "old\n"
    assert audit == [
        "denied:write_file:a.py:APPROVAL_REQUIRED",
        "denied:edit_file:a.py:APPROVAL_REQUIRED",
    ]


def test_r3_24_03(tmp_path):
    """Shell, MCP writer, and child-task bypasses deny pre-effect."""
    target = tmp_path / "a.py"
    target.write_text("old\n")
    audit: list[str] = []
    runner = GovernedRunner(
        (Grant("a.py", allow=frozenset({"read"})),),
        audit.append,
    )
    permit = _permit()
    for tool in ("execute_python", "shell", "mcp_writer", "child_task"):
        decision = runner.dispatch(tool, "write_existing", "a.py", permit)
        assert decision.allowed is False, tool
        assert decision.code == "SCOPE_DENIED"
    assert target.read_text() == "old\n"
    assert len(audit) == 4


def test_r3_24_04(tmp_path):
    """Revocation between decide and apply still blocks the write."""
    target = tmp_path / "a.py"
    target.write_text("old\n")
    audit: list[str] = []
    runner = GovernedRunner(
        (Grant("a.py", allow=frozenset({"write_existing"})),),
        audit.append,
    )
    permit = _permit()
    decision = runner.dispatch("edit_file", "write_existing", "a.py", permit)
    assert decision.allowed
    with pytest.raises(CyranoError) as exc:
        runner.broker.apply_scoped_patch(
            permit=permit,
            trust_root=ROOT_PUB,
            subject_digest=SUBJECT,
            now=1,
            is_revoked=lambda pid: True,
            apply_fn=lambda: target.write_text("evil\n"),
        )
    assert exc.value.code == "PERMIT_REVOKED"
    assert target.read_text() == "old\n"


def test_r3_24_05(tmp_path):
    """Unsupported modes refuse before dispatch; resume is supported."""
    audit: list[str] = []
    runner = GovernedRunner(
        (Grant("a.py", allow=frozenset({"write_existing"})),),
        audit.append,
    )
    permit = _permit()
    for mode in ("yolo", "planning"):
        decision = runner.dispatch(
            "edit_file",
            "write_existing",
            "a.py",
            permit,
            mode=mode,
        )
        assert decision.code == "UNSUPPORTED_MODE"
    for mode in ("manual", "auto", "headless", "acp", "resume"):
        decision = runner.dispatch(
            "edit_file",
            "write_existing",
            "a.py",
            permit,
            mode=mode,
        )
        assert decision.allowed, mode


def test_r3_24_06(tmp_path):
    """Symlink, hardlink, and dotdot escapes deny; source unchanged."""
    original = tmp_path / "original.txt"
    original.write_text("precious\n")
    scratch = tmp_path / "scratch"
    scratch.mkdir()

    link = scratch / "link"
    link.symlink_to(original)
    with pytest.raises(CyranoError) as exc:
        plan_sandbox(
            [(str(link), "/work/link", "scratch")],
            workspace_root=scratch,
        )
    assert exc.value.code == "PATH_ESCAPE"

    hard = scratch / "hard"
    os.link(original, hard)
    st = original.stat()
    with pytest.raises(CyranoError) as exc:
        plan_sandbox(
            [(str(hard), "/work/hard", "scratch")],
            workspace_root=scratch,
            protected_inodes={(st.st_dev, st.st_ino)},
        )
    assert exc.value.code == "PROTECTED_ALIAS"

    with pytest.raises(CyranoError) as exc:
        plan_sandbox(
            [(str(scratch / ".." / "original.txt"), "/w/o", "ro")],
            workspace_root=scratch,
        )
    assert exc.value.code == "PATH_ESCAPE"

    assert original.read_text() == "precious\n"
