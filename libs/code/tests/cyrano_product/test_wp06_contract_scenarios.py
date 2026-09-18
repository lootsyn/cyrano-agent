"""WP06 contract scenarios: the PEQ-PY Python quality pack.

Each case runs a real tool (ruff/ty/pytest subprocesses) or the real
ledger — no fixture doubles stand in for execution.
"""

import shutil
import subprocess
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.kernel.approvals import (
    SignedPermit,
    issue_permit,
    verify_permit,
)
from deepagents_code.cyrano.quality.policy import (
    QualityPolicy,
    check_path_in_scope,
    require_run_permit,
    resolve_quality_policy,
)
from deepagents_code.cyrano.quality.runner import (
    Diagnostic,
    QualityReportStore,
    RawCheckReport,
    attempt_outcome,
    compare_diagnostic_multisets,
    run_native_checks,
    snapshot_python_files,
)
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

ROOT = Path(__file__).resolve().parents[2]
TARGET_DDL = (ROOT / "cyrano/contracts/sql/target-schema.sql").read_text()

CLEAN = 'def add(a: int, b: int) -> int:\n    """Add."""\n    return a + b\n'
F401 = 'import os\n\n\ndef f() -> int:\n    """F."""\n    return 1\n'
BAD_FORMAT = "def f( ):\n    return    1\n"
NAMING = "def badFunction():\n    pass\n\n\nclass bad_class:\n    pass\n"
DOCSTYLE = 'def f() -> int:\n    return 1\n'
B006 = "def f(x=[]):\n    return x\n"
TYPE_ERR = 'def f() -> int:\n    return "s"\n'
PYTEST_FAIL = "def test_x():\n    assert False\n"
LONG_DOC = (
    'def f() -> int:\n    """'
    + "word " * 30
    + '"""\n    return 1\n'
)
SUPPRESSED = (
    "import os  # noqa: F401\n\n\ndef f() -> int:\n"
    '    """F."""\n    return 1\n'
)


def _policy(tool: str, **over) -> QualityPolicy:
    config = {"tool": tool, "scope": ["*.py"], "line_length": 79}
    config.update(over)
    return resolve_quality_policy(config)


def _write(root: Path, name: str, src: str) -> Path:
    path = root / name
    path.write_text(src)
    return path


def _run(root: Path, policy: QualityPolicy, **kw) -> RawCheckReport:
    manifest = snapshot_python_files(root)
    return run_native_checks(manifest, policy, root, **kw)


# ---------------------------------------------------- tool runs --


def test_peq_py_t01(tmp_path):
    """Raw FAIL from the formatter is preserved; never a pass."""
    _write(tmp_path, "m.py", BAD_FORMAT)
    report = _run(tmp_path, _policy("ruff-format"))
    assert report.status == "FAIL"
    assert report.exit_code != 0


def test_peq_py_t02(tmp_path):
    """Ruff F401 on a new violation is FAIL with the parsed rule."""
    _write(tmp_path, "m.py", F401)
    report = _run(tmp_path, _policy("ruff", select=["F401"]))
    assert report.status == "FAIL"
    assert {d.rule for d in report.diagnostics} == {"F401"}


def test_peq_py_t03(tmp_path):
    """W505 requires max_doc_length; missing it is a config contract."""
    with pytest.raises(CyranoError) as exc:
        _policy("ruff", select=["W505"])
    assert exc.value.code == "POLICY_CONFIG_MISMATCH"
    _write(tmp_path, "m.py", LONG_DOC)
    policy = _policy("ruff", select=["W505"], max_doc_length=72)
    report = _run(tmp_path, policy)
    assert report.status == "FAIL"
    assert any(d.rule == "W505" for d in report.diagnostics)


def test_peq_py_t04(tmp_path):
    """Selected naming rules diagnose badFunction and bad_class."""
    _write(tmp_path, "m.py", NAMING)
    report = _run(tmp_path, _policy("ruff", select=["N"]))
    rules = {d.rule for d in report.diagnostics}
    assert "N802" in rules and "N801" in rules


def test_peq_py_t05(tmp_path):
    """Selected docstring rules diagnose a missing docstring."""
    _write(tmp_path, "m.py", DOCSTYLE)
    report = _run(tmp_path, _policy("ruff", select=["D"]))
    assert any(d.rule.startswith("D") for d in report.diagnostics)


def test_peq_py_t06(tmp_path):
    """B006 is diagnosed; fixing the code, not ignoring, resolves it."""
    _write(tmp_path, "m.py", B006)
    policy = _policy("ruff", select=["B"])
    assert _run(tmp_path, policy).status == "FAIL"
    _write(tmp_path, "m.py", "def f(x=None):\n    return x or []\n")
    assert _run(tmp_path, policy).status == "PASS"


def test_peq_py_t07(tmp_path):
    """A type error is a raw FAIL from the checker, not a pass."""
    if shutil.which("ty") is None:
        pytest.skip("ty unavailable")  # honest not-run, not a pass
    _write(tmp_path, "m.py", TYPE_ERR)
    report = _run(tmp_path, _policy("ty"))
    assert report.status == "FAIL"


def test_peq_py_t08(tmp_path):
    """A pytest raw FAIL refuses COMPLETE."""
    _write(tmp_path, "test_m.py", PYTEST_FAIL)
    report = _run(tmp_path, _policy("pytest"))
    assert report.status == "FAIL"
    assert attempt_outcome([report]) == "INCOMPLETE"


def test_peq_py_t09(tmp_path):
    """Pytest exit 5 (no tests) is BLOCKED_NO_TESTS, never success."""
    _write(tmp_path, "m.py", CLEAN)
    report = _run(tmp_path, _policy("pytest"))
    assert report.status == "BLOCKED_NO_TESTS"
    assert attempt_outcome([report]) == "INCOMPLETE"


def test_peq_py_t10(tmp_path):
    """An unmet acceptance gate keeps the attempt INCOMPLETE."""
    _write(tmp_path, "m.py", F401)
    report = _run(tmp_path, _policy("ruff", select=["F"]))
    assert attempt_outcome([report]) == "INCOMPLETE"


def test_peq_py_t11(tmp_path):
    """One clean file does not average away a FAIL report."""
    _write(tmp_path, "m.py", F401)
    fail = _run(tmp_path, _policy("ruff", select=["F"]))
    _write(tmp_path, "clean.py", CLEAN)
    clean_manifest = snapshot_python_files(tmp_path)
    assert len(clean_manifest.entries) == 2
    assert attempt_outcome([fail]) == "INCOMPLETE"
    assert fail.status == "FAIL"


# --------------------------------------------------- fix / scope --


def test_peq_py_t12(tmp_path):
    """Safe fix then re-check is deterministic; double fix is stable."""
    path = _write(tmp_path, "m.py", BAD_FORMAT)
    assert _run(tmp_path, _policy("ruff-format")).status == "FAIL"
    ruff = shutil.which("ruff")
    assert ruff
    subprocess.run(
        [ruff, "format", str(path)], check=True, capture_output=True
    )
    once = path.read_bytes()
    subprocess.run(
        [ruff, "format", str(path)], check=True, capture_output=True
    )
    assert path.read_bytes() == once  # second fix is a no-op
    assert _run(tmp_path, _policy("ruff-format")).status == "PASS"


def test_peq_py_t13(tmp_path):
    """The snapshot inventory governs which files the policy sees."""
    _write(tmp_path, "a.py", CLEAN)
    _write(tmp_path, "b.py", F401)
    manifest = snapshot_python_files(tmp_path)
    assert {e.path for e in manifest.entries} == {"a.py", "b.py"}
    report = run_native_checks(
        manifest, _policy("ruff", select=["F401"]), tmp_path
    )
    assert {d.path for d in report.diagnostics} == {"b.py"}


def test_peq_py_t14(tmp_path):
    """An inventory over a missing/empty scope fails the guard."""
    with pytest.raises(CyranoError) as exc:
        snapshot_python_files(tmp_path / "nonexistent")
    assert exc.value.code == "BLOCKED"


def test_peq_py_t15(tmp_path):
    """Python work with an empty scope is BLOCKED at policy time."""
    with pytest.raises(CyranoError) as exc:
        resolve_quality_policy({"tool": "ruff", "scope": []})
    assert exc.value.code == "BLOCKED"


def test_peq_py_t16():
    """A path outside the governed scope is refused before run."""
    policy = _policy("ruff", scope=["src/**"])
    with pytest.raises(CyranoError) as exc:
        check_path_in_scope(policy, "../outside.py")
    assert exc.value.code == "PATH_POLICY_VIOLATION"
    check_path_in_scope(policy, "src/ok.py")


def test_peq_py_t17(tmp_path):
    """A tool that cannot run is an explicit blocker, not a miss."""
    _write(tmp_path, "m.py", CLEAN)
    policy = QualityPolicy(
        policy_id="x",
        tool="mypy",  # no adapter exists
        select=frozenset(),
        line_length=79,
        max_doc_length=None,
        scope_patterns=("*.py",),
    )
    manifest = snapshot_python_files(tmp_path)
    with pytest.raises(CyranoError) as exc:
        run_native_checks(manifest, policy, tmp_path)
    assert exc.value.code == "CAPABILITY_UNAVAILABLE"


def test_peq_py_t18(tmp_path):
    """A baseline bound to another snapshot is STALE_BASELINE."""
    _write(tmp_path, "m.py", F401)
    report = _run(tmp_path, _policy("ruff", select=["F401"]))
    decision = compare_diagnostic_multisets(
        report, report.diagnostics, "sha256:other-snapshot"
    )
    assert decision.decision == "STALE_BASELINE"


def test_peq_py_t19(tmp_path):
    """An old receipt cannot be reused for a changed report."""
    repo = ScopedRepository.create(tmp_path / "db", TARGET_DDL)
    sid = repo.register_scope("t", "u", "w")
    repo.create_stream(sid, "q", "quality")
    store = QualityReportStore(repo, sid, "q")
    report = RawCheckReport(
        "PASS", "ruff", (), 0, "raw1", "snap1"
    )
    first = store.submit(
        "r1", report,
        actor="runner", idempotency_key="k1",
        expected_revision=0, source_identity="src-a",
    )
    assert first.idempotent_replay is False
    changed = RawCheckReport(
        "FAIL", "ruff", (), 1, "raw2", "snap2"
    )
    with pytest.raises(CyranoError) as exc:
        store.submit(
            "r1", changed,
            actor="runner", idempotency_key="k1",
            expected_revision=1, source_identity="src-a",
        )
    assert exc.value.code == "IDEMPOTENCY_CONFLICT"
    repo.close()


def test_peq_py_t20_t21(tmp_path):
    """Identical content shares a digest; changed content differs."""
    _write(tmp_path, "a.py", CLEAN)
    m1 = snapshot_python_files(tmp_path)
    m2 = snapshot_python_files(tmp_path)
    assert m1.digest == m2.digest  # T21
    _write(tmp_path, "a.py", CLEAN + "\n")
    m3 = snapshot_python_files(tmp_path)
    assert m3.digest != m1.digest  # T20


# ------------------------------------------------------ permits --

_KEY = Ed25519PrivateKey.generate()
_SUBJECT = "sha256:" + "ab" * 32


def _permit(**kw) -> SignedPermit:
    defaults = dict(
        permit_id="p1", subject_digest=_SUBJECT,
        shown_digest="s", user_event_id="u1", scope_id="sc",
        purpose="execute", audience="cyrano", nonce="n",
        issued_at=0, expires_at=10_000,
    )
    defaults.update(kw)
    return issue_permit(_KEY, **defaults)


def test_peq_py_t22():
    """No permit is POLICY_VIOLATION, never an implicit pass."""
    with pytest.raises(CyranoError) as exc:
        require_run_permit(
            None, _KEY.public_key(),
            subject_digest=_SUBJECT, now=1,
            is_revoked=lambda _: False,
        )
    assert exc.value.code == "POLICY_VIOLATION"


def test_peq_py_t23(tmp_path):
    """A real noqa suppression is honored — no false positive."""
    _write(tmp_path, "m.py", SUPPRESSED)
    report = _run(tmp_path, _policy("ruff", select=["F401"]))
    assert report.status == "PASS"


def test_peq_py_t24():
    """A valid in-scope permit passes signature/expiry checks."""
    verify_permit(
        _permit(), _KEY.public_key(),
        purpose="execute", subject_digest=_SUBJECT, now=5,
        is_revoked=lambda _: False,
    )
    require_run_permit(
        _permit(), _KEY.public_key(),
        subject_digest=_SUBJECT, now=5,
        is_revoked=lambda _: False,
    )


def test_peq_py_t25():
    """An expired permit is denied."""
    with pytest.raises(CyranoError) as exc:
        require_run_permit(
            _permit(expires_at=1), _KEY.public_key(),
            subject_digest=_SUBJECT, now=5,
            is_revoked=lambda _: False,
        )
    assert exc.value.code == "PERMIT_EXPIRED"


def test_peq_py_t26_t27_t28(tmp_path):
    """Report store enforces trusted-source registration."""
    repo = ScopedRepository.create(tmp_path / "db", TARGET_DDL)
    sid = repo.register_scope("t", "u", "w")
    repo.create_stream(sid, "q", "quality")
    store = QualityReportStore(repo, sid, "q")
    report = RawCheckReport("PASS", "ruff", (), 0, "r", "s")
    store.submit(
        "r1", report, actor="a", idempotency_key="k",
        expected_revision=0, source_identity="trusted",
    )
    with pytest.raises(CyranoError) as exc:
        store.submit(
            "r1", report, actor="b", idempotency_key="k2",
            expected_revision=1, source_identity="impostor",
        )
    assert exc.value.code == "TRUST_MISMATCH"
    repo.close()


def test_peq_py_t29(tmp_path):
    """A policy that cannot resolve is a contract error, not a pass."""
    with pytest.raises(CyranoError) as exc:
        resolve_quality_policy({"tool": "eslint", "scope": ["*.py"]})
    assert exc.value.code == "POLICY_CONFIG_MISMATCH"


# ---------------------------------------------------- runner edge --


def test_peq_py_t30_t31(tmp_path):
    """A tool protocol error is ERROR_TOOL_PROTOCOL, not a violation."""
    _write(tmp_path, "m.py", CLEAN)
    report = _run(tmp_path, _policy("ruff", select=["BOGUS_RULE"]))
    assert report.status == "ERROR_TOOL_PROTOCOL"
    assert report.diagnostics == ()


def test_peq_py_t32(tmp_path):
    """A cancelled run returns CANCELLED; no PASS is fabricated."""
    _write(tmp_path, "m.py", CLEAN)
    report = _run(
        tmp_path, _policy("ruff"), cancel_flag=lambda: True
    )
    assert report.status == "CANCELLED"


def test_peq_py_t33(tmp_path):
    """Output beyond the limit is ERROR_OUTPUT_LIMIT, not truncated."""
    _write(tmp_path, "m.py", F401)
    report = _run(tmp_path, _policy("ruff"), output_limit=1)
    assert report.status == "ERROR_OUTPUT_LIMIT"


def test_peq_py_t34(tmp_path):
    """A lost runner is ERROR_RUNNER_LOST; no false resume result."""
    _write(tmp_path, "m.py", CLEAN)
    report = _run(tmp_path, _policy("ruff"), timeout_s=0.0001)
    assert report.status == "ERROR_RUNNER_LOST"


def test_peq_py_t35_t36_t37(tmp_path):
    """Idempotent replay, conflict, and CAS refusal on the ledger."""
    repo = ScopedRepository.create(tmp_path / "db", TARGET_DDL)
    sid = repo.register_scope("t", "u", "w")
    repo.create_stream(sid, "q", "quality")
    store = QualityReportStore(repo, sid, "q")
    report = RawCheckReport("PASS", "ruff", (), 0, "r", "s")
    first = store.submit(
        "r1", report, actor="a", idempotency_key="k",
        expected_revision=0, source_identity="src",
    )
    replay = store.submit(
        "r1", report, actor="a", idempotency_key="k",
        expected_revision=0, source_identity="src",
    )
    assert replay.idempotent_replay is True  # T35
    other = RawCheckReport("FAIL", "ruff", (), 1, "r2", "s2")
    with pytest.raises(CyranoError) as exc:
        store.submit(
            "r1", other, actor="a", idempotency_key="k",
            expected_revision=0, source_identity="src",
        )
    assert exc.value.code == "IDEMPOTENCY_CONFLICT"  # T36
    with pytest.raises(CyranoError) as exc2:
        store.submit(
            "r2", report, actor="a", idempotency_key="k9",
            expected_revision=99, source_identity="src",
        )
    assert exc2.value.code == "STALE_REVISION"  # T37
    repo.close()


def test_peq_py_t38(tmp_path):
    """A raw FAIL matching the baseline is PASS_WITH_BASELINE."""
    _write(tmp_path, "m.py", F401)
    report = _run(tmp_path, _policy("ruff", select=["F401"]))
    decision = compare_diagnostic_multisets(
        report, report.diagnostics, report.snapshot_digest
    )
    assert decision.decision == "PASS_WITH_BASELINE"
    assert report.status == "FAIL"  # raw result preserved


def test_peq_py_t39(tmp_path):
    """Equal counts but different diagnostics still FAIL."""
    _write(tmp_path, "m.py", F401)
    report = _run(tmp_path, _policy("ruff", select=["F401"]))
    baseline = (Diagnostic("m.py", 1, "E999", "different"),)
    decision = compare_diagnostic_multisets(
        report, baseline, report.snapshot_digest
    )
    assert decision.decision == "FAIL"


def test_peq_py_t40(tmp_path):
    """No baseline means no implicit pass — a FAIL stays FAIL."""
    _write(tmp_path, "m.py", F401)
    report = _run(tmp_path, _policy("ruff", select=["F401"]))
    decision = compare_diagnostic_multisets(report, None)
    assert decision.decision == "FAIL"


def test_peq_py_t41(tmp_path):
    """A snapshot-drifted baseline is STALE_BASELINE."""
    _write(tmp_path, "m.py", CLEAN)
    report = _run(tmp_path, _policy("ruff", select=["F401"]))
    decision = compare_diagnostic_multisets(
        report, (), "sha256:stale"
    )
    assert decision.decision == "STALE_BASELINE"


def test_peq_py_t42(tmp_path):
    """A whole-tree type check catches a regression in any file."""
    if shutil.which("ty") is None:
        pytest.skip("ty unavailable")
    _write(tmp_path, "good.py", CLEAN)
    _write(tmp_path, "bad.py", TYPE_ERR)
    report = _run(tmp_path, _policy("ty"))
    assert report.status == "FAIL"


def test_peq_py_t43(tmp_path):
    """An unsupported tool is an explicit blocker, never a pass."""
    _write(tmp_path, "m.py", CLEAN)
    policy = QualityPolicy(
        policy_id="x", tool="mypy", select=frozenset(),
        line_length=79, max_doc_length=None,
        scope_patterns=("*.py",),
    )
    manifest = snapshot_python_files(tmp_path)
    with pytest.raises(CyranoError) as exc:
        run_native_checks(manifest, policy, tmp_path)
    assert exc.value.code == "CAPABILITY_UNAVAILABLE"
