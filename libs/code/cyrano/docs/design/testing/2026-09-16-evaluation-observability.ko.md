# 실제 개선 평가·관측·출시 판정

문서 유형: 상세 설계 · 상태: 계획(제품 미구현)


## Problem

정적 schema 검증, 오프라인 replay, 실제 모델 실행, 운영 효과는 서로 다른 증거다. 이를 한 개 PASS로 합치면 사용자에게 기능·효과·보안이 검증되었다는 잘못된 인상을 준다. 자기개선의 비용과 실패·중단 표본을 함께 관리해야 한다.

## Proposal

### 통합 R2 증거·점수·비용

contracts/assessment/rubric.json과 evidence/product-scorecard.json을 연결한다. 현재 15개 criterion은not_evaluated/0이며hardgate는not_tested다. 65개eventpayload와 producerauthority를검증하고optional providercache미지원과필수audit누락을구분한다. cost는billableleafattempt단위이고usage불명은null/미결liability다. 제품 수용 명세 수는 실제 평가 corpus 크기나 수행 증거가 아니다.

자세한 해석·충돌 해결은 [Universal Harness 통합 설계](../architecture/2026-09-16-universal-harness-integration.ko.md)를 따른다. 원본첨부에 있는 더 느슨한예시로 이규칙을낮추지 않는다.

### 1. 증거 계층과 저장 위치

`fixture`는 가상 입력, `unit`은 작은 함수의 실행 결과, `integration`은 실제 서비스 연결, `sandbox`는 격리 실행 경계, `live`는 실제 provider task, `production`은 승인된 운영 관측이다. 하위 계층을 상위 계층으로 승격하지 않는다. `evidence/`에는 실제 수행한 검사 결과만, `tests/fixtures`에는 synthetic 값만 둔다. 수용 명세는 `not_run`으로 시작한다.

기반 코드의 100개 이상 unit 통과는 dcode 실제 연결·보안·cache hit·효과의 증거가 아니다. 도구가 없어서 실행 못 한 Ruff/ty는 `blocked`이며 PASS/skip-success가 아니다. Python3.13에서 실행한 검사를 Python3.12에서도 실행했다고 하지 않는다. CI workflow가 존재한다는 사실과 CI run이 성공했다는 사실을 구분한다.

### 2. Evaluation plan 사전 등록

ExperimentPlan은 candidate와 baseline digest, task/snapshot manifests, family split, validation·sealed access 정책, primary criterion, secondary metrics, mandatory safety tests, planned_pairs, budget·실험 permit, 순서 seed, cache condition을 실행 전에 봉인한다. 후보 결과를 본 뒤 유리한 성공 기준으로 바꾸면 새 실험이다.

독립 family 수·반복 수는 통계적 가설과 운영 scope를 반영해 정한다. 초기 예시 20 families × 3 repeats × 2 conditions는 120개 task execution, 60개 pair다. 반복 3회는 독립 family 3개가 아니다. 하나의 repo만 사용할 수 있으면 scope를 그 프로젝트의 task families로 제한하고 전역 일반화라고 보고하지 않는다.

### 3. 실제 paired evaluator

baseline과 candidate는 같은 task source·요구·환경·모델/endpoint·기본 예산·evaluator를 사용한다. 후보가 runtime code를 바꾸는 경우 의도한 runtime diff를 별도로 manifest에 표시한다. 각 pair의 실행 순서는 미리 정한 randomization에 따른다. 별도 clean sandbox와 새 task state를 사용하여 첫 실행의 cache artifact·source 수정·DB state가 두 번째에 오염되지 않도록 한다.

provider prompt cache 자체를 완전히 cold로 만들 수 없는 경우 forced cold라고 주장하지 않는다. `production_observed` 조건으로 cache usage를 기록하거나 native 기능으로 검증 가능한 통제만 적용한다. latency에는 queue·network·tool·judge와 모델 시간을 분리해 저장한다.

### 4. Hard gate와 두 개선 경로

승인 우회, scope 누출, 비밀 유출, hidden tests 접근, audit 변조, 테스트 삭제, 거짓 완료는 하나라도 hard reject다. safety fail을 높은 평균 success·비용 절감으로 상쇄하지 않는다.

품질 개선형은 품질 효과의 하한이 preregistered 최소 향상을 넘고 비용·latency 상한을 만족해야 한다. 효율 개선형은 품질 차이 하한이 `-noninferiority_margin` 이상이면서 비용/지연 차이 상한이 `-minimum_saving` 이하여야 한다. baseline/candidate의 방향은 모든 metric에 명시한다. 수치가 null·NaN·불완전이면 eligible이 아니다.

foundation `deepagents_code.cyrano.evaluation.gates.decision`은 효율 개선형의 계산 규칙 일부만 구현한다. 실제 분석기·authority 검증·다중 metric·품질 개선형은 WP20에서 구현한다. schema가 합법적인 EvaluationReport라도 trusted evaluator identity·signature·실행 참조·pair 수·analysis policy가 검증되지 않으면 release service가 받아들이지 않는다.

### 5. 통계와 분모

task repeat를 family 안에서 먼저 집계하고 family 간 차이를 비교한다. binary correctness는 pair difference와 실패 유형을 보존한다. 비용·latency는 평균뿐 아니라 분포와 극단값, 취소·timeout을 보고한다. family clustered bootstrap 또는 사전 승인된 분석기로 interval을 구하고 method·seed·resample count·software hash를 남긴다. 여러 후보를 계속 시험할 때 validation access 제한과 final sealed set으로 선택 편향을 줄인다.

환경 실패 때문에 양쪽 모두 실행 못 한 pair는 원래 계획된 분모에 남기고 invalid/missing 원인을 기록한다. 안전하게 재실행 가능한 경우 preregistered retry rule에 따라 같은 pair를 보충한다. 후보에 불리한 task만 제거하지 않는다. 검정력 부족은 inconclusive이며 sample size를 늘릴 예산·동의가 없으면 baseline을 유지한다.

### 6. 누수 방지

repository family, issue lineage, adjacent commit, 생성 task template, 사용자 대화 원형을 split key로 사용한다. 같은 원형의 단어만 바꾼 task가 train과 sealed에 나뉘지 않게 한다. 시간 cut-off 뒤에 나온 수정 코드·memory·acceptance를 과거 task 입력에 주입하지 않는다.

Author·learning analyst는 sealed files나 detailed judge outputs를 읽지 못한다. 평가 plan의 hidden manifest reference는 opaque ID다. 개발 세트 detailed feedback, validation aggregate, sealed withheld가 기본이다. evaluator 로그의 정답 snippet이 일반 telemetry로 새어나가는 것도 테스트한다.

### 7. 비용·예산

기록할 비용은 사용자 업무, reflection/analysis, candidate 생성, replay 계산, 실제 baseline/candidate, reviewer, 저장·운영이다. 금액은 decimal string과 currency를 함께 저장한다. adapter가 과금 의미를 모르면 null이다. 금액/usage가 없는데 0으로 넣어 절약이라고 계산하지 않는다.

각 worker에 model/tool/시간/금액 cap과 남은 예산 lease를 준다. concurrent workers가 같은 남은 예산을 중복 소비하지 않도록 reserve/settle 원장을 적용한다. 외부 청구 receipt가 지연되면 reserved와 actual을 분리한다. 실제 발생한 비용이 cap을 초과했을 때의 정지·알림·미정산 처리도 기록한다.

### 8. Observability event vocabulary

이벤트는 command 원장, 신뢰된 runner 관측, model self-report, 외부 service 응답을 구별한다. session/run/WorkUnit/Attempt/model/tool trace 관계와 producer_seq·중앙 event_seq를 보존한다. event_seq는 commit 순서이며 벽시계 순서와 같다고 가정하지 않는다. 같은 프로세스의 소요시간은 monotonic clock으로 계산한다.

필수 영역은 session lifecycle, interview obligations/answers, contract/review, plan/approval, permit/tool/file/test, memory recall/application, learning proposal/impact, replay support, actual pairs/judge, release/canary/rollback, telemetry gaps·recovery다. payload는 이벤트별 versioned schema에 연결한다. 새로운 model-visible input은 context event가 있어야 한다.

### 9. Dashboard 최소 화면

| 화면 | 필수 표시 | 잘못된 표시 방지 |
|---|---|---|
| Sessions | 단계·상태·scope·blocking reason | cancelled/unknown를 success로 묶지 않음 |
| Timeline | 사용자→계획→도구→검증→학습 연결 | model report와 runner 결과 구별 |
| Plan & Approvals | DAG·권한 목적·만료·변경 영향 | spec approval을 execute 승인처럼 표시 안 함 |
| Changes & Verification | source diff·baseline·actual test | 실행 안 된 test를 통과로 안 보임 |
| Memory Inspector | scope·근거·stale·사용 단계 | relevance를 진실 확률처럼 표시 안 함 |
| Learning A/B | 가설·diff·route·실제/replay·상태 | out_of_support를 실패로 안 보임 |
| Cache & Cost | 관측된 사용량·missing·총비용 | null을0, hash동일을hit로 표시 안 함 |
| Releases & Recovery | active/pinned/revoked·rollback 영향 | harness rollback과 코드 원복 구별 |
| Runtime Health | compatibility·telemetry gaps·worker leases | 미검증 capability를 녹색으로 표시 안 함 |

제품의 기본 화면은 dcode 내부 Textual TUI다. 조회는 인증된 query service를 사용하고 대화/LLM 호출과 분리한다. 외부 HTML/SSE backend는 선택사항이며 기본 실행의 의존성이 아니다. 외부 화면을 활성화할 때도 조회와 승인 mutation을 분리하고 origin/CSRF/session auth를 적용한다. 파일 경로·민감 payload와 제어문자를 안전하게 렌더링한다.

### 10. 강제 경고와 CoverageReport

즉시 경고는 무승인 실행, protected path, cross-scope memory, audit 저장 실패, unknown execution outcome, critical plan drift, 필수 검증 누락, secret 노출이다. 일반 경고는 예산 소진 임박, exporter backlog, 반복 tool failure, cache metrics missing이다. self-improvement가 경보 threshold를 자동 낮춰 경고 수만 줄이지 못하게 한다.

coverage report에는 각 사건 유형의 1차 관측 경로, 보완 경로, 테스트 ID, 마지막 성공 여부, 미검증/누락 사유가 들어간다. 분모가 비어 있다고 100%로 표시하지 않는다. summarization·native child provider retry 누락이 있으면 그 범위를 명시한다.

### 11. 출시 판정

출시 판정은 준비물 완성, 코드 품질, 전체 기능·권한 통합, 실제 효과를 별도 단계로 표시한다. WP23 완료 전에 실제 운영 자기개선 기능이 완성됐다고 하지 않는다. `project-manifest.json`, WP 상태, evidence의 차이를 검사하여 계획 문서만 작성하고 implemented로 옮기지 못하게 한다.

네 추가 요구 PEP8/계획 리뷰/Memory Self-Improving/전체 관측의 평가점수는 실행 증거 기반이다. 항목당 체크리스트가 있어도 실행하지 않았다면 해당 효과·통합 점수를 자동 부여하지 않는다. 만점 숫자를 설계서 표지에 붙이지 않는다.

## Alternatives considered

**하나의 합산 score:** safety·correctness 악화를 효율로 상쇄할 수 있다. hard gate와 목적별 interval을 분리한다.

**replay latency를 실제 비용으로 계산:** cache·routing·queue가 달라진다. historical proxy와 actual을 별도 필드로 둔다.

**외부 trace 서비스 필수:** 비밀·접근·비용 문제로 사용 불가능할 수 있다. local event store가 기본이고 외부 export는 선택적이다.

## Acceptance criteria

B의 zero-actual 평가가 eligible이 될 수 없어야 한다. paired denominator·family split·sealed access·budget fence·unknown usage를 검사한다. dashboard 모든 상태가 실제 evidence level을 드러내야 한다. 실제 cache/효과 측정이 없으면 unknown/not_tested 표시가 유지되어야 한다.

## Risks

모델·provider 변화, 작은 표본, 과한 experiment 비용, selection bias, 외부 trace의 개인정보 보존이 주요 위험이다. release는 모델 이름 특화가 아니라 검증한 실행 조건과 허용 scope를 명시한다.

## Native CLI 모니터링의 현재 설계 연결

사용자 운영 모니터링의 기본은 [dcode 내부 Monitor](../NATIVE_MONITOR_TUI.ko.md)다. 기존 dashboard 용어는 이 native 화면의 읽기 view를 포함하는 개념이며 외부 웹 UI 필수 요구가 아니다. 실행은 RF07–RF09에서 native 명령·인증 query·Textual·실제 호출 coverage를 함께 검증한다.
