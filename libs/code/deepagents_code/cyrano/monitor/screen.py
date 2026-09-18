"""Textual monitor component; native binding is an RF07 work item.

This screen never opens a database, invokes an LLM, or approves a
mutation.
"""

from __future__ import annotations

from typing import Protocol

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Static, TabbedContent, TabPane

from deepagents_code.cyrano.monitor.projection import terminal_text


class MonitorReader(Protocol):
    """Supply authorized and already-redacted, bounded view text."""

    async def read(self, request_id: str) -> dict[str, str]:
        """Return tab-name to bounded text; raise on denial."""
        ...


class CyranoMonitorScreen(ModalScreen[None]):
    """Read-only overlay which leaves the agent's task running."""

    BINDINGS = [("escape", "dismiss", "대화로"), ("r", "refresh", "갱신")]
    TABS = (
        ("overview", "요약"),
        ("timeline", "흐름"),
        ("calls", "호출"),
        ("changes", "변경·검증"),
        ("memory", "기억"),
        ("learning", "개선"),
        ("health", "도구·상태"),
    )
    DEFAULT_CSS = """
    CyranoMonitorScreen { align: center middle; }
    #cyrano-body { width: 96%; height: 94%; border: solid $accent; }
    #cyrano-connection { height: 2; }
    TabPane { height: 1fr; }
    """

    def __init__(self, reader: MonitorReader, request_id: str) -> None:
        """Store the authorized reader and target request id."""
        super().__init__()
        self.reader = reader
        self.request_id = request_id

    def compose(self) -> ComposeResult:
        """Build panes; no file reads or network calls happen here."""
        with VerticalScroll(id="cyrano-body"):
            yield Static("Cyrano Agent · 읽기 전용", markup=False)
            yield Static("연결 확인 전 · 값 미확인", id="cyrano-connection")
            with TabbedContent():
                for name, title in self.TABS:
                    with TabPane(title, id=f"tab-{name}"):
                        yield Static("미조회", id=f"view-{name}", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        """Start the first nonblocking read once the overlay mounts."""
        self.action_refresh()

    def action_refresh(self) -> None:
        """Replace an older read worker; refresh makes no model turn."""
        self.run_worker(self._read(), group="cyrano-read", exclusive=True)

    async def _read(self) -> None:
        """Render authorized text, or swap in an explicit stale view."""
        try:
            views = await self.reader.read(self.request_id)
            if not isinstance(views, dict) or any(
                not isinstance(value, str) for value in views.values()
            ):
                raise ValueError("INVALID_MONITOR_VIEW")
            if not self.is_mounted:
                return
        except Exception:  # Never print bodies that may hold secrets.
            if not self.is_mounted:
                return
            # A failed read may mean authorization was revoked. Do not
            # keep the previous sensitive content visible anyway.
            for name, _ in self.TABS:
                self.query_one(f"#view-{name}", Static).update(
                    "데이터 숨김 · 연결과 조회 권한을 다시 확인하세요"
                )
            self.query_one("#cyrano-connection", Static).update(
                "조회 실패 · 이전 내용 숨김 · 원시 오류는 표시하지 않음"
            )
            return
        for name, _ in self.TABS:
            self.query_one(f"#view-{name}", Static).update(
                terminal_text(views.get(name, "데이터 미확인"), 16000)
            )
        self.query_one("#cyrano-connection", Static).update(
            "조회 완료 · 읽기 전용 · 원장 관측 범위는 요약에서 확인"
        )

    def on_unmount(self) -> None:
        """Cancel only this screen's workers, never the agent run."""
        self.workers.cancel_group(self, "cyrano-read")
