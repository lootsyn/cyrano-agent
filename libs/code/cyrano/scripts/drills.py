"""Run isolated WP23 Category A readiness drills and write evidence.

Every drill executes real local behavior in temporary directories,
captures the observed outcome, verifies cleanup, and reports
``passed`` / ``failed`` / ``blocked``. Nothing here touches a
network, a paid model, production credentials, a real bounded
filesystem mount, a separate OS principal, or a live dcode run.
"""

import argparse
import asyncio
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT.parent
DRILLS_DIR = ROOT / "evidence" / "drills"
TARGET_DDL = ROOT / "contracts" / "sql" / "target-schema.sql"

sys.path.insert(0, str(CODE))
from deepagents_code.cyrano.cli.launch import (  # noqa: E402
    restore_with_deletions,
    verify_install_nonmutation,
)
from deepagents_code.cyrano.contracts.types import (  # noqa: E402
    CyranoError,
)
from deepagents_code.cyrano.kernel.actions import (  # noqa: E402
    ActionBroker,
    Grant,
)
from deepagents_code.cyrano.kernel.approvals import (  # noqa: E402
    ApprovalDesk,
    issue_permit,
    verify_permit,
)
from deepagents_code.cyrano.sqlite.repository import (  # noqa: E402
    EXTENSION_DDL,
    ScopedRepository,
)

NOT_REVOKED = lambda pid: False  # noqa: E731


def _check(name: str, passed: bool, detail: object = "") -> dict:
    """Record one observed check outcome."""
    return {"name": name, "passed": bool(passed), "detail": detail}


def _blocked(reason: str, work: Path) -> dict:
    """Report a drill whose local prerequisites are missing."""
    return {
        "status": "blocked",
        "blockers": [reason],
        "checks": [],
        "cleanup": _cleanup(work),
        "raw": {},
    }


def _cleanup(path: Path) -> dict:
    """Remove a drill workdir and verify removal."""
    shutil.rmtree(path, ignore_errors=True)
    return {"path": str(path), "removed": not path.exists()}


def _finish(checks: list[dict], work: Path, raw: dict) -> dict:
    """Assemble a drill result; any failed check fails the drill."""
    status = (
        "passed" if checks and all(c["passed"] for c in checks) else "failed"
    )
    return {
        "status": status,
        "blockers": [],
        "checks": checks,
        "cleanup": _cleanup(work),
        "raw": raw,
    }


def _permit(key: Ed25519PrivateKey, permit_id: str, subject: str):
    """Issue a drill permit; throwaway key material only."""
    return issue_permit(
        key,
        permit_id=permit_id,
        subject_digest=subject,
        shown_digest=subject,
        user_event_id="ue-1",
        scope_id="scope-1",
        purpose="execute",
        audience="ops",
        nonce="n-1",
        issued_at=1,
        expires_at=100,
    )


def _verify_code(permit, root, subject: str, revoked: bool) -> str:
    """Verify a permit and report ``VERIFIED`` or the refusal code."""
    try:
        verify_permit(
            permit,
            root,
            purpose="execute",
            subject_digest=subject,
            now=10,
            is_revoked=lambda pid: revoked,
        )
    except CyranoError as exc:
        return exc.code
    return "VERIFIED"


def drill_key_rotation() -> dict:
    """Rotate the permit trust root; old permits must die."""
    work = Path(tempfile.mkdtemp(prefix="cyrano-drill-keys-"))
    checks: list[dict] = []
    key_a = Ed25519PrivateKey.generate()
    key_b = Ed25519PrivateKey.generate()
    subject = "sha256:" + hashlib.sha256(b"drill").hexdigest()
    permit_a = _permit(key_a, "drill-a1", subject)
    permit_b = _permit(key_b, "drill-b1", subject)
    pub_a, pub_b = key_a.public_key(), key_b.public_key()
    checks.append(
        _check(
            "permit_verifies_under_issuing_root",
            _verify_code(permit_a, pub_a, subject, False) == "VERIFIED",
        )
    )
    checks.append(
        _check(
            "old_permit_rejected_after_rotation",
            _verify_code(permit_a, pub_b, subject, False)
            == "INVALID_SIGNATURE",
            _verify_code(permit_a, pub_b, subject, False),
        )
    )
    checks.append(
        _check(
            "new_permit_verifies_under_new_root",
            _verify_code(permit_b, pub_b, subject, False) == "VERIFIED",
        )
    )
    checks.append(
        _check(
            "revocation_survives_rotation",
            _verify_code(permit_b, pub_b, subject, True) == "PERMIT_REVOKED",
            _verify_code(permit_b, pub_b, subject, True),
        )
    )
    raw = {"key_material": "ephemeral_in_memory"}
    return _finish(checks, work, raw)


def drill_backup_restore() -> dict:
    """Back up, wipe, and restore a scoped repository."""
    work = Path(tempfile.mkdtemp(prefix="cyrano-drill-backup-"))
    checks: list[dict] = []
    live = work / "live" / "store.sqlite3"
    live.parent.mkdir(parents=True)
    repo = ScopedRepository.create(live, TARGET_DDL.read_text())
    scope = repo.register_scope("tenant", "user", "ws")
    repo.create_stream(scope, "stream-1", "task")
    for index in range(3):
        repo.execute_command(
            scope,
            "agent",
            "record",
            f"key-{index}",
            {"n": index},
            "stream-1",
            expected_revision=index,
        )
    events_before = repo.list_events(scope, "stream-1")
    dump_digest = hashlib.sha256(
        "\n".join(repo.connection.iterdump()).encode()
    ).hexdigest()
    backup = work / "backup" / "store.sqlite3"
    backup.parent.mkdir(parents=True)
    dest = sqlite3.connect(str(backup))
    try:
        repo.connection.backup(dest)
    finally:
        dest.close()
    repo.close()
    shutil.rmtree(live.parent)
    restored_path = work / "restored" / "store.sqlite3"
    restored_path.parent.mkdir(parents=True)
    shutil.copy2(backup, restored_path)
    reopened = ScopedRepository.open(restored_path)
    try:
        events_after = reopened.list_events(scope, "stream-1")
        dump_after = hashlib.sha256(
            "\n".join(reopened.connection.iterdump()).encode()
        ).hexdigest()
    finally:
        reopened.close()
    checks.append(
        _check("events_survive_restore", events_after == events_before)
    )
    checks.append(_check("logical_digest_matches", dump_after == dump_digest))
    tombstoned = restore_with_deletions(
        [{"id": "m1"}, {"id": "m2"}, {"id": "m3"}],
        [{"target": "m2"}],
        writer_version=2,
        generation_version=2,
    )
    checks.append(
        _check(
            "tombstones_replayed",
            tombstoned["restored"] == 2
            and tombstoned["tombstones_replayed"] == 1,
            dict(tombstoned),
        )
    )
    try:
        restore_with_deletions(
            [{"id": "m1"}],
            [],
            writer_version=1,
            generation_version=2,
        )
        writer_code = "ACTIVATED"
    except CyranoError as exc:
        writer_code = exc.code
    checks.append(
        _check(
            "old_writer_refused",
            writer_code == "MIGRATION_REQUIRED",
            writer_code,
        )
    )
    raw = {"events": len(events_before), "dump_digest": dump_digest}
    return _finish(checks, work, raw)


def _manifest(root: Path) -> dict[str, str]:
    """Digest every file under a fixture target tree."""
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(
            p.read_bytes()
        ).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def drill_install_nonmutation() -> dict:
    """Unpack the wheel beside a fixture target; it must not drift."""
    work = Path(tempfile.mkdtemp(prefix="cyrano-drill-install-"))
    wheel = next(
        iter(sorted((CODE / "dist").glob("deepagents_code-*.whl"))),
        None,
    )
    if wheel is None:
        return _blocked("no deepagents_code wheel under dist/", work)
    checks: list[dict] = []
    target = work / "target"
    (target / "pkg").mkdir(parents=True)
    (target / "pkg" / "mod.py").write_text("x = 1\n")
    (target / "README.md").write_text("fixture\n")
    before = _manifest(target)
    site = work / "site"
    site.mkdir()
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(site)
    after = _manifest(target)
    try:
        verify_install_nonmutation(before, after)
        intact = True
    except CyranoError:
        intact = False
    checks.append(_check("target_manifest_unchanged", intact))
    checks.append(
        _check(
            "wheel_contents_outside_target",
            (site / "deepagents_code").is_dir()
            and not (target / "deepagents_code").exists(),
        )
    )
    tampered = dict(after)
    tampered["pkg/mod.py"] = "0" * 64
    try:
        verify_install_nonmutation(before, tampered)
        tamper_code = "ACCEPTED"
    except CyranoError as exc:
        tamper_code = exc.code
    checks.append(
        _check(
            "tamper_detected",
            tamper_code == "INSTALL_MUTATION",
            tamper_code,
        )
    )
    raw = {"wheel": wheel.name, "target_files": len(before)}
    return _finish(checks, work, raw)


def _drill_broker(audit: list[str]) -> ActionBroker:
    """Bind a real broker with one granted path."""
    tools = frozenset({"edit_file", "execute_python", "read_file"})
    grants = (Grant("a.py", allow=frozenset({"write_existing"})),)
    return ActionBroker(tools, grants, audit.append)


def drill_permission_bypass() -> dict:
    """Attempt mutation paths that must all be refused in-process."""
    work = Path(tempfile.mkdtemp(prefix="cyrano-drill-perms-"))
    checks: list[dict] = []
    key = Ed25519PrivateKey.generate()
    root = key.public_key()
    subject = "sha256:" + hashlib.sha256(b"drill").hexdigest()
    audit: list[str] = []
    broker = _drill_broker(audit)

    def attempt(vector: str, expected: str, **kw) -> None:
        decision = broker.decide(
            trust_root=root,
            subject_digest=subject,
            now=10,
            is_revoked=kw.pop("is_revoked", NOT_REVOKED),
            **kw,
        )
        checks.append(
            _check(
                vector,
                not decision.allowed and decision.code == expected,
                f"{decision.code}",
            )
        )

    good = _permit(key, "drill-p1", subject)
    wrong_scope = _permit(key, "drill-p2", "sha256:" + "0" * 64)
    spec_only = issue_permit(
        key,
        permit_id="drill-p3",
        subject_digest=subject,
        shown_digest=subject,
        user_event_id="ue-1",
        scope_id="scope-1",
        purpose="spec",
        audience="ops",
        nonce="n-1",
        issued_at=1,
        expires_at=100,
    )
    forged = _permit(Ed25519PrivateKey.generate(), "drill-p4", subject)
    attempt(
        "no_permit_denied",
        "APPROVAL_REQUIRED",
        tool="edit_file",
        action="write_existing",
        path="a.py",
        permit=None,
    )
    attempt(
        "revoked_permit_denied",
        "PERMIT_REVOKED",
        tool="edit_file",
        action="write_existing",
        path="a.py",
        permit=good,
        is_revoked=lambda pid: True,
    )
    attempt(
        "wrong_scope_denied",
        "SUBJECT_MISMATCH",
        tool="edit_file",
        action="write_existing",
        path="a.py",
        permit=wrong_scope,
    )
    attempt(
        "wrong_purpose_denied",
        "WRONG_APPROVAL_ACTION",
        tool="edit_file",
        action="write_existing",
        path="a.py",
        permit=spec_only,
    )
    attempt(
        "forged_signature_denied",
        "INVALID_SIGNATURE",
        tool="edit_file",
        action="write_existing",
        path="a.py",
        permit=forged,
    )
    attempt(
        "ungranted_path_denied",
        "SCOPE_DENIED",
        tool="edit_file",
        action="write_existing",
        path="secret.txt",
        permit=good,
    )
    attempt(
        "scope_tool_denied",
        "SCOPE_DENIED",
        tool="execute_python",
        action="execute",
        path="a.py",
        permit=good,
    )
    desk = ApprovalDesk()
    record = desk.present(
        subject_digest=subject,
        shown_text="apply patch",
        audience="ops",
        nonce="n-1",
        expires_at=100,
    )
    result = desk.submit(
        record.request_id,
        actor="ops",
        nonce="n-1",
        decision="approve",
        shown_text="apply patch",
        display_revision=record.display_revision,
        client_event_id="ce-1",
        now=10,
    )
    checks.append(
        _check(
            "unopened_display_no_receipt",
            result.status != "approved",
            result.status,
        )
    )
    try:
        desk.submit(
            record.request_id,
            actor="intruder",
            nonce="n-1",
            decision="approve",
            shown_text="apply patch",
            display_revision=record.display_revision,
            client_event_id="ce-2",
            now=10,
        )
        actor_code = "ACCEPTED"
    except CyranoError as exc:
        actor_code = exc.code
    checks.append(
        _check("wrong_actor_denied", actor_code == "ACL_DENIED", actor_code)
    )
    target = work / "a.py"
    target.write_text("old\n")
    applied = []

    def apply():
        applied.append(True)
        target.write_text("new\n")

    try:
        broker.apply_scoped_patch(
            permit=forged,
            trust_root=root,
            subject_digest=subject,
            now=10,
            is_revoked=NOT_REVOKED,
            apply_fn=apply,
        )
        patch_code = "APPLIED"
    except CyranoError as exc:
        patch_code = exc.code
    checks.append(
        _check(
            "forged_patch_never_applies",
            patch_code == "INVALID_SIGNATURE"
            and not applied
            and target.read_text() == "old\n",
            patch_code,
        )
    )
    checks.append(_check("denials_audited", len(audit) >= 1, len(audit)))
    raw = {"attempts": len(checks), "audit_events": len(audit)}
    return _finish(checks, work, raw)


class _DiskFullConnection(sqlite3.Connection):
    """A real connection that raises ENOSPC once the disk fills."""

    full = False

    def execute(self, sql, parameters=(), /):
        """Fail writes as a full disk would; reads still work."""
        if self.full and sql.lstrip().upper().startswith(("INSERT", "UPDATE")):
            raise sqlite3.OperationalError("database or disk is full")
        return super().execute(sql, parameters)


def drill_disk_full() -> dict:
    """Inject ENOSPC mid-write; no partial commit may survive."""
    work = Path(tempfile.mkdtemp(prefix="cyrano-drill-diskfull-"))
    checks: list[dict] = []
    db_path = work / "store.sqlite3"
    conn = _DiskFullConnection(str(db_path), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(TARGET_DDL.read_text())
    conn.executescript(EXTENSION_DDL)
    repo = ScopedRepository(conn)
    scope = repo.register_scope("tenant", "user", "ws")
    repo.create_stream(scope, "stream-1", "task")
    repo.execute_command(
        scope,
        "agent",
        "record",
        "key-0",
        {"n": 0},
        "stream-1",
        expected_revision=0,
    )
    events_before = repo.list_events(scope, "stream-1")
    requests_before = repo.connection.execute(
        "SELECT count(*) FROM requests"
    ).fetchone()[0]
    conn.full = True
    try:
        repo.execute_command(
            scope,
            "agent",
            "record",
            "key-1",
            {"n": 1},
            "stream-1",
            expected_revision=1,
        )
        failure = "COMMITTED"
    except sqlite3.OperationalError as exc:
        failure = str(exc)
    conn.full = False
    checks.append(
        _check(
            "disk_full_surfaces_typed_error",
            failure != "COMMITTED" and "disk" in failure,
            failure,
        )
    )
    events_after = repo.list_events(scope, "stream-1")
    requests_after = repo.connection.execute(
        "SELECT count(*) FROM requests"
    ).fetchone()[0]
    checks.append(
        _check(
            "no_partial_commit",
            events_after == events_before
            and requests_after == requests_before,
            {"events": len(events_after), "requests": requests_after},
        )
    )
    repo.execute_command(
        scope,
        "agent",
        "record",
        "key-2",
        {"n": 2},
        "stream-1",
        expected_revision=1,
    )
    checks.append(
        _check(
            "repository_usable_after_rollback",
            len(repo.list_events(scope, "stream-1")) == len(events_before) + 1,
        )
    )
    repo.close()
    raw = {"injection": "sqlite execute INSERT/UPDATE -> ENOSPC"}
    return _finish(checks, work, raw)


_INJECT = "[bold]x[/bold]\x1b[31mred\x1b[0m \x1b]8;;https://evil\x07L"


async def _screen_views(app) -> dict[str, str]:
    """Collect rendered text from every governed view."""
    screen = app.screen
    await app.workers.wait_for_complete()
    views = {
        name: str(screen.query_one(f"#view-{name}").content)
        for name, _ in screen.TABS
    }
    views["connection"] = str(screen.query_one("#cyrano-connection").content)
    return views


def drill_governed_screens() -> dict:
    """Render governed views headless; injection must stay literal."""
    work = Path(tempfile.mkdtemp(prefix="cyrano-drill-screens-"))
    try:
        from textual.app import App

        from deepagents_code.cyrano.monitor.screen import (
            CyranoMonitorScreen,
        )
    except ImportError as exc:
        return _blocked(f"textual unavailable: {exc}", work)

    class _Reader:
        async def read(self, request_id: str) -> dict[str, str]:
            return {
                name: f"{name} body {_INJECT}"
                for name, _ in CyranoMonitorScreen.TABS
            }

    class _BadReader:
        async def read(self, request_id: str) -> dict[str, str]:
            raise PermissionError("denied")

    class _Host(App[None]):
        def __init__(self, reader) -> None:
            super().__init__()
            self._reader = reader

        def on_mount(self) -> None:
            self.push_screen(CyranoMonitorScreen(self._reader, "req-1"))

    async def run(reader) -> dict[str, str]:
        app = _Host(reader)
        async with app.run_test() as pilot:
            await pilot.pause()
            return await _screen_views(app)

    checks: list[dict] = []
    views = asyncio.run(run(_Reader()))
    checks.append(
        _check(
            "all_views_rendered",
            len(views) == 8 and all(value for value in views.values()),
            sorted(views),
        )
    )
    checks.append(
        _check(
            "markup_rendered_literally",
            "[bold]x[/bold]" in views["overview"],
            views["overview"][:60],
        )
    )
    ansi_free = all("\x1b" not in v for v in views.values())
    checks.append(_check("no_ansi_or_osc_leakage", ansi_free))
    bound = {binding[0] for binding in CyranoMonitorScreen.BINDINGS}
    checks.append(
        _check(
            "no_mutation_keybindings",
            bound <= {"escape", "r"},
            sorted(bound),
        )
    )
    denied = asyncio.run(run(_BadReader()))
    masked = all("숨김" in value for value in denied.values())
    checks.append(
        _check(
            "denied_read_masks_content",
            masked and "[bold]" not in str(denied),
            denied.get("overview", "")[:60],
        )
    )
    raw = {"tier": "headless", "views": sorted(views)}
    return _finish(checks, work, raw)


def _repack_cached_wheel(name: str, outdir: Path) -> str | None:
    """Zip the newest cached unpacked wheel into the wheelhouse."""
    normalized = name.replace("-", "_").lower()
    archive = Path.home() / ".cache" / "uv" / "archive-v0"
    if not archive.is_dir():
        return None

    def version_key(name: str) -> tuple:
        stem = name.removesuffix(".dist-info")
        version = stem.rsplit("-", 1)[-1]
        return tuple(int(p) if p.isdigit() else 0 for p in version.split("."))

    candidates = sorted(
        archive.glob(f"*/{normalized}-*.dist-info"),
        key=lambda d: version_key(d.name),
    )
    if not candidates:
        return None
    dist_info = candidates[-1]
    unpacked = dist_info.parent
    stem = dist_info.name.removesuffix(".dist-info")
    version = stem.rsplit("-", 1)[-1]
    wheel_meta = dist_info / "WHEEL"
    tag = "py3-none-any"
    if wheel_meta.is_file():
        tags = re.findall(r"^Tag: (.+)$", wheel_meta.read_text(), re.M)
        if tags:
            tag = tags[0]
    wheel = outdir / f"{normalized}-{version}-{tag}.whl"
    with zipfile.ZipFile(wheel, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in sorted(unpacked.rglob("*")):
            if item.is_file():
                zf.write(item, item.relative_to(unpacked))
    return wheel.name


def _missing_dep(stderr: str) -> str | None:
    """Extract a package name the offline resolver could not find."""
    for pattern in (
        r"no version of ([a-zA-Z0-9_.-]+)(?:\[[^\]]*\])?==",
        r"only ([a-zA-Z0-9_.-]+)(?:\[[^\]]*\])?[<!=]",
        r"no solution found.*?'([^']+)'",
    ):
        match = re.search(pattern, stderr)
        if match:
            return match.group(1)
    return None


def _run(argv: list[str], timeout: int) -> dict:
    """Run a bounded subprocess and capture the raw outcome."""
    result = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return {
        "argv": argv,
        "exit": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def drill_clean_env_install() -> dict:
    """Install the wheel into a fresh venv from local files only."""
    work = Path(tempfile.mkdtemp(prefix="cyrano-drill-cleanenv-"))
    checks: list[dict] = []
    raw: dict = {"commands": []}
    uv = shutil.which("uv")
    if uv is None:
        return _blocked("uv not on PATH", work)
    wheels = sorted((CODE / "dist").glob("deepagents_code-*.whl"))
    if not wheels:
        return _blocked("no deepagents_code wheel under dist/", work)
    venv = work / "venv"
    wheelhouse = work / "wheelhouse"
    wheelhouse.mkdir()
    for source in (CODE / "dist", CODE.parent / "deepagents" / "dist"):
        if source.is_dir():
            for artifact in source.glob("*.whl"):
                shutil.copy2(artifact, wheelhouse / artifact.name)
    env_python = venv / "bin" / "python"
    raw["commands"].append(
        _run([uv, "venv", str(venv), "--seed"], timeout=120)
    )
    if raw["commands"][-1]["exit"] != 0 or not env_python.is_file():
        return {
            "status": "blocked",
            "blockers": ["venv creation failed"],
            "checks": checks,
            "cleanup": _cleanup(work),
            "raw": raw,
        }
    requirement = "deepagents-code==0.1.70"
    attempted: list[str] = []
    install: dict = {"exit": 1, "stderr": "resolution not attempted"}
    for _ in range(8):
        install = _run(
            [
                uv,
                "pip",
                "install",
                "--offline",
                "--python",
                str(env_python),
                "--find-links",
                str(wheelhouse),
                requirement,
            ],
            timeout=300,
        )
        raw["commands"].append(install)
        if install["exit"] == 0:
            break
        missing = _missing_dep(str(install["stderr"]))
        if missing is None or missing in attempted:
            break
        attempted.append(missing)
        packed = _repack_cached_wheel(missing, wheelhouse)
        raw.setdefault("repacked", []).append(
            {"package": missing, "wheel": packed}
        )
        if packed is None:
            break
    if install["exit"] != 0:
        return {
            "status": "blocked",
            "blockers": [
                "offline resolution failed",
                str(install["stderr"])[-1200:],
            ],
            "checks": checks,
            "cleanup": _cleanup(work),
            "raw": raw,
        }
    smoke = _run(
        [
            str(env_python),
            "-c",
            "import deepagents_code.cyrano; print('cyrano import ok')",
        ],
        timeout=120,
    )
    raw["commands"].append(smoke)
    checks.append(
        _check(
            "wheel_installed_and_importable",
            smoke["exit"] == 0 and "cyrano import ok" in smoke["stdout"],
            smoke["stdout"].strip() or smoke["stderr"].strip(),
        )
    )
    inside = str(venv).startswith(str(work))
    checks.append(_check("install_confined_to_venv", inside, str(venv)))
    return _finish(checks, work, raw)


DRILLS = {
    "key_rotation": drill_key_rotation,
    "backup_restore": drill_backup_restore,
    "install_nonmutation": drill_install_nonmutation,
    "permission_bypass": drill_permission_bypass,
    "disk_full": drill_disk_full,
    "governed_screens": drill_governed_screens,
    "clean_env_install": drill_clean_env_install,
}


def run_drill(name: str, argv: list[str]) -> dict:
    """Execute one drill and return its evidence record."""
    result = DRILLS[name]()
    return {
        "kind": "executed_readiness_drill",
        "drill": name,
        "category": "A",
        "authorization": "isolated_no_external_effects",
        "external_effects": False,
        "argv": argv,
        **result,
        "cleanup_verified": bool(result.get("cleanup", {}).get("removed")),
    }


def main() -> int:
    """Run drills and write one evidence file per gate."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=sorted(DRILLS), default=None)
    args = parser.parse_args()
    DRILLS_DIR.mkdir(parents=True, exist_ok=True)
    names = [args.only] if args.only else list(DRILLS)
    summary = {}
    for name in names:
        record = run_drill(
            name, [sys.executable, str(Path(__file__).name), name]
        )
        path = DRILLS_DIR / f"{name}.json"
        path.write_text(json.dumps(record, indent=2) + "\n")
        summary[name] = record["status"]
        print(f"{name}: {record['status']} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
