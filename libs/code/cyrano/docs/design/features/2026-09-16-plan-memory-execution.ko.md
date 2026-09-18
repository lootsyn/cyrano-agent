# 계획·독립 리뷰·사람의 결정·실행 통제

문서 유형: 현재 상세 설계. 제품 연결은 구현 대상이다. 필수 인터뷰의 원문·의무·revision 계약을 계획 이후까지 이어간다. 이전 납품판의 우선순위나 별도 보완팩을 읽어야 하는 구조가 아니다. 주 소유자는 WP09이며, 승인·효과 강제는 WP03, 인터뷰 인계는 WP07/08, native 연결은 WP06, 원장은 WP02, 관측은 WP13, 실행 검증은 WP10/20이 소유한다.

## 1. 하나의 업무 흐름과 종료 조건

`접수 → 필수 인터뷰 → 명세 확정 → 설계 선택 → 계획 초안 → 기계 교차 검사 → 독립 AI 리뷰 → finding 처리 → 사람 공동 검토 → 계획 승인 → 별도 실행 허가 → 작업 실행·검증·리뷰 → 통합 검증 → 최종 인수 → 허가된 반영/공개`가 기본 흐름이다. 설계·계획을 다시 고쳐야 하면 그 산출물의 소유 단계로 돌아간다. 대화가 길다는 이유로 검토 의무를 없애지 않는다.

기존 `contracts/v2/session-state-machine.json`은 세션의 큰 단계를 소유한다. 계획 검토의 세부 상태는 `contracts/v2/planning.schema.json`의 객체로 저장한다. 같은 의미의 두 전역 상태기계를 만들지 않는다. `plan_review` 단계 안에서 `draft → static_checked → under_review → changes_required/reviewed → presented → approved`를 관리하며, 변경·철회로 `stale`, 사용자 보류로 `deferred`, 거부로 `rejected`가 된다. 이 상태 자체는 실행 권한이 아니다.

요구를 이미 현재 코드가 충족하면 실제 검증과 독립 검토 후 `verified_no_change`를 결과 보고에 남긴다. 이를 위해 가짜 파일 수정·apply receipt를 만들지 않는다. 분석 요청은 `answered`로 종료하며, 이 두 결과와 코드 변경 결과를 구분한다. 기존 세션 완료 이벤트에는 결과 종류와 검증 참조를 결속한다.

## 2. 필수 인터뷰에서 계획으로의 인계

WP07/08은 `InterviewContract`와 현재 요구·제약·acceptance·비목표·미해결 의무·신뢰된 사용자 결정 참조를 전달한다. 과거에 답한 질문은 관련 범위와 근거가 유효하면 재사용한다. 질문 수가 0이어도 준비도 검사를 생략하지 않는다. 알려진 blocker, 사용자 의도 충돌, 필수 검증 불가능 상태를 점수 평균으로 상쇄하지 않는다.

인계 수신자는 계약 digest, source snapshot, 사용 가능한 runtime 기능, scope, 최신 MemoryView, 개인정보 분류를 확인한다. 사용자의 명시적 제품 결정을 agent의 추정으로 바꾸지 않는다. 정보 수집과 로컬 설치·script 실행은 다르다. 계획 전 조사에서 실행이 필요하면 읽기 전용으로 검증된 recipe와 별도 준비 허가를 사용하며, '조사'라는 이름으로 untrusted repository script를 무제한 실행하지 않는다.

## 3. 계획 객체와 서명 대상

기존 `GovernedWorkPlan`이 계획의 실행 범위를 표현한다. 그 위의 `PlanReviewSubject`는 다음을 추가로 결속한다. 요구·설계 선택·초기 source snapshot·work plan digest·허용된 runtime/도구/skill policy·테스트 계획·예산·외부 효과·복구 절차·검토 대상 파일·증거 보존 정책이다. 허용범위가 없는 항목을 `null`로 덮어넣어 통과시키지 않는다.

작업에는 `requirement_ids`, `acceptance_ids`, 생성/수정/삭제할 파일, 읽을 근거, 소비/생산 인터페이스, dependency, 독점 자원, 정확한 argv와 cwd, env allowlist, timeout, retry class, 비용 한도, owner, expected artifact, 검증 oracle, 실패·복구가 필요하다. 구현 단계는 작은 검증 가능한 결과를 만든다. 단순 '수정한다/테스트한다'는 작업 정의가 아니다.

**해시 순환을 금지한다.** 승인 대상 projection에는 진행률·화면 cursor·review response·approval_ref·execution_permit_ref·signature·실행 결과를 넣지 않는다. Subject를 먼저 봉인하고 리뷰·표시·승인·permit이 그 digest를 바깥에서 참조한다. 표시 문자열 변화가 권한 범위 변화인지 별도 classifier가 판단한다. JSON key 순서나 공백 재정렬 때문에 실행 의미가 바뀌었다고 하지 않으며, 문자열 안 공백·NFC/NFD·명령 인수의 다른 bytes는 임의로 합치지 않는다.

계획의 초기 source와 승인 범위 안에서 생성된 작업 사본 revision을 구분한다. 승인된 이전 작업의 정상 수정으로 `candidate_head`가 바뀐 것은 허용된 계보 진전이며 매 도구 호출마다 전체 계획을 재승인하지 않는다. 작업은 예상 parent output digest에 결속한다. 사용자의 원본 수정, 다른 branch 결과, 허용하지 않은 파일 변경은 계보에 없으므로 stale 처리한다.

## 4. 정적 교차 검사 알고리즘

`validate_plan(subject, contract, inventory)`는 다음 순서로 findings를 반환한다. 검사는 권한을 발급하지 않는다.

1. ID 중복, 누락 ref, 잘못된 schema와 scope를 거부한다. 익명 빈 계획·비어 있는 완료 기준도 거부한다.
2. 모든 활성 requirement에 구현 작업 또는 근거 있는 `verified_no_change/not_applicable` 판정을 연결한다. 필수 요구를 advisory로 낮추지 않는다.
3. 각 WorkUnit의 acceptance에 실제 oracle·실행환경·긍정/부정 fixture를 연결한다. test 이름의 존재만 확인하는 test로 대체하지 않는다.
4. 소비 인터페이스와 생산 인터페이스의 이름·인수·반환·예외·데이터 형식·소유 transaction을 비교한다. 연속 작업 간 환경·schema·lockfile 변경도 의존성이다.
5. DAG cycle·없거나 자기 자신을 가리키는 dependency를 거부한다. 같은 자원에 대한 동시 쓰기는 conflict edge 또는 명시적 serialization을 요구한다.
6. network·install·MCP·외부 agent·CI 설정·데이터 migration·비용 증가를 효과 목록에 포함한다. shell 명령이 파일 목록 밖을 바꿀 수 있으면 해당 실행환경을 격리한다.
7. 실패·취소·timeout·unknown outcome·보상 실패 때 멈출 위치와 담당자를 확인한다. 다중 파일 apply를 단일 DB transaction이라고 기술한 계획은 거부한다.
8. 지원하지 않는 runtime 기능이나 숨겨진 사용량으로 budget upper bound를 만들 수 없으면 자동 실행 후보에서 제외한다. 권한 검사는 fallback으로 생략하지 않는다.

출력 `PlanCheckReport`는 각 검사 ID, 실제 관측, 참조 위치, 영향, `passed/failed/unverifiable/not_applicable`와 근거를 가진다. Unknown 검사는 pass로 합치지 않는다. 과거 검사를 재사용하려면 source/policy/runtime/subject/test-plan fingerprint가 같아야 한다.

## 5. 독립 AI 리뷰의 입력과 분리

Reviewer는 별도 실행 식별자와 read-only 도구만 받는다. 같은 모델 사용 자체는 독립성 위반이 아니지만 작성자의 동일 실행을 표시 이름만 바꿔 reviewer로 삼지 않는다. '독립'은 실행·쓰기 권한·평가 근거의 분리이지 통계적 오류 독립성 보장이 아니다. blind handoff 검토자는 작성자의 결론·이전 리뷰의 verdict를 기본 입력으로 받지 않는다.

최소 검토 영역은 요구 일치, 구현 가능성·의존성, 테스트·oracle 적절성, 운영·취소·복구다. security reviewer는 높은 위험 또는 승인/비밀/격리 변경에 추가한다. 모델 이름을 기준으로 별도 프롬프트를 하드코딩하지 않는다. 같은 scope 안의 신뢰된 원문을 읽어야 하며 필요한 근거를 못 읽으면 해당 영역은 `unverifiable`다.

`ReviewFinding`은 ID, subject_digest, reviewer_run, requirement/work-unit/file ref, 설명, evidence ref, severity, 실제 영향, 수정을 요구하는 조건, 반증 가능 조건을 포함한다. severity의 평균은 readiness 점수가 아니다. 계획의 잘못을 구현자가 임의로 무시할 수 있는 '의견'으로 만들지 않는다.

## 6. finding 처리·재검토·수렴

작성자의 응답은 `accept_fix / rebut_with_evidence / request_clarification`이다. 적용한 수정은 새로운 subject revision을 생성한다. `resolved` 판정은 새 artifact와 검증 증거를 확인한 reviewer/결정 서비스가 한다. 작성자가 자신의 finding 상태를 직접 완료로 변경할 수 없다.

오탐은 반증 근거를 reviewer가 확인해 `not_reproduced/invalid`로 닫는다. 위험 수용은 신뢰된 권한자의 명시적 범위·이유·만료가 있어야 하며 비완화 안전 의무·사용자 핵심 의도·검증 위조는 예외 대상이 아니다. '다른 reviewer가 괜찮다고 했다'는 단독 반박 근거가 아니다.

수정본은 dependency와 finding 위치로 영향범위를 계산한다. 영향받은 검토만 다시 수행하되 범위 판정이 불명확하면 검토 범위를 넓힌다. 새 source나 tool schema가 바뀌면 그 부분의 오래된 리뷰는 stale다. 상태는 아래처럼 종료한다.

| 조건 | 결과 |
|---|---|
| 필수 영역을 검토했고 blocking finding 없음 | 사람 검토용 표시본 생성 가능 |
| 수정 가능 finding 남음 | changes_required |
| 리뷰 예산/횟수 상한 도달, finding 남음 | deferred 또는 replan; 자동 통과 금지 |
| reviewer timeout/실패/근거 접근 불가 | unverifiable; 대체 검토는 새 run으로 기록 |
| 의견 충돌 | 근거 비교·상위 검토; 다수결 승인 금지 |

초기 설정의 `max_review_rounds=3`은 비용 제한이지 3회 후 합격 규칙이 아니다. 운영자가 변경하려면 계획 예산과 policy를 함께 확인한다.

## 7. 사람에게 보여줄 DecisionPacket

사람에게 제시할 내용은 목표/비목표, 실제 변경 파일·데이터, 선택한 대안·포기한 대안, 작업 순서, 테스트·미실행 항목, 외부 효과·권한·비용 상한, 복구 한계, 남은 finding, 이전 표시본과의 의미 차이다. 요약으로 중요한 위험을 숨기지 않는다. 상세 열람은 동일 immutable snapshot에서 가져온다.

`DecisionRequest`는 decision_id, purpose, subject_digest, display_digest, actor_scope, request_revision, nonce, expiry, 허용 입력 종류를 가진다. 검토 자료는 목적마다 다르다. 계획 동의, 실행 허가, 원본 반영, 최종 인수, 외부 공개를 한 generic 'yes'에 묶지 않는다. UI에서 여러 목적을 한 화면에 표시할 수는 있지만 목적별 명시 선택과 서로 다른 receipt를 생성한다.

기본 선택은 없음이다. Enter 연타·열기 직후 키 이벤트·재연결 후 지연된 click으로 승인하지 않는다. display digest를 renderer에 전달하고 사용자 이벤트가 동일 화면 generation에서 발생했는지 확인한다. 사용자가 실제로 모든 글을 읽었다는 사실까지 기술적으로 증명했다고 주장하지 않는다.

## 8. 사람 응답 판정과 amendment

구조화 응답은 `approve / reject / defer / cancel / request_changes / ask_question`이다. 자유 텍스트를 쓴 경우 parser는 proposal만 만들며 명시적인 UI 또는 신뢰된 caller의 확인이 실제 결정이다. '좋아, DB는 건드리지 말고 진행해'는 `request_changes`다. 원래 subject 승인과 수정 실행으로 나누어 몰래 처리하지 않는다.

수정 요청은 원문·제안 patch·목적을 저장하고 영향 요구·파일·외부 효과·테스트·budget을 재계산한다. 새로운 subject/display를 만든 뒤 영향을 받은 리뷰·승인을 다시 얻는다. 관련 없는 이전 user fact를 새로 질문하지 않는다. `cancel`은 요청 취소, `reject`는 해당 선택 거부, `defer`는 보류이며 모두 허가를 생성하지 않는다. 창 닫기·무응답·만료도 허가가 아니다.

부분 승인은 독립적으로 실행 가능한 dependency-closed 작업 집합에만 허용한다. 승인하지 않은 dependency를 필요한 작업이 참조하면 분리 계획을 다시 제시한다. 'A만 승인'을 전체 plan 허가로 처리하지 않는다. 일부 작업을 제거했어도 shared migration·공통 interface가 바뀌면 나머지 계획의 의미를 재검토한다.

## 9. 실행 전 원자 판정과 효과 경계

신뢰된 decision broker는 actor/purpose/subject/display/expiry/revocation을 확인한 후 기존 `TrustedApprovalReceipt`를 생성한다. 사람 응답 JSON은 receipt가 아니다. Action Broker는 매 효과 시작 직전에 receipt·scope·현재 policy·기대 candidate parent·budget·lease/fencing을 확인해 `ToolExecutionPermit`을 제한적으로 발급/소비한다.

`BEGIN IMMEDIATE → request 상태와 expected revision 검사 → 허가/거부 결정 기록 → permit/effect reservation과 outbox 기록 → COMMIT → effect dispatch` 순서다. DB commit 전 실제 외부 효과가 일어나면 안 된다. 같은 idempotency key의 같은 payload는 이전 receipt, 다른 payload는 `IDEMPOTENCY_CONFLICT`다.

control_revision과 telemetry sequence를 구분한다. 호출 이벤트 한 개가 추가됐다는 이유로 계획 승인 전체를 무효화하지 않는다. 반대로 사용자 철회·권한 변경은 telemetry 표시 변경이 아니라 control event이며 신규 dispatch를 차단한다.

파일·shell·MCP·서브에이전트·headless·ACP 모두 같은 강제 경로를 통과한다. 정책 확인 도구를 우회할 수 있는 raw shell이 같은 보호 디렉터리를 쓰면 governed가 아니다. 소유 OS 권한 또는 검증된 sandbox가 없으면 advisory로 명시하고 제품 평가 2-4 통과로 표시하지 않는다.

## 10. 범위 변경과 review invalidation

`ChangeImpact`는 변경된 requirement, source path, API, DB schema, permission, budget, test oracle, skill/tool inventory를 seed로 하여 reverse dependency closure를 구한다. 변경이 local implementation choice이며 사전 승인된 대안 집합 안에 있으면 결정 원장만 기록할 수 있다. 범위 확대나 acceptance 약화는 사람 재결정 대상이다.

진행률·문구·탐색 결과 정렬처럼 실행 의미와 무관한 변경은 plan subject를 바꾸지 않는다. 허용된 code result의 계보는 기록하지만 승인되지 않은 새 effect를 소급 허가하지 않는다. 영향 판정이 불가능하면 영향받을 수 있는 작업을 pause하고 계획을 다시 검토한다.

## 11. Interrupt·재시작·철회

LangGraph 공식 설명상 resume는 interrupt가 있는 node의 앞부분부터 다시 실행될 수 있다. 따라서 질문 표시 준비, 비용 예약, 외부 전송 등은 재실행 안전해야 한다. 한 node invocation은 하나의 pending decision에 대응하고 동일 decision_id/nonce를 재사용한다. 새 nonce로 같은 허가를 여러 번 발급하지 않는다. 평행 interrupt는 순서가 아니라 interrupt_id와 decision_id의 mapping으로 응답을 맞춘다. [공식 근거 NS73](../../reference/SOURCES.ko.md#ns73)

`interrupt()` 예외를 일반 오류로 삼켜 승인된 것으로 계속하지 않는다. 재질문은 상태·조건 edge로 수행하며 하나의 while loop에서 누적 interrupt와 외부 효과를 반복하지 않는다. checkpoint는 인증·권한 저장소가 아니다. resume 입력을 그대로 DB 승인 상태로 쓰지 않는다.

철회와 신규 효과 시작은 신뢰된 effect fence에서 직렬화한다. 철회 전 이미 dispatch한 효과는 `cancel_requested`로 관리하며 취소 확인 전 `cancelled_no_effect`라고 쓰지 않는다. 늦은 사용량·청구는 보존하고 stale 결과의 업무 적용만 차단한다. 결과가 불명확하면 reconciliation 후 재시도 여부를 결정한다. 사람 미응답 중 승인 expiry가 지나면 새 표시·결정이 필요하다.

## 12. 작업별 실행·테스트·리뷰와 최종 인수

작업은 `reserve → bind → run → collect → verify → independent review → settle`을 수행한다. expected TDD red를 기능 회귀나 나쁜 기억으로 자동 학습하지 않는다. code change가 끝났어도 실제 acceptance·리뷰·scope 검사가 끝나기 전 complete가 아니다. '테스트 파일 존재'나 `pytest --collect-only`는 테스트 실행이 아니다.

병렬 branch의 통합 결과는 새로운 artifact다. merge conflict를 고친 코드는 새 변경이고 merged source에서 회귀검사·필요 리뷰를 재수행한다. 통합 테스트가 실패하면 branch별 pass를 합산해 성공으로 표시하지 않는다.

인수 packet은 요구별 충족/미충족/미실행, 실제 명령·source digest, diff·한계·복구를 표시한다. 코드 작성, 최종 검토, 사용자 인수, source apply, commit, push, publish를 분리한다. 사용자가 별도 위임하지 않은 push/배포는 수행하지 않는다. 작업 경험은 승인된 source/effect 결과와 함께 Memory 후보로 연결하되 활동 기록을 능력 개선의 증거로 세지 않는다.

## 13. 구현할 API와 패키지 소유권

아래는 현재 제품 함수가 아니라 구현 계약이다. 입력 JSON은 경계에서 엄격하게 검사하고 내부 도메인 함수에는 typed object를 전달한다.

| 파일 (`deepagents_code/cyrano/` 기준) | 함수 | 입력·반환·오류 |
|---|---|---|
| `workflow/plans.py` | `build_review_subject(plan, requirements, snapshot) -> PlanReviewSubject` | immutable subject 생성; dangling ref·불명확 scope 거부 |
| `workflow/plan_checks.py` | `validate_plan(subject, inventory) -> PlanCheckReport` | cross-artifact 검사; 실패를 boolean 하나로 숨기지 않음 |
| `workflow/reviews.py` | `request_review(subject, reviewer_binding) -> ReviewRequest` | 작성자 실행과 reviewer 분리; immutable input |
| `workflow/reviews.py` | `resolve_finding(finding, response, evidence) -> FindingResolution` | 증거와 주체 검사; 중요한 미해결 자동 닫기 금지 |
| `workflow/decisions.py` | `present_decision(subject, purpose) -> DecisionRequest` | 표시 artifact 봉인; 사용자 권한 발급 아님 |
| `kernel/approvals.py` | `record_decision(request, response, trusted_actor) -> Receipt` | actor·nonce·display·revision·expiry CAS; 위조/중복 처리 |
| `workflow/changes.py` | `classify_change(old, new, dependencies) -> ChangeImpact` | 영향 closure와 invalidation set; unknown이면 pause |
| `kernel/actions.py` | `authorize_effect(action, current_state) -> ToolExecutionPermit` | 효과 직전 재검사·budget/fence 예약 |
| `workflow/settlement.py` | `assess_completion(candidate, evidence) -> CompletionDecision` | 실제 test·review·목적을 검증; no-change도 별도 처리 |
| `monitor/decisions.py` | `load_packet/submit_response` | 인증된 조회/쓰기 분리; UI callback 재전송·stale 처리 |

## 14. 필수 테스트와 실행 원칙

구체 사례는 `tests/acceptance/catalog.json`의 `PLAN-*`, `HUMAN-*`, `REVIEW-*`, `CHANGE-*`, `RESUME-*`, `CON-HIL-*`에 있다. 담당 WP09·WP03·WP10, 테스트 개발 TS04/TS05가 같은 case ID를 사용한다. case에는 전제·입력·실행·금지 효과·원시 증거·복구가 있다. schema fixture는 제품 평가 점수를 주지 않는다.

무효한 승인, 잘못된 actor, 다른 workspace, 만료·철회, display mismatch, 승인 직후 source 변경, 중복 클릭, API 직접 호출, shell/MCP/child 우회, DB full, outbox crash, 늦은 결과, 조건부 승인, 부분 승인, 필수 리뷰 실패, review limit, 무응답, 원본 drift, test 축소, source apply 실패를 필수 반례로 한다.

계획/HITL 비용과 사용자 개입도 측정하되 클릭 수 감소만으로 더 좋은 절차라 평가하지 않는다. false-ready·의도 위반·무승인 효과는 hard failure다. 승인 fatigue를 줄이려면 동일 scope의 설명을 명확하게 묶되 다른 권한 목적을 숨겨 결합하지 않는다.

## 15. 두 입력, 하나의 실행 권위

일반 대화에서 제안한 다음 작업과 모델이 생성한 DAG를 모두 `WorkUnitSpec`으로 정규화한다. 기존 kernel이 상태·권한을 판단하고 기존 workflow가 dispatch한다. 별도 Temporal/Dolt/Beads DB나 두 번째 LangGraph agent loop를 만들지 않는다. [LLMCompiler](../../reference/SOURCES.ko.md#ns64)의 planner/scheduler 분리는 참고하지만 임의 코드 실행을 허용하는 근거가 아니다.

## 16. WorkflowIR

허용 node kind는 `read`, `agent_task`, `verify`, `human_decision`, `join`, `apply_candidate`다. function name·import·eval·shell string을 IR의 제어 흐름으로 허용하지 않는다. 실제 shell은 이미 검증된 recipe ID와 arguments로 Broker에 요청한다.

각 노드는 id, dependencies, requirement_ids, acceptance_ids, input_artifact_refs, output_contract_id, scope_ref, resource_claims, retry_class, max_attempts, deadline, cost_cap, compensation_ref를 가진다. `human_decision`은 UI로 요청할 뿐 스스로 승인을 발급하지 않는다. `apply_candidate`에는 별도 적용 허가와 현재 snapshot 검사가 필요하다.

조건식은 literal/typed field access/eq/ne/and/or/not에 제한한다. field는 이미 settled된 조상 결과의 허용 필드만 참조한다. 실패를 숨기기 위해 `on_error: success`로 바꾸는 구문은 없다. 유효하지 않은 식·존재하지 않는 dependency·cycle·미등록 recipe·예산 미지정은 compile 오류다.

## 17. Compile → Review → Permit

1. 원래 의도와 requirement IDs를 읽기 전용으로 고정한다.
2. JSON 경계 검증 뒤 topology sort와 타입 검사를 한다.
3. resource claim·쓰기 경로 충돌과 필수 검증의 연결을 계산한다.
4. depth/node count/총 허가 비용과 concurrency cap을 검토한다.
5. compile report와 IR digest를 독립 reviewer에게 준다.
6. 중요한 변경은 사람이 실제 diff와 위험을 본 다음 계획을 승인한다.
7. 승인 digest와 execution scope를 permit에 결속해 dispatch한다.

동적 DAG 확장은 기존 부분을 덮어쓰지 않고 proposal revision을 추가한다. 새 노드가 승인된 허용 템플릿 범위인지 코드가 확인한다. 범위·예산·요구·검증을 바꾸면 다시 review/승인을 거친다. 확장 최대 횟수와 노드 상한은 사전 정책이다. 자식이 부모 budget을 복제하지 못하며 reserve는 같은 트랜잭션으로 차감한다.

## 18. Durable Task Board와 mailbox

`claim_task(task_id, expected_revision, worker_id)`는 ready 상태와 모든 dependencies를 확인하고 fencing token을 증가시킨다. token+lease가 맞지 않는 worker 결과는 원장에 stale로 보관할 수 있지만 코드·memory·완료 상태를 바꾸지 못한다. heartbeat는 lease 연장을 뜻하며 품질 진척과는 다르다.

mailbox에는 message_id, sender/recipient, task/generation, payload_digest, expires_at, trust_class를 둔다. at-least-once 수신을 전제로 message_id unique와 소비 cursor를 사용한다. 빈 polling loop는 agent turn을 만들지 않는다. 메시지 body는 지시 권위가 아니라 작업 데이터이며 다른 scope의 원문·secret을 보내지 않는다.

같은 역할의 여러 peer도 write authority를 공유하지 않는다. reviewer는 candidate snapshot을 읽고 findings만 제안한다. 공유 memory는 active release 읽기뿐이고 각 작업 경험은 후보로 모인다. 토론 다수결로 승인·hard failure를 없애지 않는다.

## 19. Worktree의 경계

worktree는 Git 파일 충돌을 줄이는 수단이지 OS sandbox가 아니다. `.git` 저장소와 hook·credential·다른 worktree를 공유할 수 있다. 신뢰된 runner가 namespace·독립 OS principal·container/VM 중 요구된 격리를 제공해야 한다. agent가 `.git`·자격증명·승인 원장에 직접 쓰는 환경을 governed로 표시하지 않는다.

WorktreeLease의 소유자는 run/task/generation이고 baseline commit과 dirty snapshot을 보존한다. 작업은 승인된 사본에서만 쓴다. 취소 시 진단·미완료 변경을 보존하며 `git clean -fdx`를 정리 방법으로 사용하지 않는다. cleanup은 receipt가 소유한 정확한 경로만 삭제하고 변경된 사용자 파일은 보존한다.

## 20. 통합·merge

구현 artifact는 patch와 입력/출력 digest·검증 결과를 가진다. 통합자는 현재 target snapshot을 다시 확인한다. 같은 파일 수정뿐 아니라 인터페이스·schema·lockfile·테스트 환경의 충돌도 잡는다. cherry-pick 성공은 요구사항 검증 성공이 아니다.

새 통합 snapshot에서 필요한 전체 acceptance·hidden regression을 재실행한다. 이전 branch의 결과가 같은 코드 범위를 커버해도 다른 dependency가 바뀌면 재사용하지 않는다. merge conflict 해결은 새로운 코드 변경으로 계획·리뷰 범위에 들어간다. publish/push는 별도 권한이다.

## 21. 오류와 완료

`DAG_CYCLE`, `UNBOUND_REQUIREMENT`, `RESOURCE_CONFLICT`, `BUDGET_UNBOUND`, `PERMIT_STALE`, `LEASE_LOST`, `RESULT_STALE`, `UNKNOWN_EFFECT`, `MERGE_REVALIDATION_REQUIRED`를 구분한다. 테스트 실패를 controller 실패와 혼합하지 않는다. 부모 완료는 모든 필수 child가 verified 또는 승인된 비적용 상태일 때만 가능하다. 자식 중단을 침묵으로 무시하지 않는다.

## 22. Inception 소스에서 추가로 확인한 비이식 조건

[Inception runtime/journal](../../reference/SOURCES.ko.md#ns71)을 실제 확인했다. generated script라는 입력 아이디어는 채택하지만 별도 Flue runtime은 설치하지 않는다. 필수 child의 null 결과를 filter하여 전체 성공으로 만들지 않는다. journal 쓰기가 실패했는데 재개 가능하다고 표시하지 않는다. 이미지는 개수 대신 실제 내용/변환 digest, schema는 함수 이름이나 present 상수 대신 검증된 전체 canonical schema digest에 결속한다. immutable source, 환경, 도구 inventory, scope, 허가, generation이 없는 result memo는 code task resume의 근거가 아니다.
