"""Move into a reviewed native test suite after installing dcode test deps.

This exercises a component with fake data, not a product monitoring backend.
"""

import pytest
from textual.app import App
from textual.widgets import Static
from deepagents_code.cyrano.monitor.screen import CyranoMonitorScreen


class Reader:
    async def read(self, request_id):
        return {key: "합성 fixture" for key in [
            "overview", "timeline", "calls", "changes", "memory", "learning", "health",
        ]}


class MonitorApp(App):
    def on_mount(self):
        self.push_screen(CyranoMonitorScreen(Reader(), "R-TEST"))


@pytest.mark.asyncio
async def test_component_escape_and_refresh():
    app = MonitorApp()
    async with app.run_test(size=(100, 35)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, CyranoMonitorScreen)
        assert len(app.screen.query(Static)) >= 9
        await pilot.press("r")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, CyranoMonitorScreen)
