# 캐시 친화적 Context·Skill·역할 설정

문서 유형: 상세 설계 · 상태: 계획(제품 미구현)


## Problem

skill·agent 설정·memory를 매 요청마다 자유롭게 재조합하면 같은 작업의 공통 prefix가 흔들린다. 반대로 모든 지침과 기억을 고정 prefix에 밀어 넣으면 노출 범위·토큰·안전성이 나빠진다. 사용자는 모델 특화가 아닌 범용 구조로 cache 효율을 높이면서 인터뷰·계획·학습 기능을 모두 유지하려 한다.

## Proposal

### 통합 R2 profile·memory lifetime

configs/task-profile-policy.json이 phase/task/risk/권한/예산/review 합성 규칙을 소유한다. Memory release는 고정하지만 query view는 task의 dynamic tail이다. selected stable memory subset은 epoch초기고정만 허용한다. 모든spec은critic+blind, plan/final은독립review, highcritical은security추가다. 현재시각/상태/nonce를 stable prefix에 넣지 않는다. cachehit은providerusage관측없이확정하지 않는다.

자세한 해석·충돌 해결은 [Universal Harness 통합 설계](2026-09-16-universal-harness-integration.ko.md)를 따른다. 원본첨부에 있는 더 느슨한예시로 이규칙을낮추지 않는다.

### 1. 네 종류의 캐시를 구분한다

| 종류 | 저장 내용 | 정확성 기준 | 공유 경계 |
|---|---|---|---|
| Provider prompt/KV cache | 제공자가 처리한 prefix 상태 | 실제 provider usage로만 관측 | provider/model/endpoint/계정 경계, 보편 TTL 보장 없음 |
| CYRANO context artifact cache | 결정적으로 렌더링한 승인 블록 | raw bytes와 dependency digest | tenant·user·release·role·epoch |
| Memory query cache | 승인 scope 내 검색 결과 ID | ACL revision·freshness·query·memory release | tenant/user/workspace exact |
| Derived summary cache | 원본 evidence의 요약 | input digest·요약기 버전·권한·의미 검증 | 원본과 동일 또는 좁은 scope |

tool 실행 결과나 테스트 verdict를 저장해 실제 평가를 건너뛰는 기능은 이 설계의 캐시가 아니다. 동일한 명령 문자열이라도 파일·환경·권한·시간에 따라 결과가 달라진다. Replay의 허용된 과거 결과 재사용은 별도의 탐색 평가이며 실제 실행 완료로 표기하지 않는다.

### 2. 기본 context 순서

```text
[고정: CYRANO가 소유하는 prefix]
  00 constitution                 짧은 공통 규칙, 승인 원칙
  10 role                         하나의 역할과 출력 계약
  20 tool inventory               epoch 동안 고정된 도구 명세
  30 skill catalogue              정렬된 이름·설명·version/digest
[별도 native 계층]
  dcode가 조립하는 시스템 지침·native 도구
[변동: 작업 입력과 대화의 tail]
  run_binding / contract / work_unit
  scoped memory view / evidence references
  최근 관측 / 사용자의 새 요청 / 남은 작업
```

위 순서는 CYRANO 소유 블록의 논리적 순서다. dcode가 네이티브 system prompt·tool schema를 다른 위치에 직렬화한다면 WP05의 실제 request capture에서 확인하고 문서화한다. CYRANO가 provider 전체 wire prefix를 통제한다고 가정하지 않는다. content hook에서 매 호출 system message 전체를 재작성하지 않으며 가능한 가장 늦은 동적 주입 위치를 사용한다. 안전한 삽입 위치를 제공하지 않는 버전은 `stable_prefix_scope=cyrano_only` 또는 기능 미지원으로 표시한다.

### 3. 고정 블록에 넣지 않을 값

run/session ID, 시간, 임시 경로, 작업별 requirement·decision, 승인 nonce·signature, 남은 예산, 실시간 progress, 최신 memory 결과, 모델별 benchmark label은 고정 블록에 넣지 않는다. 역할명이 같다는 이유로 오래된 사용자 답을 고정 지침에 남기지 않는다. 변동 데이터는 `ContextManifest.change_reason`과 함께 tail로 전달한다.

기본 `constitution`은 안전·정직·근거·제안 권한만 포함한다. 별도 정책 enforcement를 대체하지 않는다. 정책 version의 digest를 넣을 필요가 있으면 release 단위 고정 값으로 다루고 매 요청 발생시각을 붙이지 않는다.

### 4. Context epoch와 release pin

`ContextEpoch`는 `(run_id, role_id, release_digest, tool_inventory_digest, native_runtime_digest, memory_view_policy_digest)`로 식별한다. 같은 epoch에서 role·tool catalogue·skill metadata를 재정렬하지 않는다. 동적 scope 밖의 기억은 조회하지 않는다. 선택된 memory 내용과 skill 본문 revision도 actual context manifest에 남긴다.

새 release가 승인되어도 진행 중 Run의 일반 context는 그대로다. 새 Run 또는 사용자가 승인한 새 episode에서만 rebind한다. 권한 철회·비밀 노출·취약 skill revoke는 cache보다 우선하여 현재 run을 pause하고 context를 재구성한다. cache를 보존하려고 revoked 명령을 계속 전달하면 안 된다.

도구를 줄이거나 늘리는 phase 전환은 명시적 새 epoch다. 모든 도구를 한꺼번에 항상 노출하는 방식과 매 tool call 직전에 catalogue를 바꾸는 방식을 모두 피한다. `phase_bundle`은 작업·위험 기반이며 모델 이름 기반이 아니다.

### 5. 생성 문자열과 hash 규칙

JSON artifact canonicalization은 version 1 규칙을 적용한다: UTF-8, NFC, 객체 key 정렬, 배열 순서 보존, 문자열 개행 LF, 부동소수 값 거부, signed metric·금액은 decimal string, 정수는 안전 범위, key normalization 충돌 거부. 이미 저장한 원본 source나 사용자 문장은 별도 raw bytes로 보존하고 원본을 canonicalization해서 증거 hash를 바꾸지 않는다.

`stable_prefix_digest`는 **렌더링한 실제 UTF-8 bytes**의 SHA256이다. `request_digest`는 native request가 모두 보이지 않는 경우 `deepagents_code.cyrano.context_digest`라는 논리 의미를 가진다. provider wire hash나 cache key로 오인하지 않는다. 같은 prefix bytes를 여러 번 컴파일하는 테스트는 제공자 cache hit 테스트가 아니다.

토큰 수를 모르면 `token_count=null`, `token_measurement_source=unknown`다. byte 길이는 진단값이고 1token=4char 같은 근사로 hard context limit을 통과시키지 않는다. 실제 tokenizer/model limit이 확인되거나 제공자 오류 전 안전한 측정 경로가 있을 때만 hard token budget을 강제한다.

### 6. Skill 형태와 지연 로딩

각 product skill은 다음 구조다. 개발 에이전트용 `.agents/skills`와 제품 runtime용 `plugins/cyrano/skills`는 목적이 다르다.

```text
plugins/cyrano/skills/<skill-id>/
  SKILL.md                  이름·설명 + trigger·절차·검증·중단 조건
  references/checklist.md   상세 기준, 필요한 때만 읽음
  assets/output.example.json
```

skill에는 `name`, `description` frontmatter를 둔다. version·digest·scope·requires·risk·allowed phases는 별도 CYRANO SkillManifest로 관리한다. native dcode가 모든 추가 frontmatter를 이해한다고 가정하지 않는다. 공식 progressive disclosure는 metadata→본문→resource 접근 방식이며 실제 dcode loader의 root·중복 우선순위·서브에이전트 상속을 테스트해야 한다 [S05].

startup은 승인된 catalog의 metadata만 고정 순서로 투영한다. task가 필요로 하는 skill만 본문을 로딩하고 resource는 해당 단계에서 읽는다. 매 요청 모든 references를 본문에 합치지 않는다. 동일 이름의 다른 skill을 여러 경로에 설치하는 경우 덮어쓰기 우선순위에 기대지 않고 배포 validator가 거부한다.

실행 script가 있는 skill은 `SkillManifest.resources[].executable=true`다. script 변경을 “지침 수정”이라고 낮은 위험으로 분류하지 않는다. 의존성 추가, 네트워크 사용, shell 실행은 별도 허가·코드 review·실행 검증을 요구한다.

### 7. AgentRole 설정

AgentRole은 역할 목적, 허용 skill, 입력 schema, 출력 schema, 도구 권한 집합, 필수 리뷰, context 정책을 가진다. 모델 필드는 role artifact에서 제외하고 deployment의 provider selection이 공급한다. 후보 생성자와 독립 reviewer는 동일 모델이어도 별도 입력 scope·실행 instance를 가진다. 이는 독립 프로세스/증거 관점이지 서로 다른 모델이면 자동 독립이라는 뜻이 아니다.

개발 role은 architect, implementer, reviewer, security-reviewer, release-reviewer다. 제품 role은 facilitator, evidence-scout, critic, blind-handoff-reviewer, planner, plan-reviewer, implementer, verifier, learning-analyst, candidate-author, experiment-reviewer, code-reviewer다. 결정권은 role prompt가 아니라 trusted kernel에서 관리한다. 평가 최종 판정기는 모델 role이 아닌 deterministic service다.

### 8. Cache telemetry

모델 attempt마다 `provider_requested`, `provider_served`, `model`, `endpoint_class`, `runtime_digest`, `stable_prefix_digest`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `usage_semantics`, `charged_cost`, `price_revision`, `usage_coverage`를 저장한다. 제공자가 숨긴 route는 unknown이다. 비밀이 포함된 endpoint 원문은 기록하지 않는다.

일부 provider는 input 안에 cached input을 포함하고 일부는 별도 필드를 쓴다. adapter가 의미를 검증하기 전 합산·차감하지 않는다. 분모가 없으면 cache ratio는 null이고 0%가 아니다. 지연 감소만으로 cache hit을 판정하지 않는다. provider가 제공하는 명시적 cached tokens가 있는 표본에 대해서만 hit/read share를 계산하고 측정 누락 비율을 같이 표시한다.

OpenAI exact-prefix cache, Anthropic의 native cache 표시, OpenRouter의 라우팅/캐시 안내 등은 provider adapter의 검증 대상이지 모든 모델에 같은 TTL을 강제하는 공통 규칙이 아니다 [S07–S09]. 작은 prefix 요청으로 더 긴 prefix의 TTL이 유지된다고 가정하지 않는다. 유료 keepalive·dummy warming은 기본 비활성이며 이 제품의 기본 실행계획에도 포함하지 않는다.

### 9. 캐시 최적화 실험

실험은 성능과 정확성을 함께 비교한다. 같은 role/task/runtime/provider/model에서 stable prefix 유지, 동적 tail 변경, tool inventory 변경, skill body 변경, memory revision 변경, release 변경, session resume, model 교체, provider fallback 조건을 각각 분리한다. 각 실험은 최소한 실제 request 구조에 대한 관측 범위를 밝힌다.

컨텍스트 후보는 경로 B다. 조립 순서·요약 길이·선택 기억을 바꾸면 출력이 달라질 수 있으므로 cached tokens 개선만으로 승격하지 않는다. 실제 task correctness·의도 보존·승인 위반·검증 누락·비용·latency 비교를 모두 수행한다. correctness가 나빠졌다면 hit율이 좋아도 배포하지 않는다.

### 10. 구현 API와 실패 의미

`ContextCompiler.compile(spec) -> CompiledContext`는 side effect 없이 블록·manifest를 만든다. `ContextBinding.apply(run, compiled, expected_epoch)`는 dcode adapter가 실제로 반영한 블록 IDs를 receipt로 반환한다. 실패 시 기존 epoch를 임의 혼합하지 않는다. `SkillRegistry.resolve(role, release) -> tuple[SkillManifest,...]`는 duplicate·revoked·dependency missing이면 에러다. `MemoryViewBuilder.select(query, principal, snapshot)`는 ACL revision을 포함하는 immutable view를 반환한다.

오류: CONTEXT_BUDGET(축약·분할 필요), DUPLICATE_BLOCK/INVALID_BLOCK_ID(생성 오류), UNKNOWN_TOKEN_LIMIT(강제 길이 검증 불가), STALE_CONTEXT_EPOCH(재바인딩 필요), SKILL_DIGEST_MISMATCH(격리·재설치), DUPLICATE_SKILL(배포 오류), CACHE_USAGE_UNKNOWN(성능 판정 미확정; 작업 정확성 실패와 다름).

## Alternatives considered

**모든 skill을 system prompt에 넣기:** 검색 절차는 줄지만 토큰·scope 노출·prefix 변경 비용이 커진다. 작은 metadata catalog와 필요한 본문만 사용한다.

**모델별 튜닝 prompt:** 사용자가 제외한 기능이다. provider별 실제 cache wire 옵션은 지원하되 추론/행동의 모델별 특화는 만들지 않는다.

**항상 같은 prefix로 만들기 위해 기억 고정:** 오래된 사실과 revoked skill을 계속 사용하게 된다. freshness·권한이 cache보다 우선한다.

## Acceptance criteria

같은 static 입력의 렌더링 raw bytes는 같고 dynamic 값 변경은 stable digest를 바꾸지 않아야 한다. 권한 철회는 즉시 context 재검토를 유발한다. metadata만 로딩한 초기 상태와 body/resource 실제 로딩이 event로 구별되어야 한다. native loader·child inheritance·실제 usage semantics가 미검증이면 검증된 것으로 표시하지 않는다. CACHE-01 product cases를 실제 provider 허가 환경에서 실행해야 cache 효율 개선을 주장할 수 있다.

## Risks

dcode의 system prompt 재구성, native summarization, provider tokenizer/라우팅 변화가 prefix 안정성을 깨뜨릴 수 있다. 이 위험을 숨기기 위해 자체 해시를 provider cache hit처럼 보고하지 않는다. 큰 고정 catalogue 자체의 비용도 실험에 포함한다.

## 1. 조립 순서

```text
L0 native policy·기본 역할·고정 tool schema
L1 승인된 role/skill metadata + core memory release
L2 작업 단계별 승인된 절차 본문
L3 현재 의도·계획·검증 의무·관련 evidence/memory view
L4 이번 turn의 관측·도구 결과·사용자 입력
```

각 블록에 id, revision, source digest, 권위, scope, bytes, token measurement source를 가진다. 순서는 deterministic key로 고정하고 중복 ID는 오류다. native prompt를 새로운 거대 system prompt로 교체하지 않는다. time/run id/approval nonce/progress는 L3/L4에만 둔다. 권한 자체는 prompt에서 강제하지 않는다.

## 2. ContextEpoch

epoch는 runtime/provider route, stable prompt blocks, tool inventory, policy revision, approved memory/skill release에 결속된다. 동일 epoch에서는 stable blocks를 부분 수정하지 않는다. 정당한 변경은 새 epoch를 만들고 이유를 기록한다. 같은 thread를 resume했다고 최신 파일이 자동 재로딩되었다고 가정하지 않는다.

byte digest 동일성은 provider cache 적중 증명이 아니다. wire adapter가 실제 요청을 관측할 수 있으면 정규화된 비교 hash를 남기고, 할 수 없으면 `wire_observed=false`다. provider의 실제 캐시 키나 내부 shard를 추정하지 않는다.

## 3. 의무를 보존하는 compaction

`ObligationManifest`는 사용자 원문 참조, 활성 요구, 해소되지 않은 blocker, 선택된 설계, 계획 revision, 미완료 WorkUnit, 미결 call, 승인/철회 ref, 남은 budget, 필요한 acceptance를 포함한다. 요약 모델이 이것을 작성/삭제하는 권위를 갖지 않는다.

compaction은 (1) 원시 artifact를 고정하고 (2) 필수 의무를 코드가 추출하며 (3) 선택적 narrative를 요약하고 (4) 출력에서 의무 집합과 call/result 관계가 보존됐는지 검사한 다음 (5) 새 context epoch를 채택한다. 하나라도 사라지면 `OBLIGATION_LOSS`로 거부한다. 남은 예산에 맞지 않으면 작업을 더 작은 단위로 재계획하거나 pause한다.

복원 파일 목록은 경로 문자열이 아니라 snapshot/file digest를 가진다. 변경된 파일은 재읽어야 한다. 커다란 과거 도구 결과는 요약만 남기되 원문 artifact가 존재해야 하고 삭제·권한변경 시 참조도 무효화한다. hash만 있고 원문이 없는데 읽은 것처럼 답하지 않는다.

## 4. 검색과 ToolExposure

검색은 권한·정책·workspace 필터 후 relevance를 계산한다. 동점은 결정적인 ID로 정렬한다. 불필요한 대형 graph와 모든 skill 본문은 상시 주입하지 않는다. phase 시작에 필요한 최소 도구 집합을 선택해 고정한다. 도구 선택기를 바꾸는 개선은 lane B이며 actual eval 대상이다.

optional intelligence 미지원 때 text fallback이 충분한 것은 code 탐색이다. 권한·정확한 symbol identity·필수 검증 실패를 text 검색으로 성공 처리하지 않는다. fallback 이유와 결과의 보장 차이를 context와 trace에 남긴다.

## 5. 캐시 종류를 혼동하지 않는다

| 종류 | 재사용 대상 | 범위·검증 |
|---|---|---|
| provider prompt cache | prefix 계산 | 제공자·route·정책·TTL와 실제 usage |
| HTTP keepalive | 네트워크 연결 | 비용·token cache와 무관 |
| MCP 목록 cache | 도구 목록 | endpoint/schema snapshot·만료 |
| code/doc index | 파싱·검색 자료 | source/config/provider/ACL digest |
| result memo | 실제 계산 결과 | read-only·완전한 입력 동일성·freshness |

## 6. TTL·warming 실험

Claude 공식 문서의 TTL은 **요청 시작 시점** 기준이다. Senpi 소스에서 참고한 완료 시점 기반 타이머를 그대로 일반화하지 않는다. 프로세스 내 대기에는 monotonic을 쓰며, 재시작 후에는 이전 monotonic timestamp를 비교할 수 없으므로 wall clock 증거와 provider 정책·시계 불확실성을 보수적으로 처리한다. TTL을 모르거나 clock이 역행하면 보존을 보장하지 않는다. [NS11·NS53](../../reference/SOURCES.ko.md#ns53)

`CacheObservation`에는 request_started_at, completed_at, provider/route, prefix digest, cache_read/write, accounting semantics, TTL policy ref, uncertainty, explicit/implicit cache identity를 둔다. 누락은 null이다. input total에 cached가 포함되는지 확인하지 않고 비율을 계산하지 않는다.

기본값 `warming_enabled=false`. 활성화 실험의 전제는 명시 동의, 실제 지원 검증, 독립 비용 cap, idle·pending input 검사, 사용자 작업 우선, 중복 flight 방지, 새 generation에서 결과 적용 차단이다. 실제 청구는 stale response여도 기록한다. 네트워크 실패 후 cap 사용량을 몰래 반환하지 않는다.

실험의 경제성은 `warm 비용 + 추가 지연 + 후속 실제 업무 비용`을 기준안과 비교한다. 작은 접두사만 계속 보내면 긴 prefix 전체가 보존된다는 가정, 모델 교체 후 cache 공유, 자식 간 cache 공유는 하지 않는다. vendor별 실측 증거가 없으면 unknown이다.

## 7. 기본 운영값의 성격

core memory·skill·도구 예산과 thresholds는 검토할 초기 정책이지 연구에서 입증된 최적값이 아니다. 사용자 핵심 의무는 숫자에 맞추어 삭제할 수 없다. 공개 모델이 하나뿐이면 하나의 조건에서만 측정했다고 보고하고 다른 모델 호환성을 추정하지 않는다.
