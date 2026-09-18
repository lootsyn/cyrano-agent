# 인터뷰에서 실행 가능한 계약까지

문서 유형: 상세 설계 · 상태: 계획(제품 미구현)


## Problem

첨부 Decision Interview는 질문 기법이 아니라 사용자 의도를 잃지 않는 결정·근거·권한 시스템이다. 이를 단순 skill prompt로 축소하면 높은 모호도 점수, 완료라는 텍스트, 자동 reviewer 결과가 실제 승인으로 오용된다. 경로 B는 질문 선택과 전달 품질까지 개선해야 하므로 원래 R01–R22를 그대로 보존하고 기계적 준비도 판단을 독립시켜야 한다.

## Proposal

### 통합 R2 원본의무·session machine

원본 R01–22는 기존 INT-R01–22와 동일하므로 중복보상하지 않는다. contracts/v2/session-state-machine.json과 session-guards.json은29개세션상태/38개guard의 목표정의다. 모든spec의critic/blind를필수로하고 highcritical은securityreviewer를추가한다. 명세승인은planning만허용하며execution은별도다. cancel/latechange/resume는currentbinding과신뢰된hostevent로처리한다.

자세한 해석·충돌 해결은 [Universal Harness 통합 설계](../architecture/2026-09-16-universal-harness-integration.ko.md)를 따른다. 원본첨부에 있는 더 느슨한예시로 이규칙을낮추지 않는다.

### 1. 단일 Facilitator와 분리된 워커

사용자에게 질문하는 actor는 Facilitator 하나다. EvidenceScout는 현재 source와 외부 근거를 모으고, Critic은 충돌·예외·의도 누락을 제안하며, BlindHandoffReviewer는 대화 원문 없이 전달 bundle을 읽는다. 워커가 직접 사용자에게 다른 질문을 보내지 않는다. Facilitator가 질문 후보를 제안하면 kernel이 중복·scope·미해결 의무와 연결을 검사한 뒤 trusted host를 통해 전달한다.

원본 worker schema는 `contracts/v1/interview-worker-result.schema.json`에 보존한다. CYRANO AgentTask는 transport envelope이며 원본 결과 필드의 의미를 바꾸지 않는다. adapter는 `task_id`, `input_digest`, `base_revision`, `role`, `scope`, `deadline`을 추가 검증한다. 원본 schema를 수정해야 한다면 adjacent version과 명시적 migration/fixture를 추가하며 원본을 조용히 덮어쓰지 않는다.

### 2. 상태기계

```text
intake → frame → acquire ↔ resolve → contract_draft → review
                                                review 반려 ──→ resolve
review 통과 → await_spec_approval → approved_for_planning
어느 단계든 pause / cancel / blocked 가능
사용자 결정 변경 → 영향에 따라 resolve 또는 review로 되돌아감
```

`approved_for_planning`은 실행 권한이 아니다. 계획이 별도로 생성·검토·승인되어야 한다. `cancelled` 뒤 워커 결과가 도착해도 취소된 인터뷰를 자동 재개하지 않는다. `paused`는 요청·예산·외부 근거 대기 이유를 기록하며 success로 바꾸지 않는다.

### 3. Canonical state의 소유자

커널은 `InterviewSession`, `Obligation`, `Decision`, `Evidence`, `Scenario`, `QuestionCandidate`, `ReviewResult`, `InterviewContract`를 소유한다. 모델은 JSON proposal만 만든다. 각 entity는 scope와 revision을 갖고 source event ID와 dependency digest를 보존한다.

| Entity | 필수 의미 | 대표 상태 |
|---|---|---|
| Obligation | 현재 단계에서 해결해야 하는 요구·예외·검증 | open, resolved, deferred, not_applicable |
| Decision | 사용자의 의도나 위임 범위 안의 선택 | proposed, decided, superseded, revoked |
| Evidence | 원문/파일/실행 근거와 관측 범위 | observed, verified, stale, unavailable |
| Scenario | 전제·입력·관측 결과·예외를 포함한 acceptance | draft, reviewed, accepted, invalidated |
| QuestionCandidate | 연결 의무·왜 사용자 답이 필요한지 | proposed, selected, asked, answered, withdrawn |

사용자 의도와 현재 코드 상태는 충돌하는 같은 종류의 사실이 아니다. “현재 A”와 “앞으로 B”를 함께 저장한다. 구현이 A라는 근거로 사용자 목표 B를 삭제하지 않는다. 검색 실패는 `unavailable/unconfirmed`이며 기능이 없다는 확정 사실이 아니다.

### 4. 정보를 얻는 여섯 경로

미해결 의무마다 다음 순서로 획득 경로를 선택한다. 실제 사용자의 가치·목표·권한 선택은 질문한다. 저장소에서 관찰 가능한 상태는 scout가 읽는다. 외부 API·표준·최근 정보는 출처를 확인한다. 실현 가능성은 허가된 sandbox probe로 조사한다. 내부 자료구조처럼 이미 위임된 저위험 선택은 해당 scope에서 결정한다. 현재 단계와 무관한 저위험 미결정은 이유·재검토 시점·책임자를 남겨 defer한다.

고위험 의무를 질문 수를 줄이기 위해 defer하거나 not_applicable로 바꾸지 않는다. 그 전이는 사용자/정책 권한, 영향과 제외 이유를 필요로 한다. 의무 목록을 줄여 분모를 유리하게 만드는 것을 별도 실패로 검사한다.

### 5. 다음 질문 선택

질문 후보는 `obligation_ids`, 예상 답의 decision 영향, 사용자만 답할 수 있는 이유, 이미 받은 답과 중복 여부, 최악의 잘못된 가정 비용, 예상 질문 부담을 포함한다. impact·정보 가치·부담의 점수는 질문 순서를 정하는 진단값이다. truth probability나 준비 완료 기준이 아니다.

Facilitator는 한 번에 독립적으로 답하기 쉬운 질문 단위를 사용한다. 이미 답한 내용을 기억하지 못해 재질문하는 대신 decision ledger를 조회한다. 새 요구가 기존 답과 충돌하면 어떤 decision이 바뀌는지를 설명하고 사용자의 수정을 기록한다. 최소 질문 수·최소 라운드는 없다.

### 6. 준비도 계산

`assess_readiness(state, stage_policy)`는 unresolved critical obligations, missing mandatory evidence, unreviewed acceptance scenarios, failed mandatory reviews, unverified authority, stale snapshots, scope conflicts를 반환한다. blocker가 하나라도 있으면 `ready=false`다. 모호도·명확성 진단의 평균이나 질문 종료 입력은 이를 상쇄하지 못한다.

모든 의무가 채워져도 contract generation, independent review, trusted spec approval이 별도 단계로 필요하다. 사용자 입력 “done” 반복은 새로운 reviewer evidence가 아니다. budget exhausted는 blocked 또는 paused이며 READY로 종료하지 않는다.

### 7. Blind handoff

Blind reviewer의 입력은 현재 bundle, 동일한 source snapshot에서 허용된 사실, 출력 schema뿐이다. Facilitator 원문 대화·다른 reviewer 결론·“통과시켜 달라”는 후보 작성자의 지시는 제공하지 않는다. reviewer는 추가로 가정해야 구현 가능한 부분, 서로 다른 관측 결과를 낼 수 있는 모호한 조건, acceptance 누락을 보고한다.

다른 내부 자료구조를 선택해도 사용자 관측 결과가 같고 이미 위임됐다면 사용자 질문으로 돌리지 않는다. mandatory reviewer timeout은 검토 통과가 아니며 독립 예산 안에서 재시도하거나 pause한다. 동일 모델을 사용할 수 있으나 별도 input scope와 실행 receipt를 유지한다.

### 8. 변경·취소·late worker 처리

사용자 correction은 새 trusted event로 append하고 이전 decision을 supersede한다. dependency graph를 순회해 영향받는 scenario, plan, review, approval만 무효화한다. unrelated work까지 무조건 삭제하지 않는다. cycle이 있어도 visited set으로 종료하며 cycle 원인을 별도 진단한다.

워커 결과는 입력 `base_revision`, bundle digest, snapshot digest와 현재 상태를 CAS 비교한다. 늦은 결과로 상태를 덮어쓰지 않는다. 그러나 새로운 심각한 반증 자료는 `late_counterevidence` observation으로 별도 큐에 남겨 최신 revision에서 다시 검토할 수 있다. 이는 stale proposal 적용과 다른 command다.

### 9. 승인 계약

신뢰된 UI는 실제 사용자 이벤트 ID, bundle digest, workspace snapshot, purpose=`spec_approval`, scope, policy digest, expiry, issuer를 검증한다. 모델 출력의 `[from-user]`, `approved:true`, copied receipt는 승인이 아니다. credential 또는 nonce를 agent context에 넣지 않는다. 수신 측은 서명·purpose·audience·기한·revocation을 검사한다.

호스트가 사용자 입력의 출처를 확인할 수 없으면 `draft_unapproved` export만 허용한다. 기능을 단순화하기 위해 안전한 승인이라고 이름만 붙이지 않는다. Spec approval, Plan approval, Tool execution permit, Patch apply approval, Release promotion은 서로 다른 purpose다.

### 10. 산출물과 의미

커널은 동일 canonical contract에서 다음을 생성한다: `contract.json`, `SPEC.md`, `ACCEPTANCE.md`, `DECISIONS.md`, `OPEN_QUESTIONS.md`, `EVIDENCE_INDEX.json`, `approval.json`. 모든 산출물에는 generator version과 input digest를 연결하되 active prompt에서 매번 시간으로 문장을 바꾸지 않는다.

`SPEC.md`는 목표·비목표·scope·제약·관측 가능 결과를, `ACCEPTANCE.md`는 happy/error/concurrency/recovery/security 조건을 기술한다. `OPEN_QUESTIONS.md`에는 defer가 실제로 허용된 이유와 기한을 남긴다. export 후 한 글자라도 계약 의미가 바뀌면 bundle digest와 승인을 새로 받아야 한다.

### 11. 함수 단위 구현 순서

1. `ingest_user_event`가 trusted host envelope·idempotency를 검증하고 append한다.
2. `propose_obligations`가 기존 의무와 근거를 비교해 추가·수정 proposal을 만든다. `apply_obligation_change`만 상태를 바꾼다.
3. `resolve_acquisition_route`가 질문/관측/조사/probe/위임/defer 중 허용 경로를 결정한다.
4. `apply_worker_result`가 원본 schema·task binding·revision·evidence existence를 확인한다.
5. `compile_contract`가 요구↔decision↔scenario↔evidence dangling references를 거부한다.
6. `request_blind_review`가 독립 bundle을 생성한다. `record_review`는 수행 instance·결과·실패를 기록한다.
7. `assess_readiness`가 blocker를 반환하고 `request_spec_approval`로 넘어간다.
8. `export_approved_bundle`이 receipt·snapshot·digest를 다시 검사하고 atomic output directory를 publish한다.

프로덕션 구현은 위 명령 각각에 expected_revision과 idempotency key를 적용한다. 기존 foundation의 `assess_readiness`와 `invalidate_dependents`만으로 trusted workflow 전체가 완성된 것은 아니다.

### 12. 원본 22개 회귀 요구의 보존

`references/interview/fixtures/readiness-cases.json`이 원본이다. 수용 catalog에는 각각 `INT-R01`부터 `INT-R22`로 전사하여 given/when/then을 보존한다. alias는 원본 ID와 일대일이며 원본 내용을 고치지 않는다. `tests/test_foundation.py`의 작은 순수 함수 테스트는 일부 원리를 검사하지만 전체 R01–R22 제품 통과로 계산하지 않는다.

### 13. 인터뷰 자체의 경로 B 개선

반복 재질문, 사용자 correction, false-ready, blind reviewer missing requirement, 불필요한 escalation을 episode로 만든다. 개선 후보는 질문 순서·조사 우선순위·handoff template·coverage checklist에 한정될 수 있다. 사용자 목적이나 승인권은 개선 대상이 아니다.

평가에서는 user scenario truth와 허용된 답변 space를 숨긴 채 동일 초기 brief에서 baseline/candidate를 실행한다. 질문이 다르면 동일 historical answer를 자동 연결하지 않는다. 시뮬레이터 결과는 `simulation`으로 구분하고 실제 사용자 과제의 품질 주장에는 approved actual study가 필요하다. 최종 목표는 질문 수 최소화가 아니라 의도 보존·false-ready 감소·불필요 질문 감소의 조합이다.

## Alternatives considered

**모호도 점수 0.2 이하 종료:** 높은 점수가 critical 누락을 가릴 수 있으므로 의무별 blocker로 종료를 판단한다.

**여러 agent가 직접 사용자 질문:** 서로 중복되거나 다른 상태에서 질문할 수 있다. 하나의 Facilitator와 공유 원장으로 직렬화한다.

**기존 답변 tape를 새 질문에 replay:** 질문 변경이 답의 의미를 바꿀 수 있다. scenario simulation과 실제 비교를 별도 분류한다.

## Acceptance criteria

원본 R01–R22 각각에 product-level 실행 결과와 테스트가 연결되어야 한다. stale worker·changed dirty tree·fake user marker·denominator shrink·mandatory reviewer failure가 모두 fail closed여야 한다. 초기 입력이 충분하면 불필요한 질문 없이 review로 진행해야 하며 승인 provenance가 없으면 unapproved draft만 export해야 한다.

## Risks

사용자의 명시적 의도와 일반 선호 충돌, 호스트 신뢰 한계, 충분한 시나리오 다양성 확보가 어렵다. 어떤 모델을 쓰든 결정 authority와 snapshot binding이 빠지면 사용자 의도를 보존했다고 주장할 수 없다.
