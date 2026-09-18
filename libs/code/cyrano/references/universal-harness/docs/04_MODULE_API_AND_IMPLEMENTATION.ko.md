# 모듈·API·저장소 계약과 구현 순서

## 21. 구현 구조와 의존 방향

```text
src/udh_harness/
  domain/
    ids.py                # UUID/digest/scoped identifiers
    errors.py             # 고정 ErrorCode와 사용자 표시 메시지
    events.py             # EventEnvelope와 각 typed payload
    interview.py          # 원본 v1 DTO, authority/evidence 분리
    plans.py              # WorkPlan/WorkUnit/Review/Scenario
    approvals.py          # v2 receipt/permit; 서명 I/O는 service
    memory.py             # MemoryRecord/MemoryView
    learning.py           # Candidate/Eval/Release DTO
    ports.py              # 외부 clock/store/runner/model host protocol
  kernel/
    reducer.py            # 이벤트→순수 상태 전이
    readiness.py          # 단계별 blockers 계산
    invalidation.py       # dependency graph 전이 무효화
    routing.py            # 질문/읽기/조사/보류/검토 선택
    scheduler.py          # DAG, lease, resource/budget reservation
    plan_validation.py    # 작업 완전성·cycle·write-set·coverage
    policy.py             # scope 교집합·deny 우선
    completion.py         # 완료 증거 계산
  services/
    sessions.py
    interview.py
    planning.py
    reviews.py
    approval_broker.py
    action_broker.py
    snapshots.py
    memory_service.py
    learning_service.py
    evaluation_service.py
    promotion_service.py
    reporting.py
  persistence/
    sqlite.py             # connection/WAL/transaction boundaries
    repositories.py       # typed repository interfaces
    canonical.py          # canonical-json-v1 / digest
    blobs.py              # immutable bytes + fsync
    outbox.py             # leases/retries/dedupe
    migrations.py         # version/checksum/backup
  security/
    principal.py          # worker/run/user token 구분
    signatures.py         # Ed25519 verify/sign issuer
    paths.py              # canonical scope/path traversal/alias
    commands.py           # argv recipe interpreter
    redaction.py          # ingestion/export 전 필터
    sandbox.py            # isolation manifest와 검증
  context/
    assembler.py
    budgets.py
    manifests.py
    offload.py
  middleware/
    composite.py
    binding.py
    guards.py
    observation.py
    learning.py
  adapters/
    dcode/extension.py
    dcode/middleware.py
    dcode/tools.py
    dcode/hooks.py
    dcode/discovery.py
    dcode/launcher.py
    dcode/workers.py
    dcode/usage.py
    http/api.py
    http/approval_api.py
    cli/main.py
    telemetry/otel.py
    telemetry/langsmith.py
    sandbox/linux.py
  evaluation/
    runner.py
    splits.py
    scoring.py
    promotion_gates.py
    replay.py
  dashboard/
    api.py
    views.py
    static/
```

`domain/kernel`은 dcode/LangChain/httpx/OTel import를 금지한다. `services`는 domain ports에 의존한다. `adapters`가 구체 라이브러리에 의존한다. 순환 import 또는 kernel에서 직접 LLM 호출은 architecture test로 차단한다. 새로운 microservice를 여러 개 만드는 대신 시작 구현은 control service 하나+격리 runner+외부 dcode 프로세스다. 이 분리는 서비스 개수 최소화가 아니라 권한 경계에 따른다.

## 22. 핵심 함수 계약

### 22.1 Kernel 인터페이스

| 함수 | 입력 | 출력 | 주요 오류 |
|---|---|---|---|
| `start_session(request, actor)` | workspace/scope/policy/runtime | SessionSnapshot | INVALID_SCOPE, UNSUPPORTED_RUNTIME |
| `ingest_user_event(event, host)` | raw text/display refs/provenance | EventReceipt | UNTRUSTED_USER_EVENT |
| `next_action(snapshot)` | 현재 합의·의무·예산 | TypedAction | BUDGET_EXHAUSTED, BLOCKED |
| `apply_proposal(result, expected_revision)` | v1/v2 worker DTO | ApplyReceipt | STALE_REVISION, UNKNOWN_EVIDENCE |
| `assess_readiness(stage, snapshot)` | trusted snapshot | ReadinessReport | 결과는 blocker 목록, 예외 남용 금지 |
| `compile_spec(session, expected_revision)` | 유효 intent/decision/scenario | ArtifactBundle | UNRESOLVED_BLOCKER |
| `validate_plan(plan, spec, policy)` | 정확한 digest 객체 | PlanValidationReport | INVALID_DAG, UNBOUNDED_WRITE_SET |
| `request_review(bundle, role)` | immutable bundle/role/context mask | ReviewTask | CAPABILITY_UNAVAILABLE |
| `issue_approval(display, user_event)` | trusted broker channel only | SignedReceipt | UNTRUSTED_APPROVAL, DIGEST_MISMATCH |
| `authorize_action(request, principal)` | typed action + bound run | PermitDecision | APPROVAL_REQUIRED, SCOPE_DENIED |
| `complete_work_unit(result)` | actual output/evidence | TaskReceipt | PREIMAGE_CONFLICT, VERIFICATION_MISSING |
| `finalize_run(session)` | latest DB state | RunReport | UNRESOLVED_BLOCKER, AUDIT_GAP |
| `pause/cancel/resume(request)` | actor+reason+expected revision | SessionSnapshot | INVALID_TRANSITION |

`set_ready`, `set_approved`, `overwrite_state`, `increment_revision`, `grant_any_tool` API는 만들지 않는다. 상태는 typed command→검증→이벤트→reducer로만 바꾼다. 반환된 READY는 진단이 아니라 gate 결과여야 한다.

### 22.2 Service 인터페이스

| 함수 | 계약 |
|---|---|
| `SnapshotService.capture(scope)` | 읽기 허가 범위의 byte hash, 제외 목록, incomplete flag 반환 |
| `SnapshotService.diff(before, after)` | 변경/생성/삭제와 권한 이탈, 정상 epoch evolution 구분 |
| `ActionBroker.execute(action, permit)` | idempotency reserve→intent commit→runner→reconcile |
| `MemoryService.query(query, principal, view)` | scope/freshness 먼저, 결정적 bounded result |
| `MemoryService.propose(candidate)` | 활성 지식 직접 변경 없음, 출처 필수 |
| `MemoryService.publish(release, approval)` | 승인·parent CAS·artifact 검증 후 새 snapshot |
| `LearningService.create_job(run)` | terminal event 기준 exactly-once logical enqueue |
| `EvaluationService.evaluate(candidate, spec)` | 고정 split/runtime/budget, 결과 evidence와 uncertainty |
| `PromotionService.promote(candidate, receipt)` | policy hard gates+CAS+immutable release |
| `ReportingService.export(session)` | 사실·미검증·권한·테스트·memory·usage·learning 보고 |

서비스 응답의 boolean은 모델이 넣는 검증 완료 필드가 아니다. 서버가 확인한 evidence에서 계산한다. 예를 들어 `approval_verified`는 서명·provenance·digest·expiry 검사 결과이며 worker JSON의 true를 그대로 읽지 않는다.

## 23. 외부 API

### 23.1 API 보안 영역

일반 run API와 승인 API는 별도 listener/인증 audience로 나눈다. run token은 session/workspace/role/action scope에 묶인다. 사용자 token만 approval endpoint를 호출할 수 있고, worker는 승인 요청 생성만 할 수 있다.

모든 mutation request에 `Idempotency-Key`와 `expected_control_revision`을 요구한다. 자원 조회는 cursor pagination을 사용한다. request body 1 MiB, artifact upload 기본 10 MiB, event body 기본 64 KiB 초과는 413 또는 artifact 경로를 안내한다. 상한은 policy에 versioned 값으로 보관한다.

### 23.2 endpoint 계약

| Method / Path | 주체 | 요청/응답 schema | 동작 |
|---|---|---|---|
| POST `/v1/sessions` | host | SessionCreate → SessionView | workspace/policy/runtime bind |
| GET `/v1/sessions/{id}` | scope-bound | → SessionView | 상태·blockers·digest |
| POST `/v1/sessions/{id}/user-events` | trusted host | UserEvent → EventReceipt | 원문/출처 |
| POST `/v1/sessions/{id}/proposals` | worker | WorkerResult → ApplyReceipt | 제안 접수·CAS |
| GET `/v1/sessions/{id}/readiness?stage=` | scope-bound | → ReadinessReport | 서버에서 계산 |
| POST `/v1/sessions/{id}/plans` | planner | WorkPlan → ArtifactReceipt | 검증 후 PLAN_REVIEW |
| POST `/v1/sessions/{id}/reviews` | assigned reviewer | ReviewResult → EventReceipt | assignment/input digest 검증 |
| POST `/v1/approval-requests` | host/worker | ApprovalRequest → DisplayBundle | 요청만, 승인 아님 |
| POST `/v1/user/approvals/{id}` | authenticated user only | HumanDecision → SignedReceipt | 별도 승인 listener |
| POST `/v1/actions` | bound worker | ActionRequest → OperationView | Broker permit 검증·예약 |
| GET `/v1/operations/{id}` | bound worker | → OperationView | unknown/running/result 구분 |
| POST `/v1/sessions/{id}/pause|resume|cancel` | host/user | ControlRequest → SessionView | 취소 전파 |
| POST `/v1/memory/query` | bound worker | MemoryQuery → MemoryView | scope-aware recall |
| POST `/v1/memory/proposals` | bound worker | MemoryRecord(candidate) → CandidateReceipt | activation 금지 |
| POST `/v1/learning/candidates` | learning worker | Candidate → CandidateReceipt | 증거·target 검사 |
| POST `/v1/evaluations` | authorized evaluator | EvalSpec → EvaluationView | 비용 승인·split 고정 |
| POST `/v1/releases/promote` | promotion service | PromotionRequest → Release | 별도 receipt 필요 |
| GET `/v1/events?session_id=&after_seq=` | read scope | → EventPage | durable replay/SSE |
| GET `/v1/reports/{session_id}` | read scope | → RunReport | 미완료 상태도 정직하게 반환 |

같은 API를 CLI/MCP wrapper에서 호출한다. MCP tool은 user approval API를 노출하지 않는다. API transport가 JSON-RPC든 HTTP든 domain command 의미는 동일하다. 스키마 파일에 없는 transport envelope는 아래 고정 형식을 사용한다.

```json
{
  "request_id": "uuid",
  "expected_control_revision": 7,
  "payload": {},
  "client_context": {"display_event_id": null}
}
```

`payload`는 endpoint별 schema로 검증한다. agent가 `actor_id`를 payload에 넣어 권한을 얻지 못하며 actor는 인증 context에서 정한다.

### 23.3 오류 형식과 재시도

```json
{
  "error": {
    "code": "STALE_REVISION",
    "message": "작업 상태가 변경되어 결과를 바로 적용할 수 없습니다.",
    "retryable": false,
    "current_revision": 8,
    "affected_ids": ["plan-01"],
    "required_action": "refresh_and_rebase",
    "correlation_id": "uuid"
  }
}
```

400: 형식/스키마. 401: 인증 실패. 403: scope/권한. 409: CAS/idempotency/preimage 충돌. 422: 의미 검증/전이/준비도. 429: 예산·rate/concurrency. 503: 필수 broker/DB/runtime unavailable. 5xx를 자동 통과로 처리하지 않는다. retryable은 서버가 결정하고 재시도는 idempotency key를 보존한다.

## 24. 저장소·트랜잭션·canonicalization

### 24.1 SQLite 정책

WAL, foreign_keys=ON, busy_timeout=5000ms를 초기 설정으로 사용한다. 단일 control writer 원칙으로 시작하고 네트워크 파일시스템의 SQLite 공유는 금지한다. transaction은 짧게 유지한다. LLM/runner는 transaction 밖에서 호출하고 그 전후 intent/result를 별도 기록한다.

`sql/001_initial.sql`은 구현 시작용 DDL이다. JSON Schema와 서비스 의미 검사도 병행한다. SQL CHECK만으로 자연어 계약·scope·서명이 검증된다고 주장하지 않는다.

### 24.2 Mutation 알고리즘

1. 인증된 principal과 workspace/session binding을 확인한다.
2. 요청 DTO의 strict schema와 payload digest를 계산한다.
3. BEGIN IMMEDIATE 후 `(principal, operation, idempotency_key)` 조회.
4. 동일 digest이면 기존 receipt 반환, 다른 digest이면 IDEMPOTENCY_CONFLICT.
5. session의 control_revision을 expected와 비교.
6. authority/참조/session-scope/상태/의존관계를 검사.
7. event append, state projection 및 영향 무효화, outbox를 함께 기록.
8. control_revision CAS update, 응답 receipt 저장 후 COMMIT.
9. 외부 side effect는 저장된 intent 기반 worker가 실행한다.

telemetry ingestion은 event append를 하되 semantic control_revision을 증가시키지 않는다. audit와 domain mutation의 연결은 transaction ID로 추적한다. agent가 revision을 임의 선택하여 다음 번호로 확정하는 API는 없다.

### 24.3 Invalidation 알고리즘

변경 엔티티의 새 버전을 추가하고 기존 version을 superseded로 표시 → `depends_on/verified_by/approved_by` reverse edge를 BFS/DFS로 탐색 → 관련 spec/plan/review/test/permit/memory view를 stale/revoked로 표시 → 실행 중 lease의 신규 dispatch 차단 → 구체 unresolved list 생성. cycle guard와 visited set을 사용하며 저장 graph의 invalid cycle은 별도 오류다.

관측 evidence의 freshness 변화가 반드시 사용자 의도를 폐기하는 것은 아니다. 의도의 근거와 현재 코드 사실을 분리해 영향 의무를 재검토한다. 관련 없는 전체 세션을 불필요하게 초기화하지 않는다.

### 24.4 artifact export

내용을 canonical bytes로 만들고 digest 기반 temp path에 기록→fsync→atomic rename→DB artifact index 등록→manifest 생성 순서다. bundle manifest는 자기 digest와 approval 서명을 포함하지 않는 content 목록을 해시한다. approved bundle을 수정하면 새 digest/new revision이다.

기억·승인·테스트 원문은 필요에 따라 암호화된 blob로 저장한다. 검증 보고서는 display snapshot과 같은 식별자로 묶고 원본을 다시 렌더링했을 때 내용이 달라지지 않도록 template version도 고정한다.

## 25. 개발 작업 패키지

모든 WP는 필수다. 순서는 기능 축소가 아니라 의존관계를 따른다. 각 WP 완료 전에 해당 단위의 계획·리뷰·검증 evidence를 남긴다.

| WP | 선행 | 구현 파일/영역 | 구체 산출물 | 완료 조건 |
|---|---|---|---|---|
| WP00 | 없음 | adapters/dcode/discovery, config | 실제 runtime-lock와 compatibility report | extension/async/도구/child/취소/usage/격리 테스트 결과, 미지원 명시 |
| WP01 | 없음 | domain/*, persistence/canonical | strict DTO/오류/ID/digest | 모든 schema valid, unknown fields 거부, canonical vectors |
| WP02 | WP01 | persistence/*, sql | event store/CAS/idempotency/blobs/outbox | 재시작 replay·충돌·rollback·FK 테스트 |
| WP03 | WP02 | security/principal/signatures | trusted human channel/receipt v2 | forged/wrong digest/expired/replay 거부 |
| WP04 | WP02 | kernel/reducer/readiness/invalidation | 전체 상태기계와 dependency index | 모든 금지 전이·R01/R04/R05/R07/R09/R20 |
| WP05 | WP00,WP03 | security/sandbox/paths/commands, action_broker | governed isolation/recipe/permit | shell/file/MCP/child 우회, protected path, audit fail 테스트 |
| WP06 | WP04 | services/interview, kernel/routing | 원본 interview roles/ledger/action router | R01–R22 의미 regression 구현 |
| WP07 | WP06 | compiler/reviews/reporting | spec/acceptance/decision/evidence bundle | blind handoff·정확 bundle approval |
| WP08 | WP04,WP07 | plans/plan_validation/planning | WorkPlan DAG/traceability/review | 불명확 write-set·missing tests·cycle 거부 |
| WP09 | WP05,WP08 | scheduler/actions/snapshots | WorkUnit lease/실행/reconcile | 동시 writer 충돌·preimage·unknown outcome |
| WP10 | WP00,WP04 | middleware/*, adapters/dcode | composite order/tool bridge | native+extension+MCP+child 각 coverage 검사 |
| WP11 | WP10 | context/* | deterministic layers/offload/epoch | stable digest·dynamic tail·compaction·overflow |
| WP12 | WP02,WP11 | memory_service/domain/memory | scoped FTS5/read/propose/projection | cross-thread/workspace/freshness/delete/apply 검사 |
| WP13 | WP09,WP10 | verification services/config | quality recipes/evidence normalization | PEP8/type/test/scope·zero test·skip 처리 |
| WP14 | WP10 | events/telemetry/outbox | attempt/usage/cost/trace coverage | unknown vs 0·중복 비용·실패 이벤트·redaction |
| WP15 | WP08,WP13,WP14 | completion/reporting | final readiness/report/export | 실패·검토누락·audit gap이 완료로 못 감 |
| WP16 | WP12,WP14,WP15 | learning_service/middleware | episode/pattern/candidate jobs | TDD red 오학습·변경 scope·중복 job 검사 |
| WP17 | WP16 | evaluation/* | baseline/holdout/평가기/판정 | split leakage·기준 조작·inconclusive·hard fail |
| WP18 | WP03,WP17 | promotion_service/releases | approve/promote/canary/rollback | CAS·rebase·active run freeze·security revoke |
| WP19 | WP14,WP15,WP18 | dashboard/http/cli | 8개 화면/명령/권한/알림 | event replay·CSRF·actor isolation·privacy |
| WP20 | WP19 | ops/migrations/runbooks | 설치/업그레이드/백업/복구 | 대상 repo 무변경·key rotation·crash restore |
| WP21 | 모두 | tests/evals/evidence | 전체 release evidence 및 40점표 | governed E2E·실제 dcode·memory/cache/learning/관측 모두 확인 |

### 25.1 하위 모델 실행 지침

작업자는 한 WP를 받으면 선행 산출물과 schema/test IDs부터 확인한다. 관련 파일을 읽고 자신의 구체 파일별 변경 계획을 제출한다. 누락된 제품 결정은 임의 가정하지 말고 blocker로 보고하되 코드에서 확인 가능한 내용은 조사한다. 사용자 원래 요구사항을 간소화하거나 model-specific 분기를 추가하지 않는다.

한 번에 전체 코드를 생성한 뒤 테스트를 나중에 붙이는 대신 invariant/negative test→작은 구현→실행 evidence→독립 review 순서를 지킨다. placeholder TODO, `pass`, fake success, stubbed approval를 release 경로에 남기지 않는다. fake adapter는 이름·설정·보고서에서 fake임을 표시하고 governed production에 로드되지 않게 한다.

### 25.2 기능별 적용 기준

actor/channel 검증이 안 되면 승인 기능을 stub true로 두지 말고 CAPABILITY_UNAVAILABLE. cached usage가 없으면 null. 모델이 structured JSON을 틀리면 schema 오류 및 bounded repair 1회, 실패 후 worker failed. memory 검색이 실패하면 아무 기억이나 전체 노출하지 말고 warning/block policy. 필수 reviewer 실패는 block. 알려지지 않은 도구 이름은 registry 등록 전 deny.

### 25.3 시연 시나리오

새 unknown model로도 동일 harness release/phase profiles를 사용해 read-only 조사·인터뷰·계획·승인·작업·검증을 진행한다. 인공지능 모델의 답 품질이 나빠 통과 못 하면 workflow가 정직하게 block해야 한다. 특정 모델이 어떤 기능을 잘한다는 가정으로 평가를 통과시키지 않는다.

## 26. 테스트 계층과 분리

| 계층 | 대상 | 실행 환경 | 완료 증거 |
|---|---|---|---|
| package validation | schema/config/DDL/refs | 현재 문서 패키지 | 구조 검사 보고 |
| pure unit/property | reducer/gates/CAS/path/canonical | LLM 없이 | pytest/property report |
| component integration | DB/broker/memory/queue | 격리 local | transaction/crash/permission |
| dcode adapter contract | 실제 extension/runtime | 고정 dcode env | compatibility matrix |
| governed E2E | 승인~변경~테스트~report | 실제 sandbox+dcode | session export+trace |
| model behavior eval | 인터뷰/개발 정확도/성능 | 허용된 endpoint | task/eval metrics |
| operational drill | 취소/disk full/key rotate/rollback | 별도 시험 env | incident/recovery evidence |

문서 패키지 안의 fixtures는 **구현해야 할 사례**다. 제공한 reference oracle의 통과는 실제 middleware/승인/샌드박스 구현 통과가 아니다. 이 구분을 reports에 고정 필드로 넣는다.

## 27. 릴리스 차단 체크리스트

BASE-01/02의 실제 비침습 검사, INT-01 원본 사례 모두, PLAN-01 독립 review 및 실행 사전 차단, AUTH-01 broker provenance와 OS 경계, MEM-01 실제 조회→적용 및 삭제, LEARN-01 전체 loop, OBS-01 계측 공백 없는 필수 경로, PY-01 실제 품질 보고, CACHE-01 정확한 unknown 처리와 반복 실험, EVAL-01 holdout/hard gate를 확인한다.

지원 여부가 불확실한 dcode 확장 표면은 WP00의 명확한 integration blocker다. 기능을 조용히 생략해서 “완료”라고 내보내거나 사용자가 금지한 core 수정으로 해결하지 않는다. 필요한 API가 제공되는 검증된 릴리스에서 구현하고 adapter evidence를 고정하는 것이 계약이다.
