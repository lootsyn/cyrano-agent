# 데이터 계약·알고리즘·어댑터 동작·검증 상세

## 28. 스키마 적용 규칙

`contracts/*.schema.json`은 JSON Schema Draft 2020-12다. 모든 업무 객체의 `additionalProperties`는 false이며, `api-dtos.schema.json`은 `$defs`에 DTO를 모은 문서다. API에서 이 파일 루트에 대해 아무 JSON이나 validate하면 안 된다. 반드시 endpoint가 지정한 `#/$defs/WorkPlan` 같은 DTO reference로 검증해야 한다.

기본 식별자는 1–128자의 영숫자·점·밑줄·콜론·하이픈이다. 신규 session/run/event/receipt ID는 서버가 UUID를 생성하되 외부 표기는 이 형식에 포함되는 문자열이다. 원본 인터뷰의 `dec-1`, `R01` ID는 유지한다. digest의 wire 형식은 `sha256:` 뒤 lowercase hex 64자리다. 시간은 timezone이 포함된 RFC3339 문자열이며 저장 기준은 UTC, 사용자 화면은 Asia/Seoul 등 사용자 설정으로 렌더링한다.

프로토콜/인증/오류·usage 형식 차이를 처리하는 transport adapter는 허용한다. 이것은 모델의 추론 성향에 따라 prompt나 workflow를 바꾸는 모델 특화 계층이 아니다.

금액·비율·측정 score의 정확한 소수는 문자열로 직렬화한다. canonical signing 객체에 float를 넣지 않는다. JSON Schema 통과는 서명·권한·참조·신선도·DAG·완료 검증을 대신하지 않는다. JSON 파서는 중복 key를 기본 last-wins로 처리하지 말고 `object_pairs_hook`으로 중복 key를 거부해야 한다. 서명 검증 전에 비정상 Unicode surrogate, 너무 깊은 중첩, 과대 정수/문자열/배열을 제한한다.

### 28.1 계약 목록과 추가 의미 검사

| 파일 | 주요 필드 | 스키마 후 반드시 검사할 사항 |
|---|---|---|
| work-plan | spec/snapshot/policy/release digest, scope, WorkUnit DAG | 참조 존재, 요구·시나리오 coverage, cycle, 파일 충돌, 명령·예산 권한 |
| worker-result-v2 | role/assignment/base revision/input digest/proposals/findings | 실제 배정·role·principal, stale 처리, 제안의 비권위성 |
| review-result | assignment/reviewer/input/checklist/blind manifest | 작성자와 reviewer 분리, 정확한 입력, 필수 checklist·미해결 findings |
| approval-receipt-v2 | actor/user/display/action/bindings/Ed25519 | trusted human provenance, 서명, issuer, 만료, 철회, 세션·scope 일치 |
| execution-permit | parent approvals/task/sandbox/preimage/epoch | 승인에서 넓어지지 않음, 사용 횟수·기간, 현재 정책, Broker 발급 |
| memory-record | kind/scope/status/content/evidence/freshness/release | ACL, 관측 근거, 사용자 권한, supersedes cycle, 활성 projection |
| learning-candidate | parent/target/원인/대안/criteria/rollback/budget | exact patch, 금지 변경, 평가 자료 접근, 승인 필요 여부 |
| evaluation-report | baseline/candidate/split/criteria/metrics/verdict | task-family 분리, 실제 실행, evaluator 권한, hard gates·불확실성 |
| verification-result | check/recipe/postimage/runner/status/evidence | 실제 runner provenance, command, 테스트 수·skip·현재 postimage |
| change-manifest | permit/preimage/postimage/changes/apply_status | 파일별 create/modify/delete 의미, 승인 scope, unexpected paths |
| context-manifest | layers/digests/view/limits/usage | 실제 주입·wire 관측과 구분, security epoch, 누락 usage |
| event-envelope | source/producer/seq/trace/type/typed payload | principal이 주장한 producer인지, 참조 scope, 허용 상태 전이 |
| adapter-report | actual versions/checks/status/coverage | verified는 실제 evidence 존재·유효성, governed_ready 서버 계산 |
| run-report | 상태/승인/변경/검증/review/gap/assessment | 완료를 current truth에서 계산, 모델 자기 보고 수용 금지 |
| api-dtos | request/response와 공통 object `$defs` | endpoint별 DTO 선택, envelope/auth/CAS/idempotency 별도 적용 |

`change.operation=create`는 before_digest=null, after_digest!=null이다. modify는 양쪽 non-null이며 delete는 before!=null, after=null이다. status=passed라도 pytest 테스트 수 0·전부 skip·필수 assertion 미실행이면 통과로 인정하지 않는다. 필요한 경우 단순 lint처럼 test count가 적용되지 않는 recipe에만 count=null을 허용한다.

`adapter_report.governed_ready`와 `run_report.status`는 서버가 계산하는 response 전용 필드다. worker가 동일 schema 모양으로 업로드해도 authoritative 결과로 채택하지 않는다. 동일 객체의 입출력 권한을 endpoint·인증 주체에서 분리한다.

### 28.2 API validation 순서

`size/depth/encoding → duplicate key → JSON Schema → auth principal → workspace/session binding → idempotency → expected revision → domain semantics → effect authorization → transaction` 순으로 처리한다. signature는 서명 대상 bytes에 대해 수행하며 승인·효과 검증 과정에서 반드시 끝나야 한다. 인증 전에 불필요한 비싼 schema/서명 작업이 일어나지 않도록 transport 인증은 맨 앞에서 선행할 수 있다.

새 session 생성의 expected_control_revision은 0이다. 일반 mutation에는 현재 revision을 사용한다. 외부 model/telemetry ingestion은 일반 domain mutation endpoint를 공유하지 않고 observer 권한의 event ingestion 경로를 둔다. 외부 이벤트의 event_seq는 caller가 지정하지 못하고 DB가 부여한다. 이벤트 producer_seq는 인증된 producer별로 검증한다.

## 29. dcode 어댑터와 기능 연결

### 29.1 실제 도구 contract

다음 UDH tool 이름은 본 설계에서 새로 구현한다. dcode 내장 명령/도구로 오인하면 안 된다.

| Tool | 허용 주체·단계 | 입력 | 출력/효과 |
|---|---|---|---|
| udh_session_view | bound worker | 현재 run binding | 상태/blockers/작업 ID; 임의 session 조회 불가 |
| udh_next_action | facilitator | 현재 revision | 질문·조사·검토·대기 typed action |
| udh_submit_result | assigned worker | WorkerResult | 제안 적용/격리 결과; READY 직접 설정 불가 |
| udh_submit_plan | planner | WorkPlan | 검증된 artifact receipt; review 대기 |
| udh_submit_review | assigned reviewer | ReviewResult | 검토 evidence 등록; 승인 발급 아님 |
| udh_request_approval | host/worker | ApprovalRequest | 표시 bundle; approve tool은 없음 |
| udh_read_artifact | scope-bound worker | artifact_id+digest | bounded content·출처·신선도 |
| udh_memory_search | phase worker | MemoryQuery | scope 제한 MemoryView |
| udh_memory_read | scope-bound worker | selected memory_id+view digest | 선택된 기록의 bounded body |
| udh_memory_propose | allowed worker | candidate MemoryRecord | 제안만 저장 |
| udh_apply_patch | approved implementer | task/permit/preimage/patch artifact | Broker 적용·postimage·change manifest |
| udh_execute_recipe | approved worker | ActionRequest(EXECUTE) | operation ID·result·unknown outcome 구분 |
| udh_propose_improvement | learning analyst | Candidate | 후보 저장, 코드/정책 직접 수정 없음 |

작업 완료는 단순 tool의 문자열 `done`이 아니라 task artifacts와 VerificationResult를 Action/Reporting Service에 제출하고 completion kernel가 판정한다. Native file/shell 도구는 읽기 capability가 검증된 경우에만 활용하고, 모든 write는 UDH Broker 경로로 모은다. SDK mandatory filesystem/subagent middleware를 억지로 제거하지 않는다. 기존 native 도구가 write를 시도하면 안정된 오류 code와 허가된 Broker tool 경로를 안내한다.

`ToolMessage.tool_call_id`는 원래 요청과 일치해야 하고, 예외·취소는 성공 메시지로 포장하지 않는다. subagent 응답과 graph state update가 필요한 native tool은 실제 설치 버전의 반환 contract를 검사한다. adapter가 이를 확인하지 못하면 해당 경로를 governed에서 활성화하지 않는다.

### 29.2 원본 저장소의 자동 실행 설정

기존 프로젝트에 `.deepagents`, plugin, hooks, MCP 설정이 있더라도 자동으로 신뢰하지 않는다. 전용 DEEPAGENTS_HOME에는 기존 trust 기록을 복사하지 않는다. 원본 근거 snapshot은 보존하지만 실행 view의 자동 확장 discovery는 검증된 설정으로 통제한다. 프로젝트 prompt는 개발 정보이지 UDH 승인/보안 policy보다 상위 권한이 아니다.

dcode가 untrusted project extension을 user extension보다 먼저 실행할 수 있는 조합에서는 OS 격리와 프로젝트 자동 실행 차단을 함께 검증한다. 필요하면 자동 실행 파일을 노출하지 않는 별도 launch view와 read-only evidence mount를 사용하며, 원본 저장소 파일을 삭제·이동·수정하지 않는다. 이때 제외 목록·원본 hash·launch-view hash를 모두 기록한다. 존재하지 않는 CLI flag로 discovery를 껐다고 주장하지 않는다.

### 29.3 개발 bootstrap이 자신의 gate를 우회하지 않게 한다

UDH 자체를 만드는 첫 작업에는 완성된 UDH가 없으므로 `WP00–WP03`의 계획·리뷰·승인은 외부 구현 에이전트와 실제 사용자 검토로 남긴다. 이를 UDH가 강제했다고 보고하지 않는다. Broker/kernel 구현 후에는 자체 테스트 프로젝트에서 dogfooding을 시작하고, 검증되지 않은 자신을 승인 발급자로 등록하지 않는다.

## 30. 결정적 알고리즘의 상세 기준

### 30.1 Interview action 선택

입력을 기존 UserEvent/Decision과 먼저 대조한다. 열린 obligation 각각에 대해 필요한 것이 사람의 의도인지 현재 사실인지 구분한다. 현재 파일·문서로 확인할 수 있으면 INSPECT/RESEARCH가 먼저다. 접근 불가이면 같은 질문을 단순 반복하지 말고 필요한 접근 범위 또는 사용자 판단을 요청한다. 행동 차이가 결과·권한·비용·호환성에 영향을 주는 결정만 사용자 질문으로 올린다.

후보 행동은 `critical blocker 해소 → irreversible/high-impact 의도 → 다른 결정을 막는 dependency → 확인 비용이 낮은 사실 조사 → 선택적 품질 조언` 순서로 선택한다. 동점은 obligation 생성 순서와 ID로 결정한다. expected information gain을 LLM의 정밀한 확률처럼 계산하지 않는다. 제안 점수는 우선순위 참고일 뿐 readiness와 authorization에는 사용하지 않는다.

budget 또는 질문 soft limit을 만나면 미해결 의무·완료 가능한 다음 단계·추가 승인 필요를 표시한다. 사용자가 충분한 명세를 이미 제공했다면 질문 0회도 정상 경로다. 필수 검토까지 생략한다는 뜻은 아니다.

### 30.2 Memory 검색

1. 인증된 principal로 global/workspace/session/task 접근 가능 집합을 계산한다.
2. 해당 scope에서 active이고 현재 release view에 속한 memory ID를 구한다.
3. task requirement ID, 경로, tag 일치를 계산하고 허용된 FTS 질의를 수행한다.
4. evidence digest/TTL/사용자 정정을 확인한다. stale 기록은 별도 재검증 후보로 분리한다.
5. 정렬 키는 requirement 일치 수(desc), path 일치 수(desc), tag 일치 수(desc), 텍스트 검색 rank, verified_at(desc), memory_id(asc)다. 검색 backend가 반환하는 rank 방향을 adapter 단위 테스트에 고정한다.
6. 동일 내용 digest를 중복 제거하고 상충 authority 기록은 conflict로 올린다.
7. top-k와 context budget을 동시에 지켜 결과를 만든다. 선택되지 않은 기록 원문은 LLM에 전달하지 않는다.
8. exact record IDs/digests로 MemoryView를 만들고 context manifest에 주입 결과를 남긴다.

검색 결과를 먼저 top-k로 잘라놓고 나중에 권한 filter를 적용하지 않는다. 전체 scope의 결과 수·제목도 권한 밖 사용자에게 노출하지 않는다. FTS query는 SQL parameter로 전달하며 구문 오류는 bounded query normalization 또는 명시적 오류로 처리한다. 임의 SQL 생성은 사용하지 않는다.

### 30.3 Context budget

유효 context 한도는 실제 metadata 또는 운영자가 명시한 상한이다. `input_budget = effective_limit - output_reserve - verified_request_overhead - reserved_tool_growth`로 계산한다. tokenizer와 정확한 크기가 없으면 추정 방식·오차·상한의 출처를 보고하며 모델 한도를 발명하지 않는다.

고정 policy, 현재 계약/승인/미해결 사항, 필요한 tool schema는 필수 블록이다. 초과 시 큰 tool output을 artifact로 offload → 비관련 retrieval 제거 → 중복 기억 제거 → 오래된 비핵심 대화 요약 순서로 줄인다. 현재 acceptance·승인·blocker·검증 근거 ID를 줄여 false-ready를 만들면 안 된다. 그래도 초과하면 작은 WorkUnit으로 재계획하거나 운영자 budget/호환 설정을 요청한다.

요약 모델도 별도 model attempt로 계측한다. 원 provider의 서명된 reasoning block 또는 tool-result pairing을 임의 편집하지 않는다. UDH는 자신이 소유한 block만 변환하고 native context-compaction은 호환 테스트를 거쳐 사용한다.

### 30.4 Cache 실험 절차

캐시를 지원하는지 미리 가정하지 않는다. 공개 endpoint 조건/버전과 실제 usage adapter를 기록하고 동일한 안정 블록·tool schema·memory view·phase에서 반복 호출한다. 최초 관측 요청을 `first_observed`라고 부르고 provider cache가 이미 비어 있다고 확정하지 않는다. 같은 세션과 새 세션의 prefix 재사용을 각각 관측한다.

다음 실험은 한 변수씩 바꾼다: task tail, memory release, tool schema, phase, 모델/endpoint 교체. 실제 cached input token·cache write·latency·비용을 별도 필드에 기록한다. provider가 usage를 제공하지 않으면 “구조상 동일 prefix 확인, provider hit 검증 불가”로 결과를 분리한다. 캐시 테스트가 실제 소스 변경·테스트 결과의 response cache를 재사용해서는 안 된다.

### 30.5 Evaluation과 승격 판정

EvalSpec에는 primary outcome, 최소 실질 개선, non-inferiority 허용폭, 비용·지연 상한, 반복 수, 데이터 split, hidden acceptance, 중단 규칙을 실행 전에 고정한다. 수치가 미정이면 사용자/정책 결정을 받아야 하며 실행 후 좋은 결과에 맞춰 고르지 않는다.

동일 task-family의 baseline/candidate 결과를 쌍으로 보관하고 효과·불확실성을 보고한다. 개선 기준 충족과 비회귀 기준 충족을 따로 계산한다. 결정 규칙은 `invalid evidence → invalid`, `hard failure 또는 확인된 regression → regressed`, `기준 충족을 확인할 수 없음 → inconclusive`, `개선+모든 비회귀 충족 → improved`다. improved만 promotion 검토에 들어가고 승인 없이 활성화하지 않는다.

harness 전체를 모델마다 달리 만들지 않는다. 여러 모델을 비교 평가하더라도 똑같은 release를 대상으로 하고, 미검증 모델에 대한 일반화 주장은 하지 않는다. 모델 교체 후 API/tool protocol 연결 검사는 필요한 상호운용성 검사이지 모델 지능을 채점하는 특화 시스템이 아니다.

### 30.6 납품·취소의 종료 조건

`delivery_mode`는 계획과 session 생성 계약의 필수 필드다. patch_only 완료는 검증된 변경 patch 납품이며 원본이 바뀌었다는 뜻이 아니다. apply_to_source 완료는 원본 적용 승인·preimage 확인·실제 반영 manifest·필요한 최종 검증까지 포함한다. 원본 반영이 실패한 상태에서 검증된 patch가 존재한다는 이유로 전체 요청을 완료 처리하지 않는다.

취소 요청은 즉시 새 dispatch를 중지한다. 실행 중 operation이 있으면 CANCELLING이고, 효과가 정리된 뒤 CANCELLED다. 부분 변경·unknown outcome이 있으면 RECONCILING에서 실제 상태와 복구 선택을 보존한다. 취소는 이미 실행된 부작용의 자동 소거가 아니다. 정식 전이표는 `state-machine.catalog.json`이며 정의되지 않은 전이는 INVALID_TRANSITION이다.

## 31. 회귀 테스트 명세와 실행 증거

`fixtures/acceptance-cases.json`의 124개 Given/When/Then은 **구현하고 실행해야 할 수용 테스트 명세**다. R01–R22는 첨부본의 원문을 보존한다. 추가 102개는 PLAN, AUTH, RUN, CACHE, MEM, LEARN, OBS, PY, OPS 그룹으로 구성한다.

`fixtures/valid`는 wire schema의 정상 예시이지 실제 runtime 결과가 아니다. schema-only execution permit의 signature는 유효 서명이 아님을 명시했다. approval receipt 예시만 일회성 테스트 키로 실제 서명했고 공개키만 포함한다. 이 키/issuer는 production trust store에 등록하면 안 되며 expiry도 예시 시각에 고정되어 있다.

`fixtures/invalid`는 잘못된 worker 승인 필드, 빈 계획, 모델특화 임의 필드, float 금액, 경로 탈출, plan 없는 실행 승인, 서명 downgrade, 승인 없는 active memory, eval 없는 승격, holdout 없는 improved, 실행 없는 passed, 거짓 completed, 잘못된 event payload, 음수 token을 검증한다.

`reference/kernel_oracle.py`의 입력은 **이미 신뢰된 사실로 구성한 합성 test fixture**다. real endpoint가 이를 받아 승인 true를 믿는 구현으로 복사하면 안 된다. 이 reference는 readiness·canonicalization·DAG·promotion의 작은 명세를 실행 가능하게 만들 뿐, dcode middleware/Broker/격리를 구현한 것이 아니다.

### 31.1 재현 방법

검증 도구에는 Python, jsonschema, cryptography가 필요하다. 사용자 환경에서 실행한다면 별도 문서 검증용 venv를 만들고 의존성을 고정한 뒤 아래를 실행한다. 대상 프로젝트 venv에 설치하지 않는다.

```bash
python tools/validate_package.py
python -m unittest discover -s reference -p 'test_*.py' -v
```

이 결과와 실제 제품의 pytest/quality/E2E 결과를 다른 보고서로 남긴다. package validation PASS를 요구사항 40/40점으로 환산하지 않는다.

## 32. 구현 산출물과 납품 기준

각 WP는 코드, 실제 단위/통합 tests, schema/DB migration이 있으면 그 변경, 운영 문서, 실행 명령·exit·환경·artifact hash, 독립 review를 함께 납품한다. 최종 납품에는 `runtime-lock.json`, `compatibility-report.json`, `source-install-diff.json`, `governed-e2e-report.json`, `memory-evidence.json`, `cache-observation.json`, `evaluation-report.json`, `release-history.json`, `monitoring-coverage.json`, `quality-report.json`, `requirements-40point-evidence.json`이 필요하다.

모든 증거 객체는 report 참조와 digest를 가지며 `not_run / not_tested / unsupported / inconclusive`를 표현한다. 이러한 상태를 숨겨 테스트를 줄이거나 기능을 빼서 완료시키지 않는다. 릴리스 범위의 네 추가 요구사항은 **설정 존재가 아니라 실제 행동과 실행 증거**로 판정한다.
