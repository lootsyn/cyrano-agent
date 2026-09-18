# 런타임·권한·컨텍스트·메모리·Self-Improving 상세 계약

## 9. 승인과 실행 권한

### 9.1 승인 종류

`approve_spec_for_planning`, `approve_plan`, `authorize_execution`, `authorize_sandbox_probe`, `approve_memory_promotion`, `approve_harness_release`, `authorize_apply_patch`를 서로 다른 action으로 정의한다. commit/push/deploy/외부 서비스 구매/운영 데이터 삭제는 이 action들에 포함하지 않는다. 해당 기능을 나중에 추가하려면 별도 action·위협 모델·테스트·사용자 승인이 필요하다.

사용자는 한 화면에서 계획과 실행 범위를 함께 검토할 수 있으나 두 의사를 명시적으로 구분해서 수집하고 별도 receipt를 발급한다. 이미 유효한 명시적 위임은 반복 질문을 줄이는 데 사용하지만, 한 번의 “알아서 해”를 무기한 모든 작업 권한으로 만들지 않는다.

### 9.2 Approval Broker와 표시 계약

승인 요청에는 bundle 전체를 열람할 수 있는 링크/파일, 목적, 포함·제외 scope, 변경/생성/삭제할 파일, 실행 명령·네트워크·비용 상한, rollback, unresolved items를 보여준다. `display_digest`는 표시한 manifest의 digest다. 모델이 작성한 요약만 보고 승인한 것으로 처리하지 않는다.

Broker는 별도 사용자 전용 UI/CLI에서 actor를 인증한다. Agent/MCP/run token에는 `/approve` 권한이 없다. dcode 대화에서 생성된 “사용자가 승인함” 도구 인수도 인증 이벤트로 승격하지 않는다. trusted host의 사용자 provenance를 검증할 수 없는 환경에서는 초안/승인대기 상태만 제공한다.

receipt v2는 Ed25519 서명, `receipt_id`, `session_id`, `actor_id`, 실제 `user_event_id`, `display_event_id`, action, spec/plan/scope/policy/snapshot/release digest, 발급·만료, nonce, issuer를 가진다. 서명키는 agent/execution plane에 전달하지 않는다. consumer는 공개키와 issuer allowlist만 가진다. v1 HMAC receipt는 원본 인터뷰 범위에서만 읽고, 신규 실행 승인으로 자동 변환하지 않는다.

canonical signing은 `attestation` 필드를 제외한 객체를 정규화한 bytes에 수행한다. UDH canonical-json-v1은 JSON object key 정렬, UTF-8, compact separator, NaN/Infinity/float 금지, 정수와 문자열 금액, 배열 순서 보존, Unicode 자동 정규화 금지를 사용한다. 원문 byte digest와 의미 객체 digest를 구분한다. cryptographic signature가 실제 human provenance를 대신하지는 않는다.

### 9.3 ExecutionPermit

실제 tool call마다 장기 receipt를 그대로 노출하지 않는다. Broker가 run/WorkUnit에 묶인 짧은 permit을 발급한다. permit은 action, canonical paths, command recipe IDs, 예상 preimage, 최대 출력/시간/호출, 실행 sandbox, expiry, `policy_epoch`, parent approval IDs를 포함한다. permit 확대·refresh는 Broker에서만 한다.

expiry 기본은 15분, 장기 approval 기본은 해당 세션/작업 한정이다. 진행 중 명령이 만료 시점에 도달한 경우 신규 실행을 금지하고 기존 실행은 정책에 따라 terminate 또는 안전한 checkpoint까지 기다린다. 권한 철회·취소는 신규 dispatch를 즉시 막고 장기 job에 cancellation을 전파한다. 이미 일어난 외부 부작용을 되돌렸다고 주장하지 않는다.

### 9.4 Tool mediation

도구 이름의 substring 검사만으로 권한을 강제하지 않는다. 실제 dcode tool inventory를 canonical action으로 매핑한다: READ, SEARCH, CREATE, PATCH, DELETE, EXECUTE, NETWORK_READ, SPAWN, MEMORY_READ, MEMORY_PROPOSE, ARTIFACT_WRITE. alias/renaming/MCP tool/extension tool 모두 등록된 schema hash와 함께 매핑한다. 미등록 도구는 deny다.

경로 권한은 `read`, `create`, `write_existing`, `delete`를 독립적으로 다룬다. `only_write`가 필요한 output 경로는 model read tool과 shell read 모두 금지한다. 엄격한 `only_write` 대상은 agent/shell에 읽을 수 있는 파일 mount로 제공하지 않고 Broker의 write-only capability로만 접근시킨다. agent가 파일을 소유하는 동일 UID 환경에서 단순 tool deny만 설정한 것은 이 보장을 충족하지 않는다.

새 파일 생성은 사용자가 승인한 **정확한 파일 목록**에 포함되어야 한다. 광범위 `src/**` write를 새 파일 무제한 생성 허가로 해석하지 않는다. 승인된 sandbox의 cache/temp 생성은 프로젝트 새 파일과 구분하며 사전에 정한 scratch scope에만 허용한다.

protected paths에는 credential, `.git`, 승인 DB, policy, 활성 release, 외부 SSH/클라우드 설정, broker keys를 포함한다. symlink traversal, hardlink를 통한 보호 파일 alias, `..`, NUL, sandbox 경계 밖 절대 경로, 허용 외 cwd는 거부한다. 파일 열기 직전 검사를 수행해 TOCTOU를 줄이고 Linux governed backend는 directory fd/비추적 open 계열의 보안 primitive를 사용한다. 다른 OS는 동일 보장을 검증한 backend가 없으면 governed 미지원으로 표시한다.

### 9.5 명령 실행

기본은 shell 문자열이 아닌 `argv` recipe다. 예: `python_tests`, `python_lint`, `python_typecheck`, `git_diff_readonly`. recipe의 실행 파일, 허용 인수, cwd, env allowlist, timeout, network, filesystem mounts가 고정된다. `/bin/sh -c`, `python -c`, 임의 test plugin은 문자열 allowlist만으로 안전하지 않다. 승인된 임의 코드 실행은 반드시 sandbox에서만 수행한다.

pytest/lint/build도 프로젝트 코드·설정·plugin을 실행할 수 있으므로 “읽기 전용”이라고 분류하지 않는다. 기본 sandbox는 network off, credentials 없음, readonly 소스 snapshot, Broker 전용 작업 영역과 별도 writable 임시 영역, CPU/memory/disk/process/output 제한을 가진다. Docker socket·호스트 홈 디렉터리를 mount하지 않는다.

확장 tool이 dcode 내장 승인 목록에 자동 등록된다고 가정하지 않는다. 민감한 UDH tools는 자체 Broker 검사를 필수로 수행한다. [S01]

### 9.6 Side effect와 원자성

DB transaction과 외부 프로세스 실행은 하나의 원자적 transaction이 아니다. 실행 절차는 `intent_committed → permit_reserved → started → result_observed → reconciled`이다. `started` 뒤 프로세스가 죽고 result가 없으면 `UNKNOWN_OUTCOME`으로 남긴다. idempotency가 보장되지 않는 작업을 자동 재실행하지 않는다.

파일 patch는 expected-preimage CAS, temp file 작성, fsync, atomic rename, postimage hash로 보호한다. 여러 파일의 원본 반영은 preflight 전체 확인 후 journal을 작성하고 순서대로 적용한다. 중간 실패는 partial 상태·복구 자료를 남기며 전부 적용했다고 표시하지 않는다. 가능하면 원본 적용 대신 검증된 patch 산출물만 내보내고 사용자 승인 후 적용한다.

## 10. Middleware 설계

### 10.1 등록 형태

공개 dcode extension에는 하나의 `UDHCompositeMiddleware`와 제한된 tools를 등록한다. 내부 기능은 독립적인 클래스로 분리하되 composite 안에서 순서를 명시한다. SDK 전체 middleware 순서를 임의로 재작성하거나 내장 filesystem/subagent/caching middleware를 이름 충돌로 덮어쓰지 않는다.

아래는 **등록 형태만 보여주는 adapter 골격**이다. import 대상 UDH 클래스는 이 설계에 따라 개발할 부분이다.

```python
from udh_harness.adapters.dcode.middleware import UDHCompositeMiddleware
from udh_harness.adapters.dcode.tools import build_tools
from udh_harness.adapters.dcode.launcher import connect_session


async def extension(d):
    """Register the UDH adapter in the dcode server."""
    session = await connect_session(cwd=d.cwd, extension_path=d.path)
    d.register_middleware(UDHCompositeMiddleware(session))
    for tool in build_tools(session):
        d.register_tool(tool)
    d.on_shutdown(session.aclose)
```

`d`의 읽기 전용 context 외에 TUI state를 수정하지 않는다. `register_command` 같은 없는 API를 만들지 않는다. 사용자 명령은 UDH CLI/dashboard 또는 검증된 dcode native command adapter로 제공한다. middleware·backend 변경은 새 graph/server에서 활성화한다. [S01]

### 10.2 내부 구성

| 구성 | 책임 | MUST NOT |
|---|---|---|
| RunBinding | trusted run token에서 session/task 식별 | 모델이 준 session_id를 인증으로 신뢰 |
| LifecycleObserver | 시작·종료·중단·attempt 기록 | after_agent를 전체 업무 완료로 처리 |
| WorkflowGuard | 단계·permit·scope 확인 | prompt 지시만으로 승인 강제 주장 |
| BudgetGuard | 모델/도구 비용·동시 예약 | 공유 인스턴스 카운터로 여러 run 혼합 |
| ContextAssembler | 고정된 policy/skill/memory 투영 | 원문/서명/추론 블록 임의 재작성 |
| MemoryContext | scope/freshness/relevance 선별 | 모든 기억 자동 system 주입 |
| ToolMediator | 모든 tool action 경로 Broker 연결 | 알려지지 않은 tool 자동 허용 |
| OutcomeObserver | 실제 결과·검증·수정 신호 추출 | 테스트 red를 무조건 agent 실패로 학습 |
| CompletionGuard | 필수 evidence 및 readiness 확인 | 모델 선언으로 COMPLETED 설정 |
| LearningEmitter | terminal event에 learning job 연결 | active memory/정책/코드를 즉시 수정 |

### 10.3 호출 순서

모델 호출: run binding → durable attempt 기록 → workflow/cancellation 검사 → budget 예약 → frozen context projection → downstream native handler → 실제 응답/usage 기록 → budget 정산 → outcome observation. 예외·취소에도 attempt의 종료 상태를 보존한다.

도구 호출: binding → 요청 정규화 → audit intent 저장 → 권한·상태·path/argv 검사 → budget/lease 예약 → Broker 실행 → output 제한/민감정보 처리 → evidence/result 저장 → observation. 거부된 호출도 별도 denied event로 기록한다.

원장에 보안 관련 intent를 기록할 수 없으면 side effect를 실행하지 않는다. 단순 외부 telemetry exporter 오류는 local durable outbox로 우회할 수 있지만 원장 자체 장애는 governed mutation을 차단한다.

### 10.4 sync/async 및 동시성

dcode 실제 runtime에서 사용되는 async hooks를 구현하고 동일 로직의 sync adapter도 unit test한다. business logic은 framework-independent service 함수에 둔다. middleware 인스턴스의 mutable `self.current_session`·카운터를 여러 run에 공유하지 않는다. run-scoped context와 DB 원자적 budget reservation을 사용한다.

`before_agent`는 그래프 invocation 경계이지 반드시 사용자 세션 시작이 아니다. `after_agent`는 한 invocation 종료이지 모든 테스트·리뷰·학습의 완료가 아니다. LangChain의 before/after/wrap 순서는 다르므로 sentinel contract test로 실제 순서를 검증한다. [S06]

streaming model retry는 출력 일부가 전달된 뒤 재시도했는지 기록한다. UDH retry와 native retry를 중복해 횟수를 곱하지 않는다. tool side effect는 모델 재시도와 다르게 취급한다. cancellation exception을 일반 실패로 삼켜 성공 문자열을 반환하지 않는다.

### 10.5 우회 경로

고정된 middleware가 있어도 native compaction LLM, 다른 subagent graph, provider 내부 재시도, plugin의 import-time 코드가 바깥 경로일 수 있다. doctor는 각 경로를 실행해 coverage matrix를 만든다. runtime callback 또는 승인된 transport observer로 보완하고, 모델 내용 자체보다 protocol/attempt 정보를 우선 수집한다.

확인하지 못한 경로가 있으면 `coverage_gap` event를 남긴다. 권한 우회 가능성이면 실행 차단, 사용량 관측 공백이면 비용 `unknown` 및 전체 모니터링 평가 미충족으로 표시한다. 문제를 숨기려고 dcode core를 patch하지 않는다.

## 11. Prompt Caching과 Context Engineering

### 11.1 목표와 비보장

UDH는 특정 provider용 cache parameter나 model capability DB를 만들지 않는다. **프롬프트 구조·변경 빈도·캐시 관측**을 공통으로 개선한다. 실제 inference prefix caching은 endpoint/runtime integration의 지원에 의존한다. OpenAI-compatible 형식이라는 이유만으로 cache 기능이나 billing을 단정하지 않는다.

캐시를 지원하지 않아도 업무 계약·검증·memory·학습 기능은 그대로 제공한다. 지원 여부를 모르면 `unknown`이고 `cached_tokens=0`으로 채우지 않는다. response memoization, tool 실행 결과 cache, provider prefix cache를 서로 다른 기능으로 취급한다.

### 11.2 컨텍스트 블록

| 계층 | 내용 | 수명/변경 정책 |
|---|---|---|
| L0 | native harness 및 upstream profile | 설치/graph build 단위 |
| L1 | 짧은 공통 개발 원칙·보안 경계 | 승인된 HarnessRelease 단위 |
| L2 | phase profile·도구 schema·skill metadata | phase epoch 단위 |
| L3 | 승인된 기억 snapshot 중 필요한 안정 항목 | run/context epoch 단위 |
| L4 | 현재 spec/plan/task 및 근거 발췌 | task 단계 단위 |
| L5 | 대화·도구 결과·예외·추가 관측 | 호출별 동적 |

실제 API의 tools/system/messages 직렬화 순서는 provider가 결정할 수 있다. 위 표는 소유권·수명 정책이지 모든 provider의 wire prefix가 동일하다는 주장이 아니다. UDH-owned 블록은 고정 순서와 내용 digest를 사용하고 실제 관측 가능한 request에서 효과를 확인한다.

### 11.3 안정성 규칙

L1/L2 앞에 현재 시각, run UUID, 파일 수정 횟수, 실시간 비용, observation 내용을 매 turn 삽입하지 않는다. run identity는 metadata 또는 동적 블록에 둔다. 동일 schema/동일 skill release의 정렬·직렬화를 결정적으로 유지한다. 매 호출마다 tool set을 랜덤 축소·확대하지 않는다.

안전상 tool 제거가 필요하면 cache 손실을 감수한다. memory 철회·악성 자료 발견·권한 변경이 있으면 active run을 pause/새 epoch로 전환한다. cache hit을 위해 stale·부적절한 컨텍스트를 유지하지 않는다.

native provider cache middleware가 처리하는 header/block을 재가공하거나 동일 cache integration을 두 번 등록하지 않는다. 사용 중인 SDK는 caching과 memory 배치를 고려하지만 UDH가 모든 provider의 cache 동작을 대신 보장하지 않는다. [S05]

### 11.4 예산 관리

관리자는 각 run에 `context_budget_tokens`, `reserved_output_tokens`, `reserved_tool_result_tokens`를 설정할 수 있다. 실제 tokenizer와 model limit이 검증되면 그것을 사용한다. 문서상 limit이 없을 때 임의 128k/1M을 가정하지 않는다. char 추정은 diagnostic으로만 쓰고 token 정확값으로 표시하지 않는다.

context pressure가 높으면 관련 근거 우선 선택 → 긴 tool 결과 artifact offload → 완료 task 요약 → 필요 시 native compaction 순으로 처리한다. 승인·원문·핵심 decision ID·미해결 의무·policy digest는 요약으로 없애지 않는다. 원문은 외부 저장소에 남긴다. 강제 budget에 맞지 않으면 더 작은 work unit으로 재계획하거나 pause한다.

subagent 입력은 업무 결과에 필요한 최소 spec slice와 관련 evidence/memory다. 메인 대화를 전부 복제하지 않는다. blind reviewer에는 일부러 대화 및 다른 reviewer 답을 주지 않는다.

### 11.5 ContextManifest

각 context epoch에 `native_runtime_digest`, `release_digest`, `phase_profile_digest`, `tool_inventory_digest`, `stable_blocks[{id,digest,bytes}]`, `memory_ids/revisions`, `evidence_ids`, `dynamic_reason`, `token_measurement_source`를 기록한다. provider가 wire request를 노출하지 않으면 `wire_observed=false`다.

`stable_prefix_digest`는 UDH의 결정적 부분을 검증하는 값이다. provider cache key로 자동 전달하지 않는다. digest 일치가 실제 cache hit을 증명하지는 않는다.

### 11.6 캐시 검증

동일 runtime/model/endpoint/phase/release에서 반복 호출, AGENTS 수정, skill release 변경, tool schema 변경, dynamic tail 변경, session resume, model/endpoint 교체를 각각 분리한 실험을 실행한다. cache TTL/cold 여부를 강제로 보장할 수 없으면 `cold_assumption=unverified`로 표시한다.

측정값: input/output tokens, cache-read/write tokens(제공 시), 명시된 과금, 총 latency, first-token latency(관측 시), native retries, context bytes, 정확도/검증 결과. latency 감소만으로 cache hit 판정하지 않는다. cache 지표 제공 호출만 분모에 넣고, missing data 비율도 함께 보고한다.

## 12. Memory: 적극적 사용과 통제

### 12.1 기억 종류를 모두 유지한다

| 종류 | 저장 내용 | 조회 시점 | 권위 |
|---|---|---|---|
| Working | 현재 계획·pending·scratch references | invocation/resume | 단기 상태 |
| Episodic | 과거 작업·실패·교정·실행 증거 | 유사 작업/반성 | 관측 사례 |
| Semantic | 확인된 프로젝트 사실·환경·계약 설명 | intake/plan/change review | scope/freshness 검증 필요 |
| Procedural | skills·검증 recipe·리뷰 절차 | phase/task 선택 | 승인된 release |
| Preference | 사용자의 명시적 공통 선호 | intake/profile | 현재 요청이 우선 |
| Evidence memory | 원문·파일 snapshot·검증 artifact index | fact 재검증/리뷰 | 사실 근거, 승인 아님 |

Learning observation/candidate는 아직 활성 지식이 아니다. 이들을 보관하는 기능을 삭제하지 않으며 active memory와 신뢰 계층만 분리한다. SDK의 checkpoint state와 장기 memory/backend를 같은 저장소처럼 취급하지 않는다. [S03]

### 12.2 저장 모델

MemoryRecord에는 `memory_id`, `kind`, `scope{tenant,user,workspace}`, `title`, `content_ref`, `source_event_ids`, `evidence_refs`, `status`, `valid_from/valid_until`, `depends_on_digests`, `approval_ref`, `supersedes`, `sensitivity`, `tags`, `version`, `content_digest`가 있다.

상태: `candidate → reviewed → approved → active → stale/superseded/revoked/archived`. 일반 관측 fact의 승인 정책은 근거 검증으로 충족할 수 있으나 사용자 선호·행동 규칙·active skill 변경은 해당 사람/정책 권한을 요구한다. agent가 자신에게 scope를 넓힌 record를 생성할 수 없다.

기본 저장은 SQLite+FTS5+content-addressed blobs다. 선택적 embedding index는 adapter로 추가할 수 있지만 특정 embedding model은 필수 의존성이 아니다. semantic memory라는 이름이 반드시 vector DB를 뜻하지 않는다.

### 12.3 적극적 Recall Workflow

INTAKE에서 사용자 선호와 workspace의 활성 사실을 조회한다. PLAN_DRAFT에서 유사 task의 회귀·실패·검증 recipe를 조회한다. IMPLEMENT에서 현재 WorkUnit과 관련된 검증된 절차만 제공한다. VERIFY/REVIEW에서 과거 누락 패턴·acceptance edge cases를 조회한다. terminal run 뒤 EPISODE를 생성해 학습에 연결한다.

조회 절차: scope ACL 필터 → active/fresh 상태 필터 → task/requirement/path/tag/텍스트 검색 → 근거 유효성 확인 → 관련성 정렬 → 중복/상충 검사 → context budget 선택 → 명시적 memory view 반환. scope 검사는 retrieval 후 LLM 필터가 아니라 DB/query/service 계층에서 수행한다.

동점 정렬은 `relevance_score desc, verified_at desc, memory_id asc`로 결정적이다. 점수는 retrieval 우선순위이지 진실 확률이 아니다. source/evidence가 만료되면 해당 기록을 authoritative advice로 주입하지 않고 재검증 후보로 반환한다.

### 12.4 사용 여부를 구분한다

`memory.queried`는 검색, `memory.selected`는 결과 선택, `memory.injected`는 실제 모델 컨텍스트 전달, `memory.referenced`는 결과에서 ID 참조, `memory.applied`는 후속 계획/작업에 반영됨을 검증한 상태다. 검색 hit만으로 “메모리를 활용했다”고 평가하지 않는다.

memory 적용은 plan diff, 요구사항 연결, 실제 도구/검증 evidence로 확인한다. 모델의 “기억했습니다”는 self-report로 별도 보관한다. 효과 평가는 memory on/off 통제 과제 및 이후 실패 재발률을 사용하며 조회 횟수가 많다고 품질 개선이라고 단정하지 않는다.

### 12.5 노출·쓰기 경로

stable AGENTS projection은 사용자/공통 원칙만 간결하게 담는다. 상세 절차는 progressive skill, 프로젝트 지식은 scoped memory query/tool로 제공한다. `/udh-memory/` 같은 virtual backend를 제공할 경우 builtin file tools로 읽되 shell 접근 가능성을 가정하지 않는다. 별도 `udh_memory_search/read/propose` tools를 기본 경로로 구현하면 write 승인과 scope 통제를 명확히 할 수 있다.

Agent에는 `propose`만 허용한다. active memory/release는 broker-owned immutable snapshot으로 mount하고 일반 file/shell tool로 직접 수정할 수 없게 한다. `/remember` 같은 native 동작이 활성 AGENTS를 직접 수정하려고 하면 정책에 따라 candidate로 안내하거나 거부한다. native 기능을 꺼버리는 대신 UDH 통제 경로로 연결하되, 실제 intercept가 가능한지 통합 테스트한다.

### 12.6 freshness·삭제·이동

코드 사실은 해당 파일/환경 digest가 변하면 stale다. 범용 선호는 사용자 정정 시 supersede된다. 기본 TTL 예시는 작업 환경 사실 7일, 외부 API 사실 1일, 근거 있는 architecture 30일이지만 path digest가 바뀌면 TTL보다 먼저 무효화한다. TTL만으로 진실을 보증하지 않는다.

삭제 요청은 active projection·검색 index·vector index·cache view·export 사본의 삭제 범위를 추적한다. 감사 기록에는 민감 본문 대신 tombstone과 최소 식별 metadata를 남기는 정책을 적용한다. 이미 외부 trace 서비스에 보낸 데이터는 별도 삭제 workflow가 필요하므로 기본 외부 본문 전송은 비활성이다.

### 12.7 Memory 테스트

신규 thread, 동일 thread resume, 다른 workspace, 다른 사용자, 기억 수정 후 신규 epoch, stale fact, 상충 선호, 악성 memory, 삭제 후 검색, 동시 promotion, offload 후 근거 회수, model 교체, skill 실제 로딩·반영을 모두 검사한다. 세션 재개가 곧 최신 AGENTS 재로딩을 보장한다고 가정하지 않는다. runtime binding은 memory release를 명시적으로 고정하고 변경 시 새 epoch/server를 사용한다.

## 13. Self-Improving: 강력한 기능을 안전하게 운영

### 13.1 목적

모델의 가중치를 학습시키지 않는다. 개선 대상은 범용 인터뷰 질문 선택, 계획 분해·리뷰 절차, skills, 기억, verification recipe, context budget/선택, bounded retry·delegation·workflow 설정이다. 모델별 prompt나 capability 점수를 만들지 않는다.

모델 ID는 재현·비용·평가 결과의 실험 조건으로 남길 수 있다. 모델마다 특별 prompt를 배포하는 데 쓰지 않는다. 현재 이용 가능한 모델이 하나면 그 조건에서만 검증했다고 보고한다. 다수 모델에서도 동일 후보 artifact를 검증하되 평가 결과를 모델 특화 profile로 전환하지 않는다.

### 13.2 전체 파이프라인

```text
실행 관측 → episode 완성 → 반복 패턴/반례 분석 → 원인 가설
  → 후보 변경 생성 → 위험/권한 검사 → 정적 검증
  → 개발용 eval → 잠긴 holdout/regression → 독립 검토
  → 사람 승인 또는 좁게 사전 위임된 promotion
  → immutable HarnessRelease → canary/후속 관측 → 유지 또는 rollback
```

모든 단계는 구현 대상이다. 초기 rollout에서 observation-only로 검증하더라도 최종 제품 요구사항에서 candidate/eval/promotion/rollback을 제거하지 않는다.

### 13.3 관측과 원인

관측 signal: tool error, timeout, repeated failure, user correction, plan divergence, missing verification, reviewer finding, out-of-scope edit, memory conflict, context overrun, rework, task outcome, approval-denied, interrupted execution.

다음은 무조건 실패 학습 대상이 아니다: 의도적인 TDD red test, 정상적인 retryable network error, 명령 취소, 사용자의 요구 변경, 올바른 권한 거부, 합법적 동일 파일 재독해. event에는 `expected_outcome`, `actual_outcome`, `phase`, `intent`, `environment_error`, `user_change`를 남겨 구분한다.

LearningAnalyst는 evidence-backed 가설과 대안 원인을 제시한다. “테스트가 실패했으니 테스트를 생략하라”, “승인 때문에 느리니 승인을 제거하라”는 금지 후보다. 한 사건으로 범용 원칙을 확정하지 않는다. 반대로 단일 중대 보안 사건은 반복 횟수를 기다리지 않고 긴급 revoke/pause를 발동할 수 있다.

### 13.4 Candidate 계약

필수 필드: candidate ID, target surface, parent release digest, 관련 episode/evidence, 원인 가설, 대안 설명, 정확한 변경 patch, 기대 효과, 예상 위험, scope, policy 영향, 평가 데이터 manifest, success/non-regression 기준, rollback release, 승인 요구, 비용 상한.

변경 표면은 `skill`, `memory`, `workflow_config`, `context_config`, `verification_recipe`, `middleware_config`, `extension_code_proposal`이다. 마지막은 **코드 변경 제안**이며 실행 프로세스가 자기 Python 파일을 덮어쓰는 권한이 아니다. 별도 UDH 개발 저장소에서 계획·리뷰·보안검사·CI·사람 승인을 거쳐 새 패키지를 배포한다.

보안 정책, 승인 trust root, redaction, test verdict, holdout 데이터, audit 보존, 실행 범위 확대는 자동 promotion 대상이 아니다. 모델이 평가 기준 자체를 수정해 점수를 올릴 수 없다.

### 13.5 평가 방법

baseline과 candidate는 동일 task/snapshot/seed(가능한 경우)/runtime/model/endpoint/budget을 사용한다. 순서 효과를 줄이기 위해 실행 순서를 섞고, 동일 원본 프로젝트의 변형은 같은 split에 넣는다. hidden acceptance는 evaluator만 보며 learning worker에게 정답 테스트를 노출하지 않는다.

정적 gates: schema·policy·secret·scope·인터뷰 R01–R22·권한/회귀 cases 모두 통과. 효과 metrics: task success, false-ready/false-block, 사용자 의도 위반, 재질문, plan rework, 검증 누락, memory grounded-use, 시간·비용·tool retries.

초기 최소 실험 예시는 서로 다른 project-family 20개, 후보당 반복 3회다. 이는 충분한 통계적 검정력을 보장하는 숫자가 아니다. 표본이 부족하거나 불확실성이 크면 `inconclusive`다. non-inferiority margin·최소 유의 개선·비용 상한은 실행 전에 policy에 기록한다. 반복적으로 holdout을 들여다보면 새 후보가 과적합할 수 있으므로 접근 횟수 제한·평가 세트 회전·최종 봉인 세트를 운영한다.

단일 합산 점수로 safety regression을 상쇄하지 않는다. 승인 우회/의도 위반/비밀 유출/거짓 완료는 hard fail이다. correctness가 나빠졌는데 token 비용만 줄었다고 promote하지 않는다.

### 13.6 Promotion와 rollback

저장 enum은 schema의 lowercase를 사용하고 아래 대문자는 표시용이다. promotion은 candidate 상태 `PROPOSED → STATIC_VALIDATED → EVALUATING → EVALUATED → REVIEWED → AWAIT_APPROVAL → PROMOTED`를 따른다. `REJECTED / INCONCLUSIVE / REVOKED`도 별도 상태다. 파일 하나씩 덮어쓰지 말고 release manifest를 완성한 후 active pointer를 atomic CAS로 바꾼다.

동시에 두 후보가 같은 baseline을 수정하면 먼저 승격된 release 이후 두 번째 후보는 rebase+재평가해야 한다. old baseline 결과를 그대로 재사용하지 않는다. 기존 run은 시작 시점 release를 유지하고 새 run부터 적용한다. 보안 revoke는 기존 run에도 즉시 pause/rebind한다.

canary 비율 기본 예시는 새 세션의 10%지만 사용자의 사전 동의·scope·운영 정책이 필요하다. canary 관측은 eval 통과를 대신하지 않는다. rollback은 parent release로 pointer 전환하고 영향을 받은 run/메모리 뷰·보고서를 연결한다. 미완료 원본 코드 변경을 rollback했다고 오해하지 않도록 harness rollback과 workspace rollback을 별도 표시한다.

### 13.7 Middleware와 학습 worker의 분리

OutcomeObserver/ LearningEmitter는 짧고 결정적인 기록만 수행한다. `after_model` 안에서 추가 LLM reflection을 재귀 호출하지 않는다. 마지막 terminal event와 동일 transaction에서 learning outbox job을 생성한다. 운영 시 사용자가 시작한 worker/service가 이를 소비한다. hooks의 비동기 실행이 자동 제공된다고 가정하지 않는다.

job key는 `(run_id, terminal_event_id, learning_policy_digest)`이며 중복 실행은 동일 결과를 반환한다. job은 독립 예산·max attempts·deadline·cancellation을 가진다. 학습 실패가 이미 검증 완료된 코드 결과를 실패로 바꾸지는 않지만, “학습도 완료”라고 표시해서는 안 된다.
