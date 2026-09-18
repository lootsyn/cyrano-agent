# Cyrano Agent · 작은 길잡이

**실제 개발 위치:** dcode 전체 monorepo의 `libs/code/`. `deepagents_code/cyrano/`는 우리 제품 코드, `cyrano/`는 개발 문서·계약·도구다. ZIP 상위 포장 도구에서 제품 개발을 하지 않는다.

처음은 [개발 가이드](execution/DEVELOPER_GUIDE.ko.md)와 [구현 지시](../IMPLEMENTATION_REQUEST.ko.md). 이후 [단일 개발계획](development/MASTER_DEVELOPMENT_PLAN.ko.md)의 준비된 WP를 선택한다. TS/RC/RF는 담당 WP의 검증·세분 작업이지 별도 설치 단계가 아니다.

| 작업 주제 | 원본 |
|---|---|
| dcode 연결·프로토콜·외부 worker | [dcode 통합](design/DCODE_INTEGRATION.ko.md) |
| 필수 인터뷰 | [인터뷰 설계](design/features/2026-09-16-interview-workflow.ko.md) |
| 계획·리뷰·HITL·변경·실행 | [계획·실행 설계](design/features/2026-09-16-plan-memory-execution.ko.md) |
| Memory·자기개선 | [Memory](design/MEMORY_LIFECYCLE.ko.md), [개선](design/SELF_IMPROVEMENT_LIFECYCLE.ko.md) |
| 캐시·도구·skill | [컨텍스트](design/architecture/2026-09-16-cache-context.ko.md) |
| 모니터링·내부 UI | [관측](design/OBSERVABILITY_PIPELINE.ko.md), [화면](design/NATIVE_MONITOR_TUI.ko.md) |
| 실제 시험·40점 평가 | [전략](testing/STRATEGY.ko.md), [실행](execution/TEST_RUNBOOK.ko.md) |

`python cyrano/scripts/doc_route.py --task WP09 --content`로 필요한 작업 문서만 읽는다. [전체 목차](INDEX.ko.md)는 탐색용이며 통합본과 연구팩은 기본 읽기 대상이 아니다. `python cyrano/scripts/dev.py docs`는 라우터를 포함해 자동 갱신한다.
