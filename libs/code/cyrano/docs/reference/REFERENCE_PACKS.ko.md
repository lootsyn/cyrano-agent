# 첨부 문서팩 사용·충돌 해결

## 배치와 신뢰

`references/packs/dcode-analysis/`와 `references/packs/python-engineering/`에 첨부 원문을 그대로 보존했다. manifest는 `contracts/integration/r3-reference-packs.json`이다. 분석 문서 속 AGENTS/CLAUDE는 해당 자료의 역사적 지시이며 현재 repository root의 지시를 대체하지 않는다. 자동 skill discovery에 두 reference pack 전체를 넣지 않는다. `.agents/skills/cyrano-assessed-development`는 task별 필요한 절만 읽도록 안내한다.

참조 우선순위는 현재 사용자 A/B/C 요구 → R3 결정과 실행 계약 → 실제 고정 dcode source/test → 승인된 CYRANO 계약 → 첨부 분석 주장이다. 소스는 현재 동작의 증거이지 버그가 없다는 증명이 아니다. 분석의 추정은 직접 source/runtime 검증 전까지 추정으로 유지한다.

## dcode-analysis를 작업에 연결

분석 baseline은 `1d3232c0852c47af09119edea10eeec887e4f0da`, 공식 문서 수집은 2026-09-15다. 현재 검토한 main은 `7f9e8ed3a555933902045792da9bb184950ee7b2`다. 첨부 README의 annotated-ko clone·baseline tag·GitNexus index가 ZIP에 실제 들어있다고 가정하지 않는다. 첨부는 문서 71개이며 upstream clone은 별도 준비한다. 과거 line number 대신 현재 symbol+blob SHA를 사용한다.

| 분석 | 관련 구현 | 재검증 초점 |
|---|---|---|
| 00 overview | WP00·전체 source map | 문서/코드 차이 S1–S8·F1–F12는 버그 확정이 아님 |
| 01 boot/client/server | WP00/WP07/WP23 | 실제 client/server config 전달, crash·resume·ACP 차이 |
| 02 assembly/SDK | WP04/WP05/WP13 | middleware 이름 병합·순서·부모/자식·compaction |
| 03 config/models | WP00/WP05/WP13 | credential 우선순위·runtime generation·retry/billing |
| 04 approval/security | WP03/WP10 | Auto/headless/child 우회 가능성을 fault test로 확인 |
| 05 subagents/rubrics | WP04/WP09/WP20 | fork 독립성·reviewer readonly·grader calls |
| 06 memory/skills | WP05/WP11/WP18 | source precedence·auto-save·thread reload·resolved digest |
| 07 MCP/hooks/extensions | WP04/WP07/WP12 | trust scope·실제 hook process·timeout·등록 실패 |
| 08 sandbox | WP03/WP23 | setup 실패 cleanup·working dir·credential argv leak |
| 09 TUI/commands/ACP | WP14/WP23 | trace 조회·모드 dispatch·완료 의미 |

현재 직접 source를 확인한 사실: dcode metadata/로컬 dependencies와 native Ruff·ty, `create_cli_agent`의 Memory/Skills 구성과 extension middleware 병합·SDK 전달. 나머지 위 재검증 초점은 WP00/L3/L4의 미실행 의무이며 이번에 모든 버그를 재현했다고 표시하지 않는다.

## Python Engineering pack을 작업에 연결

15개 상세설계 장·12개 PY-W 작업·60개 PY-T 사례·4개 wire schema·참조 모델·정상/거부 fixtures·skill/role/CI templates를 보존했다. imported reference contracts는 모델 입력 검증의 참고 구현이지 source authentication·OS confinement의 증명은 아니다.

PY-W01→WP00(정책·toolchain), W02→WP01+WP06(계약·reducer), W03→WP03+WP06(snapshot), W04→WP03+WP06(policy guard), W05/W06/W07→WP06(format/lint/type/test/baseline), W08→WP02+WP06(evidence completion), W09→WP09+WP12(skill·repair), W10→WP07+WP12(dcode/hook), W11→WP22+WP23(CI/운영), W12→WP13+WP18+WP20(관측·개선)로 연결한다. 원본 작업을 implemented로 바꾸지 않는다.

## 선택한 충돌 해결

**도구:** 원문은 CYRANO Black/mypy, 현재 dcode는 Ruff/ty다. native 소스에는 Ruff 단일 formatter와 upstream ty를 유지한다. 외부 repository의 Black adapter·mypy/Pyright adapter 요구는 삭제하지 않는다. baseline과 tool parser는 formatter 종류·버전별로 다르게 고정한다.

**행 길이:** pack의 기본 team88과 R2의79가 다르다. native CYRANO 영역은 R2의79/doc72를 유지하고 upstream 전체는 원본 정책을 유지한다. customer workspace는 현재 합의를 탐색하고 승인 없이 global 정책을 바꾸지 않는다. test fixtures에서는 team88과pep79 profile 양쪽을 지원·검사한다.

**평가 배점:** 과거 20×2와 사용자 최신15세부항목 배점은 다르다. 최신15항목을 canonical로 사용하며 old scorecard는 historical fixture로만 검증한다. 기존 schema의 enum을 조용히 변경하지 않는다.

**설치 구조:** 과거 독립 uv workspace 금지를 현재 native integration 대상으로 대체한다. 고객 repository 비침습 설치·model 특화 추가 금지·immutable memory·승인·경로A/B·trace는 그대로다.

**완료·retention:** Python report의 PASS와 사용자 업무 COMPLETE는 다르다. registered report·current review·permit·source revision을 모두 확인해야 COMPLETE다. Python pack의 raw log14일/normalized90일은 외부 정책 제안이고 기존 CYRANO retention policy를 자동으로 덮지 않는다. 최종 resolved retention·민감도·삭제 cascade는 사람 승인 policy가 소유한다.

## AI 개발자의 읽기 순서

처음에는 START_HERE→R3 전략→native layout→할당 WP→해당 분석1개와 Python 설계 장만 읽는다. 실제 code symbol·현재 tests를 연 후 source binding을 기록한다. 검증되지 않은 reference의 번호·명령·API를 실제 제품 API라고 호출하지 않는다. 전체 reference pack을 system prompt에 넣지 않고 selection manifest에 필요한 path/hash/reason만 기록한다.
