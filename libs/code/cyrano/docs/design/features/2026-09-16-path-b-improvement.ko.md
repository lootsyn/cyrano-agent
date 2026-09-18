# 경로 B: 지식·절차·코드 개선 전체 구현

문서 유형: 상세 설계 · 상태: 계획(제품 미구현)


## Problem

탐색 branch를 선택하는 정책만 개선하면 인터뷰 질문, 계획 품질, 잘못된 memory, 불필요한 context, 부실한 검증 recipe, 결함 있는 하네스 코드가 그대로 남는다. 경로 B는 이들 내용을 개선해야 하지만 실행 입력을 바꾸므로 과거 결과를 그대로 재생해 개선 효과를 입증할 수 없다. 지침의 작은 변경도 권한·평가 기준·사용자 의도에 영향을 줄 수 있어 변경 표면과 평가·배포 경로를 구체적으로 분리해야 한다.

## Proposal

### 통합 R2 학습 신호·권한·품질

learning-policy의 enabled=false를유지한다. terminal-event/job outbox와 논리dedupe는업무성공과학습성공을분리한다. expectedTDDred/정상deny/userchange/envfailure를일반실패와분리한다. B변경에는실제paired평가가필수이며source설계의generic학습으로이를완화하지않는다. quality79/72, requiredreview, retention삭제와legacy승인전환금지는 INT-01–24를따른다.

자세한 해석·충돌 해결은 [Universal Harness 통합 설계](../architecture/2026-09-16-universal-harness-integration.ko.md)를 따른다. 원본첨부에 있는 더 느슨한예시로 이규칙을낮추지 않는다.

### 1. 경로 B의 정의와 완료 의미

경로 B는 **다음 실행에 전달되는 지식, 절차, context, 도구 동작 또는 runtime 구현을 바꾸는 개선 경로**다. 모델 가중치 학습을 요구하지 않으며 모델 이름별 profile을 만들지 않는다. 제안만 저장하는 관측 모드도 지원하지만 최종 제품은 후보 생성→독립 분류→실제 평가→승인→배포→후속 관측→철회를 모두 구현해야 한다.

완료는 “새 skill 파일 생성”이 아니다. 특정 scope에서 왜 필요한지, 무엇이 바뀌었는지, 어떤 실제 실행 조건으로 검증했는지, 누가 승인했는지, 다음 run에 어떤 release로 적용됐는지, 회귀 시 어디로 돌아갈지 증거가 연결된 상태다. schema의 `requires_actual_execution=true`는 검증을 요구한다는 뜻이지 이미 실행되었다는 뜻이 아니다.

### 2. 개선 표면별 계약

| 표면 | 허용 변경의 예 | 기본 평가 | 배포 단위 | 자동화 상한 |
|---|---|---|---|---|
| semantic_memory | snapshot에 근거한 프로젝트 사실 수정 | 사실 재검증 + 영향을 받는 작업 비교 | scoped MemoryRelease | 근거 있는 관측 fact 승인 정책까지; scope 확장 불가 |
| procedural_skill | 검증·리뷰 순서, 조건부 절차 | 실제 task baseline/candidate + 반례 | SkillRelease | 좁은 사전 위임 범위 내만 |
| skill_code | skill script·helper·dependency | 정적·보안·unit·실제 task·clean install | 코드 포함 SkillRelease | 일반 markdown과 별도, 사람 승인 기본 |
| interview_strategy | 질문 후보 선택·handoff 구성 | R01–R22 + scenario + 실제 사용자 조건 | InterviewStrategyRelease | 의무/승인 조건 완화 금지 |
| planning_strategy | WorkUnit 분해·의존성·검증 연결 | DAG·scope 회귀 + 실제 구현 작업 | PlanningStrategyRelease | 승인·scope 삭제 금지 |
| review_strategy | 누락 검사·독립 reviewer 입력 | planted faults + clean tasks + 실제 review | ReviewStrategyRelease | 자기 점수로 자신 승인 금지 |
| context_config | 순서·budget·offload·요약·recall | 실제 정확성 + 사용량·지연 + cache 측정 | ContextRelease | protected context 삭제 불가 |
| verification_recipe | 테스트 명령·준비·대상 선택 | 고의 오류 탐지·오탐 + clean sandbox | RecipeRelease | evaluator 기준 삭제 금지 |
| workflow_config | bounded retry·delegation 조건 | 재시도·복구·취소·실제 task | WorkflowRelease | 권한·예산 상한 확대 금지 |
| extension_code_proposal | adapter·kernel·기억 저장 bug fix | 전체 코드 파이프라인 + 실제 통합 | 새 wheel/runtime release | 운영자가 review·승인·재시작 |

`exploration_policy`도 실행 입력 의미를 바꾸는 경우 B다. 파일이 policy 폴더에 있다는 이유만으로 A로 분류하지 않는다. schema·worker prompt·tool description·summary 선택이 바뀌면 모델이 받는 입력이 달라진다.

### 3. 금지 표면과 정책 변경 요청

candidate가 approval trust root, credentials, scope ACL, sandbox 제한, audit/redaction, judge·hidden acceptance, promotion threshold, 허용 비용 상한을 수정하려 하면 `protected_change`다. 자동 학습 workflow로 배포하지 않고 별도의 사람이 시작한 정책 변경 workflow로 넘긴다. “승인 때문에 느리다”, “검증이 자주 실패한다”는 이유로 해당 보호를 없애지 않는다.

경로 검사는 realpath·symlink·case normalization·archive traversal·모듈 의존성·실행 resource를 포함해야 한다. protected 파일을 import하는 unprotected helper를 바꾸는 경우도 영향 분석한다. foundation `classify()`는 보수적 순수 함수의 예제이며 완전한 filesystem 보안 검사 구현으로 간주하지 않는다.

### 4. Observation과 Outcome

Episode Builder는 terminal run event와 artifact·tool result·review result·user correction을 묶는다. 각 observation은 `expected_outcome`, `actual_outcome`, phase, expected failure 여부, environment error 여부, 사용자 요구 변경 여부, 실행 receipt를 가진다.

다음 사건은 자동으로 학습 실패가 아니다: TDD의 의도적 red, 올바른 권한 거부, 사용자의 취소, 한 번의 retryable 네트워크 오류, 합법적인 동일 파일 재독해, 계획된 negative test. 반대로 비밀 유출·무승인 실행 같은 중대 사건은 반복 빈도를 기다리지 않고 incident와 revoke를 발동한다.

Model self-report와 runner observation을 별도 보관한다. 모델이 “이 skill을 적용했다”고 말해도 실제 plan diff·tool call·test artifact에서 반영이 확인되지 않으면 self-report일 뿐이다. 미완료/취소 작업도 분모에서 사라지지 않게 상태와 원인을 기록한다.

### 5. 학습 대상 선택과 원인 가설

Analyst는 episode를 failure family·task family·component·phase별로 묶는다. 조회 전에 scope ACL과 개인정보 정책을 적용한다. 사용자별 사실을 다른 고객의 전역 skill 학습 근거로 자동 전송하지 않는다. 먼저 중복 사건인지, 같은 환경 장애가 반복된 것인지, 같은 task 반복이 독립 표본으로 오인되고 있는지 검사한다.

가설 형식은 관측 패턴, 기제 설명, 대안 원인, 예상 영향을 받는 scope, 반례, 반증 가능한 기대 변화, 필요한 추가 근거다. 단일 사건으로 범용 규칙을 확정하지 않는다. 큰 피해를 막는 임시 차단과 일반 성능 개선은 별도 권한·상태로 처리한다.

예: “pytest 실패가 많다”가 아니라 “migration을 새 sandbox에 적용하지 않아 fixture 생성이 실패했고, migration 적용 뒤 동일 snapshot에서 수집이 성공했다”처럼 관측 단계와 환경을 연결한다. 아직 원인을 확정하지 못하면 `hypothesis`이며 active fact로 저장하지 않는다.

### 6. LearningWorkPlan과 독립 사전 리뷰

Candidate 생성 전에 학습 작업 계획을 만든다. 필수 항목은 목표 표면, episode IDs, 가설·대안 설명, exact scope, patch 작성 허용 경로, baseline release, 기대 효과, 비열등성 범위, 반례, evaluation split manifest, independent reviewer, max attempts·token/금액·시간 예산, rollback 대상이다.

ExperimentReviewer는 후보 작성자와 별도 instance로 계획을 검토한다. 질문은 “좋은 아이디어인가”뿐 아니라 “무엇이 실패하면 거부할 것인가”, “숨은 정답에 접근하는가”, “평가 비용이 관측된 문제보다 큰가”, “권한·사용자 의도·분모가 바뀌는가”다. 검토 결과는 `approved_for_experiment`이며 release promotion 승인이 아니다.

새 구현이 아직 없는 초기 상태에서 reviewer prompt만으로 승인을 대체하지 않는다. 커널은 실제 검토 실행 receipt와 trusted experiment permit이 없으면 paid evaluator를 dispatch하지 않는다. 예산 0인 기본 설정은 실제 호출을 막는다.

### 7. CandidateProposal 생성

Author는 baseline artifact의 immutable copy에서 diff를 만든다. 한 candidate는 기본적으로 한 원인 가설과 최소 변경을 가진다. 여러 surface를 묶어야 한다면 왜 원자적 bundle이 필요한지, 각 부분의 ablation을 어떻게 할지 기록한다. 서로 독립적인 개선을 한꺼번에 배포해 어떤 부분이 효과를 냈는지 모르게 하지 않는다.

필수 필드는 `id`, `parent_release_digest`, `surface`, `artifact_digest`, `patch_paths`, `patch_digest`, `scope`, `evidence_refs`, `hypothesis`, `alternative_explanations`, `expected_effect`, `risks`, `learning_work_plan_digest`, `rollback_release_digest`, `meta_depth`, `status`다. 이 JSON은 제안이며 approve/promote field를 모델이 임의 지정해도 상태를 바꿀 수 없다.

빈 diff, unchanged digest, 동작을 설명하지 않는 거대한 재작성, 근거 없는 전역화는 거부하거나 inconclusive로 유지한다. generated 문서만 바꾸고 canonical skill 원본을 바꾸지 않은 경우 실제 변경 표면을 재분류한다. 문서와 code의 내용이 충돌하면 둘 중 하나를 몰래 선택하지 않고 같은 설계 변경에서 정합화한다.

### 8. Independent ImpactClassifier

Classifier는 Author가 선언한 route를 신뢰하지 않고 artifact diff, schema 변화, tool definitions, imports, skill executable resources, memory projection, context manifest의 dependency graph를 계산한다.

```text
protected owner 또는 그 권한/판정 의존성 변경
    → manual_policy_change, 자동 평가·승격 경로 차단
실행 입력 동일성을 증명한 bounded scheduling IR 변경만
    → A, replay 선별 + 실제 최종 비교
그 외 변경 또는 불명확
    → B, 실제 baseline/candidate 비교
```

classification receipt에는 검사기 version, baseline·candidate digest, 의존성 manifest, 누락·unknown, 이유를 남긴다. classifier가 검사하지 못한 file type이 있으면 “정적 검사 통과” 대신 `unsupported_artifact`로 보류한다. 기준 threshold를 후보가 바꾸고 그 기준으로 자기 개선을 평가하지 못한다.

### 9. Knowledge lane: 프로젝트 사실과 선호

관측 fact는 먼저 `observed`로 저장하고 source digest·근거·scope를 연결한다. 예를 들어 현재 파일에서 확인한 test command는 해당 snapshot 사실이다. 환경이 바뀌면 stale가 된다. dependency hash가 달라지면 TTL이 남아 있어도 active guidance로 쓰지 않는다.

명시적 사용자 선호 변경은 trusted user event가 권위다. 사용자 선호를 만족시키는지 확인하는데 통계적 개선 실험을 강요하지 않지만, 그 선호를 다른 사용자에게 일반화하거나 자동 behavioral rule로 승격하지 않는다. observation 검증·선호 authority와 “이 memory로 작업 성능이 좋아졌다”는 주장은 별개다.

적극 Recall은 intake, plan, implementation, verify 단계마다 current scope와 phase를 query에 담아 수행한다. index·cache가 후보 memory를 active처럼 돌려주지 않도록 status filter를 service 단계에서 적용한다. 비교 평가에서는 memory on/off 또는 old/new를 같은 task 조건에서 실행하고 의도·사실 오류·재작업·기억의 실제 적용을 측정한다.

삭제·정정은 active projection, FTS/vector index, query cache, summary dependencies, export를 추적해 무효화한다. 원문을 지웠는데 요약에 민감 내용이 남는 경우를 테스트한다. audit는 최소 tombstone만 보존하고 법적 보존 판단은 별도 운영 정책을 따른다.

### 10. Procedural lane: skill와 검증 recipe

skill 후보는 trigger, 적용 범위, 단계, 결과 schema, 중단·escalation 조건, 검증 기준, negative applicability를 모두 담는다. “항상 먼저 테스트하라”처럼 이미 공통 규칙에 있는 내용을 반복 추가해 context를 비대하게 만들지 않는다. 기존 skill과 겹치면 병합·참조·좁은 조건 중 하나를 선택한다.

정적 검사는 frontmatter, description budget, ID 중복, reference 존재, relative path escape, 금지 명령, executable 분류, scope, raw digest, instructions와 output contract 정합성을 검사한다. 정책상 허용되는 자연어인지 여부는 검토를 포함하되 prompt-only 검사로 실행 보안을 보장하지 않는다.

평가는 적용해야 하는 positive tasks, 적용하면 안 되는 negative tasks, 정상 코드, 의도적으로 결함을 심은 코드, 복구·취소 상황을 포함한다. recipe가 테스트를 더 적게 실행해 빨라졌다면 검출률·관련 기능 correctness가 유지되는지 확인한다. 실패 테스트 삭제·xfail 남용·catch-all 성공 처리·expected output 변경은 별도 tamper 검사 대상이다.

native loader에서 metadata만 읽고 본문을 불러오지 않은 후보는 skill 효과를 평가한 것으로 세지 않는다. `selected`, `loaded`, `injected`, `applied`, `verified_effect` 이벤트를 구분한다. 캐시 적중이나 읽기 횟수 증가는 skill 품질의 대리 목표가 아니다.

### 11. Interview·Planning·Review lane

인터뷰 개선은 중요 누락, false-ready, 사용자 의도 위반, 불필요 재질문, blind handoff gap을 지표로 사용한다. 기존 답 tape를 다른 질문에 그대로 사용하지 않는다. 시나리오 시뮬레이터 성능과 실제 사용자 관측을 분리한다. R01–R22를 단 한 개도 삭제하지 않는다.

계획 개선은 requirement→WorkUnit→acceptance traceability, DAG cycles, conflict paths, 누락된 setup·rollback·dispatcher 작업, 계획 후 재작업을 확인한다. 작업 수를 줄이는 것만으로 점수를 올리지 않는다. 계획 approval을 건너뛰는 후보는 보호 위반이다.

Review 개선은 seeded defects 검출, 정상 변경의 false-block, 불필요한 다른 모델 호출, 핵심 보안·의도 누락을 비교한다. Author의 설명만 읽어 동의하는 방식과 independent blind evidence review를 구분한다. reviewer 수 증가를 품질 개선으로 자동 간주하지 않는다.

### 12. Context·Workflow lane

Context 후보는 stable prefix, role prompt, skill catalogue, recall ranking, summary selection, artifact offload 위치를 바꿀 수 있다. compiler의 결정성과 native binding은 정적·통합 검사를, 효과는 실제 task 평가를 요구한다. artifact reference가 모델 도구로 회수 가능한지 검증하고 중요한 의무·승인·사용자 원문·검증 실패를 요약으로 지우지 않는다.

Workflow 후보는 bounded retry, subagent dispatch, phase transition의 비보호 매개변수만 바꾼다. max cost·sandbox 범위·mandatory review·approval 조건은 learning config로 넓힐 수 없다. 올바른 거부를 실패율로 계산해서 승인 회피가 보상받지 않게 outcome taxonomy를 적용한다.

### 13. Code lane: runtime과 skill executable

코드 후보는 현재 운영 runtime을 변경하지 않고 이 dcode checkout의 별도 승인된 Cyrano source snapshot에 patch한다. 동일한 전체 개발 workflow를 거친다: 요구·계획·독립 계획 리뷰 → scoped implementation → unit/type/lint/security → clean wheel build → 설치 smoke → dcode 통합 → 실제 paired task → code review → 운영자 승인 → 새 runtime install → 새 process/epoch 전환.

코드에는 eval·exec·shell wrapping·path resolution·RPC auth·lifecycle·migrations에 대한 추가 검토가 필요하다. pyproject/uv.lock 변경은 코드 변경이며 dependency provenance와 clean environment 설치를 확인한다. 모델이 lock 파일 텍스트를 임의 편집해 resolver를 통과한 것처럼 만들지 못한다.

새 wheel의 hash와 resolved dependency manifest를 release에 고정한다. 운영 agent가 wheel 저장소·승인키·active pointer를 직접 쓰지 못한다. import-time network/worker 시작과 현재 `extension.py` 덮어쓰기, `importlib.reload`로 운영 코드를 바꾸는 기능은 금지한다.

DB schema 변경은 기존 코드 rollback과 별개다. forward-only migration 후 old release가 새 schema를 읽지 못하면 단순 pointer rollback을 수행하지 않는다. backward-compatible expand/contract, 운영자 승인 restore, forward fix 중 사전 계획한 경로를 사용한다. restore의 데이터 손실 범위와 진행 중 작업 상태를 명시한다.

### 14. 실제 비교 실행 절차

각 baseline/candidate pair는 같은 task specification, initial source snapshot, runtime(코드 후보는 의도한 변경 부분만 차이), model·endpoint, tool inventory, environment, evaluator version, budget, 허용된 seed 조건을 사용한다. 모델이 seed를 지원하지 않으면 unseeded로 기록하며 결정적 비교라고 주장하지 않는다. 순서 효과를 줄이도록 pair 순서를 랜덤화하고 실행 전 seed/order manifest를 봉인한다.

동일 repo family·issue 변형·인접 commit·대화 변형은 split을 넘지 않는다. 성공한 task만 모아 학습하지 않으며 취소·환경 오류·timeout 처리는 preregistered policy를 따른다. 비용이 불명확한 API 응답은 0으로 넣지 않고 unknown budget risk로 처리한다.

개발 세트는 후보 수정에 활용할 수 있다. holdout은 접근 횟수를 제한하고 상세 정답을 Author에게 주지 않는다. 최종 sealed set은 별도 evaluator principal만 접근한다. 같은 holdout 점수를 계속 보고 후보를 튜닝하면 새로운 blind test처럼 보고하지 않는다.

### 15. 판정과 상태 전이

```text
proposed → static_validated → evaluating → evaluated → reviewed
  → await_approval → promoted
어느 검증 단계든 rejected / inconclusive
승격 뒤 revoked (안전) 또는 rollback 대상 release로 전환
```

기준은 safety hard gate → correctness/intent/noninferiority → 비용·지연·상대적 효율 → independent review → authority다. `eligible_for_review`는 gate의 계산 결과이지 promote 권한이 아니다. 실제 실행 receipt가 없으면 replay 점수가 아무리 높아도 승격하지 않는다.

표본 부족, 방향 불일치, scope 밖 일반화, 승인 누락, baseline 이동은 각각 다른 원인으로 표시한다. 비교 중 baseline이 바뀌면 candidate를 rebase하고 영향을 받는 실험을 다시 수행한다. 예전 baseline에서 얻은 효과를 새 baseline에 그대로 붙이지 않는다.

### 16. 배포·canary·rollback

Release manifest는 정책/skill/memory/context/runtime/recipe artifact의 전체 조합과 parent digest, evaluation·review·approval refs를 가진다. 모든 파일을 쓰고 hash를 검증한 뒤 `active(scope)` pointer를 CAS로 한 번 바꾼다. 파일 하나씩 덮어써 서로 다른 release가 섞이지 않게 한다.

canary는 승인된 새 run만 대상으로 deterministic assignment한다. 기본 비율은 0이고 운영자가 scope·조건·정지 기준을 승인한 후 활성화한다. canary 중에도 mandatory acceptance·보안은 느슨해지지 않는다. 중대한 regression은 신규 dispatch 중단, 영향 run 식별, release revoke/pause, 안전한 이전 release로 전환한다.

하네스 rollback은 사용자 코드 원복이 아니다. 이미 적용된 source patch의 영향은 별도 원본 반영/복구 허가로 처리한다. memory release가 잘못된 지침을 주었다면 그 memory에 의존한 계획·산출물을 추적해서 재검토 큐에 올린다.

### 17. 재귀 폭주와 개선 비용

terminal 업무 event를 저장하는 transaction에서 outbox job을 생성한다. middleware callback 안에서 LLM reflection을 다시 호출하지 않는다. job key는 `(run_id, terminal_event_id, learning_policy_digest)`다. worker는 max attempts, deadline, cancellation, lease, fencing token을 갖는다. 외부 호출 outcome이 불명확하면 reconciliation 없이 재청구되는 재시도를 하지 않는다.

`meta_depth=0`은 업무 경험, `meta_depth=1`은 그 경험의 학습·평가 작업이다. 기본 정책은 depth1 작업에서 다시 자동 개선 cycle을 만들지 않는다. 학습 엔진 자체 개선이 필요하면 사람이 승인한 별도 개발 task로 제출한다. 자동 학습 실패가 이미 검증된 사용자 코드 결과를 실패로 바꾸지는 않지만 “학습 완료”라고 표시해서도 안 된다.

총 비용은 업무 + 후보 작성 + replay + 실제 평가 + reviewer + 저장/운영 비용이다. 절약된 업무 토큰만 표시하지 않는다. 순효과는 관측 기간과 적용 scope를 명시하고 장기 효과를 추정할 때 불확실성을 표시한다.

### 18. 예시 A: migration 준비 절차의 개선

세 작업에서 fresh sandbox의 fixture setup이 실패했다는 관측이 있다. Analyst는 migration 미적용이라는 가설과 DB URL 오류라는 대안을 제시한다. Worker는 허가된 동일 snapshot에서 두 원인을 분리해 확인한다. Candidate는 해당 프로젝트 family의 `verification-recipe`에 조건부 migration 실행을 추가하며, 모든 Python 프로젝트에 적용하지 않는다.

실험은 fresh/이미 migrated/잘못된 URL/읽기 전용 DB/권한 거부 task를 포함한다. 잘못된 URL을 migration으로 덮어버리거나 운영 DB에 명령을 보내면 hard fail이다. baseline/candidate 실제 task 결과와 비용을 비교하고 independent reviewer가 검토한다. 승인된 release만 새 run에 투영하며 환경 digest 변경 시 재검증한다. 숫자로 꾸민 성공률 없이 실제 receipt를 붙인다.

### 19. 예시 B: interview 예외 누락의 개선

사용자가 취소 시 복구를 합의했지만 handoff 문서에 빠진 사건을 원본 R18 유형으로 분류한다. Candidate는 모든 질문을 늘리는 대신, 취소/부분 성공이 관측 가능한 작업에서만 관련 obligation을 생성하는 조건을 추가한다. 정상 짧은 요청에는 불필요한 질문을 늘리지 않아야 한다.

시뮬레이션은 개발 세트에서 문서 누락을 찾는 데 사용한다. 최종 판정에는 독립 시나리오·실제 허가된 업무 관측을 사용하고 false-ready·재질문·사용자 의도 위반을 별도 보고한다. original R08의 즉시 중단 요구와 충돌하면 후보를 거부한다.

### 20. 예시 C: release CAS 버그의 개선

관측된 동시 승격 실패가 하네스 코드 결함으로 추정되면 `extension_code_proposal`을 만든다. 실행 중 store.py를 수정하지 않는다. 별도 checkout에서 race 재현 unit/integration test를 먼저 작성하고 transaction 범위를 수정한다. schema migration이 필요한지 분석한다. clean build·실제 dcode 연동·복구 테스트·사람 code review를 거쳐 새 wheel을 배포한다. 이 변경이 보호된 승인 로직을 바꾸는 경우 자동 학습 candidate가 아니라 사람이 시작한 정책/보안 변경 review로 올라간다.

### 21. 구현 메서드와 책임

| 메서드 | 소유자 | 입력 → 출력 | 필수 실패 처리 |
|---|---|---|---|
| `build_episode` | improvement/episodes.py | terminal event → immutable episode | missing receipts → incomplete |
| `analyze_patterns` | improvement/analysis.py | scoped episodes → hypotheses | no evidence → unsupported |
| `compile_learning_plan` | improvement/workplan.py | hypothesis+policy → reviewed plan request | budget/authority missing → blocked |
| `propose_candidate` | improvement/candidates.py | approved plan+baseline → proposal | empty/unsafe diff → rejected |
| `assess_impact` | improvement/impact.py | actual diff+ownership graph → assessment | unknown → B; protected → manual |
| `schedule_actual_pairs` | evaluation/paired.py | approved experiment → jobs | missing permit → denied |
| `evaluate_candidate` | evaluation/gates.py | signed actual results → review eligibility | no actual/unsafe/inconclusive |
| `review_candidate` | improvement/reviews.py | result bundle → independent findings | failure ≠ approval |
| `prepare_release` | kernel/releases.py | approved candidate bundle → immutable release | digest/baseline mismatch |
| `promote_release` | kernel/releases.py | trusted approval+CAS → active pointer | stale parent → rebase |
| `invalidate_memory_dependents` | memory/invalidation.py | revoked/stale memory → review work | maintain dependency closure |

기존 foundation에 없는 파일은 해당 WP에서 생성할 목표 경로다. 구현자가 mock을 만든 경우 mock 경로와 상태를 명시하고 prod 포트의 성공 응답으로 연결하지 않는다.

## Alternatives considered

**replay로 모든 변경 평가:** 입력을 바꾼 새 결과를 예측할 수 없다. B는 실제 실행을 필수로 한다.

**실패 후 자동 SKILL.md 덧붙이기:** 원인 오진·context 비대화·범위 누출을 만든다. candidate→scope 평가→release 단계로 제한한다.

**임의 Python 자기수정:** 변경 중인 실행과 평가 기준이 섞인다. 새 패키지와 프로세스 단위 배포를 사용한다.

**모든 변경마다 전체 저장소 수백 과제 실행:** 비용을 제어하기 어렵다. 영향 기반 정적·개발 eval을 먼저 수행하되 final scope에 필요한 regressions와 sealed actual 평가를 생략하지 않는다.

## Acceptance criteria

열거한 모든 표면이 candidate·impact·actual eval·review·approval·release·rollback 경로와 연결되어야 한다. original R01–R22, DREAM 보존 테스트, B별 positive/negative/adversarial cases를 모두 구현한다. 실행 증거 없는 candidate는 eligible/promotion 상태로 위조할 수 없어야 한다. 캐시·비용 개선이 correctness·권한 위반을 상쇄하지 않아야 한다. 학습 평가 job이 재귀 생성되거나 운영 코드를 직접 수정하지 않아야 한다.

## Risks

작은 표본 과적합, 실제 사용자 선호의 부정확한 추론, holdout 누수, script가 숨겨진 skill, 외부 provider 비용 변화, 코드/DB rollback 불일치가 주요 위험이다. 효과가 불명확하면 기준 release를 유지하고 다음 실험이나 사람이 검토할 근거를 남긴다.
