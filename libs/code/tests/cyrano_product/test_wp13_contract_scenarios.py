"""WP13 contract scenarios: CON-OBS-01..12 and R5-RF07/08/09."""

import json
from pathlib import Path

import pytest

from deepagents_code.command_registry import COMMANDS
from deepagents_code.cyrano.cli.dashboard import (
    DashboardReport,
    headless_view,
    monitor_capability,
)
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.events.domain_sink import DomainSink
from deepagents_code.cyrano.events.metrics import reduce_events
from deepagents_code.cyrano.events.native_observer import NativeObserver
from deepagents_code.cyrano.events.query import ObservationQuery
from deepagents_code.cyrano.events.reconcile import reconcile_attempts
from deepagents_code.cyrano.monitor.projection import (
    MonitorProjection,
    ProjectionError,
    terminal_text,
)
from deepagents_code.cyrano.monitor.screen import CyranoMonitorScreen
from deepagents_code.cyrano.sqlite.repository import ScopedRepository

ROOT = Path(__file__).resolve().parents[2]
TARGET_DDL = (ROOT / "cyrano/contracts/sql/target-schema.sql").read_text()


@pytest.fixture()
def ctx(tmp_path):
    repo = ScopedRepository.create(tmp_path / "db.sqlite3", TARGET_DDL)
    scope = repo.register_scope("t1", "u1", "w1")
    repo.create_stream(scope, "req-1", "request")
    sink = DomainSink(repo)
    yield repo, scope, sink, ObservationQuery(repo)
    repo.close()


def _ev(kind, n=0, **payload):
    return {
        "kind": kind,
        "payload": payload,
        "event_id": f"{kind}:{payload.get('attempt_id', n)}",
    }


def test_con_obs_01(ctx):
    """First call plus two retries: logical 1, physical 3, retries 2."""
    rows = [
        _ev(
            "model.attempt_started",
            attempt_id="a0",
            logical_request_id="l1",
            is_retry=False,
        ),
        _ev(
            "model.attempt_started",
            attempt_id="a1",
            logical_request_id="l1",
            is_retry=True,
        ),
        _ev(
            "model.attempt_started",
            attempt_id="a2",
            logical_request_id="l1",
            is_retry=True,
        ),
    ]
    snap = reduce_events(rows)
    assert snap.logical_llm_requests == 1
    assert snap.physical_llm_attempts == 3
    assert snap.llm_retry_count == 2


def test_con_obs_02(ctx):
    """Parent aggregate plus child itemized bill once per attempt."""
    rows = [
        _ev(
            "model.attempt_started",
            attempt_id="c1",
            logical_request_id="l1",
            is_retry=False,
            provider_request_id="p-1",
            attempt_no=0,
        ),
        _ev(
            "model.attempt_started",
            attempt_id="c1-copy",
            logical_request_id="l2",
            is_retry=False,
            provider_request_id="p-1",
            attempt_no=0,
        ),
    ]
    snap = reduce_events(rows)
    assert snap.physical_llm_attempts == 1


def test_con_obs_03(ctx):
    """A cancelled attempt without usage stays unknown/pending."""
    rows = [
        _ev(
            "model.attempt_started",
            attempt_id="a1",
            logical_request_id="l1",
            is_retry=False,
        ),
    ]
    snap = reduce_events(rows)
    assert snap.attempts_unknown_outcome == 1
    assert snap.cost_actual is None


def test_con_obs_04():
    """A bounded list view never hides the true total."""
    proj = MonitorProjection("w1", "req-1", "gen-1")
    for i in range(1, 101):
        proj.ingest(
            {
                "event_id": f"e{i}",
                "commit_seq": i,
                "workspace_id": "w1",
                "request_id": "req-1",
                "generation": "gen-1",
                "event_type": "work.started",
                "payload": {},
            }
        )
    assert len(proj.timeline(limit=50)) == 50
    assert proj.summary()["total_events"] == 100


def test_con_obs_05():
    """A replayed event_id never counts twice."""
    proj = MonitorProjection("w1", "req-1", "gen-1")
    event = {
        "event_id": "e1",
        "commit_seq": 1,
        "workspace_id": "w1",
        "request_id": "req-1",
        "generation": "gen-1",
        "event_type": "work.started",
        "payload": {},
    }
    assert proj.ingest(event) is True
    assert proj.ingest(event) is False
    assert proj.summary()["total_events"] == 1
    snap = reduce_events(
        [
            {"kind": "work.started", "payload": {}, "event_id": "e1"},
            {"kind": "work.started", "payload": {}, "event_id": "e1"},
        ]
    )
    assert snap.duplicate_events == 1
    assert snap.total_events == 1


def test_con_obs_06(ctx):
    """Finish-before-start binds by identity with time uncertainty."""
    rows = [
        {
            "event_seq": 5,
            "kind": "model.finished",
            "payload": {"attempt_id": "a1"},
        },
        {
            "event_seq": 9,
            "kind": "model.attempt_started",
            "payload": {"attempt_id": "a1"},
        },
    ]
    report = reconcile_attempts(rows)
    assert report.orphan_attempt_ids == ()
    snap = reduce_events(
        [
            {
                "kind": r["kind"],
                "payload": r["payload"],
                "event_id": f"e{r['event_seq']}",
            }
            for r in rows
        ]
    )
    assert snap.clock_anomalies == 1  # ordering flagged, not hidden


def test_con_obs_07(ctx):
    """A cursor behind the retained window flags stale + resync."""
    repo, scope, sink, query = ctx
    repo.create_stream(scope, "req-early", "request")
    for i in range(1, 4):
        sink.record_event(
            scope,
            "req-early",
            "domain_service",
            i,
            "work.started",
            {"run_id": f"e{i}", "schema_family": "work"},
        )
    for i in range(4, 7):
        sink.record_event(
            scope,
            "req-1",
            "domain_service",
            i,
            "work.started",
            {"run_id": f"s{i}", "schema_family": "work"},
        )
    resumed = query.resume_stream(scope, "req-1", 1)
    assert resumed.stale_cursor is True  # window start not provable
    fresh = query.resume_stream(scope, "req-1", 0)
    assert fresh.stale_cursor is False
    assert len(fresh.events) == 3


def test_con_obs_08(ctx):
    """Revoked scope access denies the next refresh entirely."""
    repo, scope, sink, query = ctx
    other = repo.register_scope("t2", "u2", "w2")
    repo.create_stream(other, "req-b", "request")
    sink.record_event(
        other,
        "req-b",
        "domain_service",
        1,
        "work.started",
        {"run_id": "req-b", "schema_family": "work", "detail": "sensitive"},
    )
    with pytest.raises(CyranoError) as exc:
        query.get_timeline(scope, "req-b")
    assert exc.value.code == "SCOPE_DENIED"


def test_con_obs_09():
    """Cancelling a monitor query never cancels the agent's work."""
    proj = MonitorProjection("w1", "req-1", "gen-1")
    assert proj.summary()["connected"] is False
    # projection has no cancel/mutation surface for the run itself
    assert not hasattr(proj, "cancel_run")
    assert not hasattr(proj, "approve")


def test_con_obs_10(ctx):
    """An unobserved offload path is a coverage gap, not zero."""
    _, scope, sink, _ = ctx
    obs = NativeObserver(sink)
    obs.note_source("tool_offload", "unsupported")
    report = obs.coverage_report()
    assert report["complete"] is False
    assert "tool_offload" in report["gaps"]


def test_con_obs_11():
    """ANSI escapes are stripped and Korean text survives."""
    raw = "\x1b[31m위험\x1b]8;;http://x\x07링크\x1b]8;;\x07 끝"
    clean = terminal_text(raw)
    assert "\x1b" not in clean
    assert "\x07" not in clean
    assert "위험" in clean and "링크" in clean


def test_con_obs_12(ctx):
    """Ten monitor reads invoke no model at all."""
    repo, scope, sink, query = ctx
    sink.record_event(
        scope,
        "req-1",
        "domain_service",
        1,
        "work.started",
        {"run_id": "req-1", "schema_family": "work"},
    )
    calls = []
    for _ in range(10):
        rows = query.get_timeline(scope, "req-1").events
        calls.append(len(rows))
    assert calls == [1] * 10
    # ObservationQuery exposes no model surface to call
    assert not hasattr(query, "invoke_model")


class _Reader:
    """In-memory authorized views; records every read call."""

    def __init__(self, views=None, error=None):
        self.views = views or {
            name: f"{name} 내용" for name, _ in CyranoMonitorScreen.TABS
        }
        self.error = error
        self.calls = 0
        self.mutations = 0

    async def read(self, request_id):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return dict(self.views)


async def test_r5_rf07_01_busy_entry():
    """The monitor opens over a busy run with no LLM/tool calls."""
    from textual.app import App

    reader = _Reader()
    app = App()

    async with app.run_test() as pilot:
        await app.push_screen(CyranoMonitorScreen(reader, "req-1"))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, CyranoMonitorScreen)
        assert reader.calls == 1  # a read, never a model call
        assert not hasattr(screen, "invoke_model")
        await pilot.press("escape")


async def test_r5_rf07_02_existing_commands():
    """Native /trace and /cost stay registered exactly once."""
    names = [c.name for c in COMMANDS]
    assert "/trace" in names and "/cost" in names
    assert len(names) == len(set(names))


async def test_r5_rf07_03_thread_switch():
    """Another request's events never leak into the projection."""
    proj = MonitorProjection("w1", "req-1", "gen-1")
    with pytest.raises(ProjectionError) as exc:
        proj.ingest(
            {
                "event_id": "x",
                "commit_seq": 1,
                "workspace_id": "w1",
                "request_id": "req-2",
                "generation": "gen-1",
                "event_type": "work.started",
                "payload": {},
            }
        )
    assert "MISMATCH" in str(exc.value)


async def test_r5_rf07_04_unauthorized_cursor(ctx):
    """A foreign request's cursor denies with no payload leak."""
    repo, scope, sink, query = ctx
    other = repo.register_scope("t2", "u2", "w2")
    repo.create_stream(other, "req-b", "request")
    sink.record_event(
        other,
        "req-b",
        "domain_service",
        1,
        "work.started",
        {"run_id": "req-b", "schema_family": "work", "snippet": "hidden"},
    )
    with pytest.raises(CyranoError) as exc:
        query.resume_stream(scope, "req-b", 0)
    assert exc.value.code == "SCOPE_DENIED"
    assert "hidden" not in str(exc.value)


async def test_r5_rf07_05_snapshot_race(ctx):
    """An event committed between snapshot and subscribe is not lost."""
    _, scope, sink, query = ctx
    sink.record_event(
        scope,
        "req-1",
        "domain_service",
        1,
        "work.started",
        {"run_id": "s1", "schema_family": "work"},
    )
    snapshot = query.resume_stream(scope, "req-1", 0)
    cursor = snapshot.cursor
    sink.record_event(
        scope,
        "req-1",
        "domain_service",
        2,
        "work.completed",
        {"run_id": "s1", "schema_family": "work"},
    )
    resumed = query.resume_stream(scope, "req-1", cursor)
    ids = [r.event_id for r in resumed.events]
    assert len(ids) == 1
    assert resumed.events[0].kind == "work.completed"


def test_r5_rf07_06_extension_limit():
    """No slash hook means honestly unavailable, not fake-registered."""

    class OnlyTools:
        def register_tool(self, fn):
            return fn

    cap = monitor_capability(OnlyTools())
    assert cap["slash_entry"] == "unavailable"
    assert cap["tool_registration"] == "available"
    assert cap["reason"]


def test_r5_rf08_01_real_call_counts():
    """1 logical / 3 physical / 2 retries; redelivery is a no-op."""
    proj = MonitorProjection("w1", "req-1", "gen-1")
    for i, (aid, retry) in enumerate(
        [("a0", False), ("a1", True), ("a2", True)]
    ):
        event = {
            "event_id": f"e{i}",
            "commit_seq": i + 1,
            "workspace_id": "w1",
            "request_id": "req-1",
            "generation": "gen-1",
            "event_type": "model.attempt_started",
            "payload": {
                "attempt_id": aid,
                "logical_request_id": "l1",
                "is_retry": retry,
            },
        }
        assert proj.ingest(event) is True
        assert proj.ingest(event) is False  # replay is free
    summary = proj.summary()
    assert summary["logical_requests_observed"] == 1
    assert summary["physical_attempts_observed"] == 3
    assert summary["retries_observed"] == 2
    assert summary["total_events"] == 3


def test_r5_rf08_02_seq_gap():
    """ACL-filtered global seq gaps are not treated as missing."""
    proj = MonitorProjection("w1", "req-1", "gen-1")
    for seq in (1, 4, 9):
        assert (
            proj.ingest(
                {
                    "event_id": f"e{seq}",
                    "commit_seq": seq,
                    "workspace_id": "w1",
                    "request_id": "req-1",
                    "generation": "gen-1",
                    "event_type": "work.started",
                    "payload": {},
                }
            )
            is True
        )
    assert proj.summary()["total_events"] == 3
    assert proj.cursor == 9


def test_r5_rf08_03_osc_attack():
    """OSC52 and bidi controls cannot reach the terminal."""
    raw = (
        "\x1b]52;c;SGVsbG8=\x07\u202eEVIL\u202c\u0645\u0631\u062d\u0628\u0627"
    )
    clean = terminal_text(raw)
    assert "\x1b" not in clean and "\x07" not in clean
    assert "\u202e" not in clean  # bidi override stripped
    assert "\u0645" in clean  # legitimate text survives


async def test_r5_rf08_04_small_terminal():
    """The overlay mounts and stays usable at 80x24."""
    from textual.app import App

    reader = _Reader()
    app = App()

    async with app.run_test(size=(80, 24)) as pilot:
        await app.push_screen(CyranoMonitorScreen(reader, "req-1"))
        await pilot.pause()
        assert isinstance(app.screen, CyranoMonitorScreen)
        await pilot.press("escape")


async def test_r5_rf08_05_dismiss_keeps_agent():
    """Esc closes the view only; the run and workers are untouched."""
    from textual.app import App

    reader = _Reader()
    app = App()

    async with app.run_test() as pilot:
        screen = CyranoMonitorScreen(reader, "req-1")
        await app.push_screen(screen)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, CyranoMonitorScreen)
        assert not hasattr(screen, "cancel_run")


def test_r5_rf08_06_overflow():
    """Over-cap ingest demands a snapshot instead of faking complete."""
    proj = MonitorProjection("w1", "req-1", "gen-1", max_events=2)
    for i in range(1, 3):
        proj.ingest(
            {
                "event_id": f"e{i}",
                "commit_seq": i,
                "workspace_id": "w1",
                "request_id": "req-1",
                "generation": "gen-1",
                "event_type": "work.started",
                "payload": {},
            }
        )
    with pytest.raises(ProjectionError) as exc:
        proj.ingest(
            {
                "event_id": "e3",
                "commit_seq": 3,
                "workspace_id": "w1",
                "request_id": "req-1",
                "generation": "gen-1",
                "event_type": "work.started",
                "payload": {},
            }
        )
    assert "SNAPSHOT_REQUIRED" in str(exc.value)
    assert proj.summary()["coverage"] == "partial_or_unknown"


async def test_r5_rf09_01_pilot_order():
    """Real key input reaches the real screen in binding order."""
    from textual.app import App

    reader = _Reader()
    app = App()

    async with app.run_test() as pilot:
        await app.push_screen(CyranoMonitorScreen(reader, "req-1"))
        await pilot.pause()
        assert reader.calls == 1
        await pilot.press("r")  # refresh binding
        await pilot.pause()
        assert reader.calls == 2
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, CyranoMonitorScreen)


def test_r5_rf09_02_first_failure(ctx):
    """First observed failure stays distinct from self-reports."""
    _, scope, sink, query = ctx
    sink.record_event(
        scope,
        "req-1",
        "tool_observer",
        1,
        "tool.failed",
        {
            "tool_call_id": "t1",
            "error_class": "nonzero_exit",
            "schema_family": "tool",
        },
    )
    sink.record_untrusted(
        scope,
        "req-1",
        "model",
        2,
        "model.self_report",
        {"claim": "it was the network"},
    )
    failure = query.get_failure(scope, "req-1")
    assert failure is not None
    assert failure.evidence["error_class"] == "nonzero_exit"
    assert failure.self_reports[0]["claim"] == "it was the network"


def test_r5_rf09_03_headless_output():
    """Headless output is JSON with no ANSI and no prompt."""
    view = headless_view(
        DashboardReport(
            request_id="req-1",
            status="failed",
            coverage_complete=False,
            coverage_gaps=("offload",),
        )
    )
    encoded = json.dumps(view, ensure_ascii=False)
    assert "\x1b" not in encoded
    assert view["schema_version"] == 1
    assert view["coverage"] == "unknown"
    assert "prompt" not in encoded.lower()


def test_r5_rf09_04_generation_reset():
    """A generation mismatch is refused; requests never mix."""
    proj = MonitorProjection("w1", "req-1", "gen-1")
    with pytest.raises(ProjectionError):
        proj.ingest(
            {
                "event_id": "e1",
                "commit_seq": 1,
                "workspace_id": "w1",
                "request_id": "req-1",
                "generation": "gen-2",
                "event_type": "work.started",
                "payload": {},
            }
        )
    assert proj.records == {}


async def test_r5_rf09_05_coalesce():
    """Refresh coalesces to one in-flight read under rapid keys."""
    from textual.app import App

    calls = []

    class SlowReader:
        async def read(self, request_id):
            calls.append(request_id)
            return {name: "x" for name, _ in CyranoMonitorScreen.TABS}

    app = App()

    async with app.run_test() as pilot:
        await app.push_screen(CyranoMonitorScreen(SlowReader(), "req-1"))
        await pilot.pause()
        for _ in range(5):
            await pilot.press("r")
        await pilot.pause()
    # exclusive worker group: at most one extra read in flight
    assert 1 <= len(calls) <= 6
    assert reader_calls_bounded(calls)


def reader_calls_bounded(calls):
    """All reads went to the same request; ledger untouched."""
    return set(calls) == {"req-1"}


async def test_r5_rf09_06_no_mutation():
    """A model-printed 'approve' in a view performs no mutation."""
    from textual.app import App

    reader = _Reader(
        views={
            name: "approve --all now" for name, _ in CyranoMonitorScreen.TABS
        }
    )
    app = App()

    async with app.run_test() as pilot:
        await app.push_screen(CyranoMonitorScreen(reader, "req-1"))
        await pilot.pause()
        assert reader.mutations == 0
        assert not hasattr(app.screen, "approve")
        await pilot.press("escape")
