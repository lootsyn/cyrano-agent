# 평가 3·4 보완 개발계획

문서 유형: 개발계획. 상태: planned. 기존 24개 WP와 12개 TS를 유지하고 13개 RC 세분 작업을 추가한다. 단순 재번호가 아니라 부족했던 storage/API/observer/query/application/release 구현 의무를 소유 WP에 연결한다.

## 필수 읽기

[Memory](../design/MEMORY_LIFECYCLE.ko.md), [Self-Improvement](../design/SELF_IMPROVEMENT_LIFECYCLE.ko.md), [Monitoring](../design/OBSERVABILITY_PIPELINE.ko.md), [실행 절차](../execution/MEMORY_OBSERVABILITY_RUNBOOK.ko.md), [현재 문서 목차](../INDEX.ko.md).

## 작업 순서

| RC | 기존 소유 WP | 산출 기능 | 세분 선행 | 상세 명세 |
|---|---|---|---|---|
| RC00 | WP00 | dcode 복사·native import·wheel 검증 | — | [작업](refinements/RC00.ko.md) |
| RC01 | WP00 | 문서 라우팅·품질·계획 시작 규칙 | RC00 | [작업](refinements/RC01.ko.md) |
| RC30 | WP11 | Memory durable 저장·revision·scope | — | [작업](refinements/RC30.ko.md) |
| RC31 | WP11 | Recall·native prompt binding·캐시 epoch | RC30, RC00 | [작업](refinements/RC31.ko.md) |
| RC32 | WP11 | Memory 적용 증명·정정·삭제 | RC31 | [작업](refinements/RC32.ko.md) |
| RC33 | WP16 | Episode→가설→학습계획→후보 | RC30, RC40 | [작업](refinements/RC33.ko.md) |
| RC34 | WP20 | 실제 paired·회귀·sealed 평가 | RC33, RC41 | [작업](refinements/RC34.ko.md) |
| RC35 | WP21 | 승격·next-run binding·revoke | RC34, RC32, RC36 | [작업](refinements/RC35.ko.md) |
| RC36 | WP19 | 경로 B 코드·resource·migration | RC34, RC00 | [작업](refinements/RC36.ko.md) |
| RC40 | WP13 | 요청 timeline·transactional event/outbox | — | [작업](refinements/RC40.ko.md) |
| RC41 | WP13 | native 호출 coverage·지표 정확성 | RC40 | [작업](refinements/RC41.ko.md) |
| RC42 | WP13 | Trace 조회·원인·privacy·권한 | RC40, RC41 | [작업](refinements/RC42.ko.md) |
| RC43 | WP23 | native E2E·부하·40점 증거 패키지 | RC35, RC42, RC01 | [작업](refinements/RC43.ko.md) |

RC43는 WP23 소유다. WP13 완료를 RC43 전체 end-to-end와 묶어 두면 WP21→WP13→RC43→WP21 순환이 생기므로 금지한다. WP13의 완료는 RC40–RC42와 자체 native 범위 검사, 전체 연결 평가는 WP23/RC43가 소유한다. RC34는 WP20을 구현하는 작업이지 WP20 전체 완료를 먼저 요구하지 않는다. 준비 스크립트가 세분 DAG와 부모 소유 관계를 확인한다.

## 구현 배치

첫 수직 절편은 source 준비→scope/event store→native observer→memory persistence/query다. 이후 plan에 memory 근거 연결→실행 적용 checker→실패 episode→학습계획/후보→actual evaluation→approval/promotion→새 session 적용→trace 조회를 연결한다. DB·DTO만 있고 native consumer가 없으면 API component 완료로만 기록한다.

격리·승인·audit 경계는 WP03/WP06에 있으며 prompt로 대체할 수 없다. 개발 시 코딩 assistant가 준수하는 plan/review 문서 절차와 제품이 사용자의 작업에서 변경을 강제하는 runtime gate의 evidence를 분리한다.

## 평가 항목별 종료 증거

3-1: process restart persisted revision; 3-2: memory view→request→plan/code/test application; 3-3: evidence-backed system block/skill/working-memory 후보; 3-4: actual paired+regression→approval→next-run artifact binding.

4-1: request phase chain/review loops; 4-2: main+child+aux model/tool/memory/learning outcome/error; 4-3: unique requests/physical attempts/retry/time/usage completeness; 4-4: read-only user가 실패 원시 근거까지 탐색한 실행 evidence.

각 항목의 증거는 [15개 rubric](../../contracts/assessment/rubric.json)에 연결한다. RC/fixture/schema 통과 숫자로 40점을 자동 부여하지 않는다. 기존 source-style 부채는 RC01/WP22의 품질 검사에서 해결해야 한다.
