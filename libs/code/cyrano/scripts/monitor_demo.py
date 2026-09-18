"""Show a synthetic monitor projection or optional Textual component."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from bootstrap import activate

activate()
from deepagents_code.cyrano.monitor.projection import MonitorProjection


def synthetic_view() -> tuple[MonitorProjection, dict[str, str]]:
    """Return fake records for UI review, not production evidence."""
    view = MonitorProjection("W-DEMO", "R-DEMO", "G-DEMO")
    events = [
        ("plan.reviewed", {"result": "revised"}),
        (
            "model.attempt_started",
            {
                "attempt_id": "a1",
                "logical_request_id": "l1",
                "is_retry": False,
            },
        ),
        (
            "model.attempt_started",
            {"attempt_id": "a2", "logical_request_id": "l1", "is_retry": True},
        ),
        (
            "model.attempt_started",
            {"attempt_id": "a3", "logical_request_id": "l1", "is_retry": True},
        ),
        ("test.failed", {"code": "ASSERTION_MISMATCH", "cause": "unknown"}),
        ("memory.applied", {"application_id": "app1"}),
        ("learning.proposed", {"candidate_id": "c1"}),
    ]
    for index, (kind, payload) in enumerate(events, 1):
        view.ingest(
            {
                "event_id": f"E-{index}",
                "commit_seq": index * 3,
                "workspace_id": "W-DEMO",
                "request_id": "R-DEMO",
                "generation": "G-DEMO",
                "event_type": kind,
                "payload": payload,
            }
        )
    counts = view.summary()
    panels = {
        "overview": "합성 데모 / 제품 실행 아님\n계획 rev4 · VERIFY\n"
        + json.dumps(counts, ensure_ascii=False, indent=2),
        "timeline": "\n".join(
            f"{e['commit_seq']}: {e['event_type']}" for e in view.timeline()
        ),
        "calls": "논리 요청 1 / 실제 시도 3 / 재시도 2\n"
        "사용량·cache·비용: 미측정",
        "changes": "test.failed: ASSERTION_MISMATCH\n"
        "확정 원인: unknown\n원본 코드 변경 없음",
        "memory": "적용 검증 synthetic 1개\n실제 Memory DB 연결 안 됨",
        "learning": "후보 synthetic C1\n실제 생성·평가·승격 미실행",
        "health": "UI data source: synthetic\n도구 설치·모델 호출 "
        "없음\n관측 coverage: unknown",
    }
    return view, panels


def main() -> int:
    """Print demo JSON or an escaped offline page; optional TUI."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", type=Path)
    parser.add_argument("--tui", action="store_true")
    args = parser.parse_args()
    view, panels = synthetic_view()
    if args.html:
        content = (
            '<!doctype html><html lang="ko"><meta charset="utf-8"><title>'
            "Cyrano Monitor — Synthetic prototype</title><style>"
            "body{font:16px system-ui;margin:3rem auto;max-width:1100px;"
            "padding:1rem;background:#0b1520;color:#ecf2f5}"
            "header{padding:1.5rem;border:1px solid #486070}"
            "nav{display:flex;gap:.5rem;flex-wrap:wrap;margin:1rem 0}"
            "button{padding:.7rem;border:1px solid #55758c;"
            "background:#183449;color:white;cursor:pointer}"
            "section{padding:1.5rem;border:1px solid #486070;"
            "margin:1rem 0}pre{white-space:pre-wrap;"
            "overflow-wrap:anywhere;font:14px ui-monospace,monospace}"
            ".badge{color:#ffd68a}</style><header><h1>"
            'Cyrano Agent · 내부 Monitor 설계 시연</h1><p class="badge">'
            "SYNTHETIC / 실제 dcode 제품 화면·실행 증거 아님</p><p>"
            "R-DEMO · W-DEMO · 연결되지 않음 · 계측 범위 불명"
            "</p></header><nav>"
        )
        labels = [
            "요약",
            "흐름",
            "호출",
            "변경·검증",
            "기억",
            "개선",
            "도구·상태",
        ]
        for key, label in zip(panels, labels, strict=True):
            content += (
                f"<button onclick=\"document.getElementById('{key}')"
                f'.scrollIntoView()">{label}</button>'
            )
        content += "</nav>"
        for (key, value), label in zip(panels.items(), labels, strict=True):
            content += (
                f'<section id="{key}"><h2>{label}</h2>'
                f"<pre>{html.escape(value)}</pre></section>"
            )
        args.html.write_text(content + "</html>", encoding="utf-8")
        print(json.dumps({"kind": "synthetic_html", "path": str(args.html)}))
        return 0
    if args.tui:
        try:
            from textual.app import App

            from deepagents_code.cyrano.monitor.screen import (
                CyranoMonitorScreen,
            )
        except ImportError as error:
            print(
                json.dumps(
                    {
                        "status": "blocked",
                        "reason": str(error),
                        "native_runtime_verified": False,
                    }
                )
            )
            return 2

        class FakeReader:
            async def read(self, request_id: str) -> dict[str, str]:
                return dict(panels)

        class Demo(App):
            def on_mount(self) -> None:
                self.push_screen(CyranoMonitorScreen(FakeReader(), "R-DEMO"))

        Demo().run()
        return 0
    print(
        json.dumps(
            {
                "kind": "synthetic_not_product",
                "summary": view.summary(),
                "panels": panels,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
