# 평가 4-1–4-4 · 실행 원장·호출 계측·지표·Trace 조회 상세 설계

문서 유형: 목표 상세 설계. 상태: planned. 현재 `events/coverage.py`는 누락 집합 계산만 제공하며, 전수 이벤트 수집·장기 저장·조회 UI가 완성된 것이 아니다. 소유 WP13/RC40–RC42, 제품 인수는 WP23/RC43, broker·runtime 연결은 WP02/WP06와 공유한다.

## 1. 전체 모니터링의 범위

관측 대상은 Cyrano가 접수한 request와 관리하는 dcode 실행·자식 작업이다. 다른 IDE의 임의 프로세스, provider 내부 비공개 추론, 계측되지 않은 사용자 shell을 전부 본다고 주장하지 않는다. 모델의 공개 메시지·짧은 근거·도구·결과만 수집하고 비공개 chain-of-thought 저장을 요구하지 않는다.

4-1의 요청별 단계는 `intake -> interview/spec -> plan -> plan_review -> approval -> dispatch -> change -> verification -> result_review -> final -> learning`이다. 반복 review, replan, pause, cancel, restart, rollback은 실제 분기로 표현하며 단순 성공 직선으로 덮어쓰지 않는다. 학습이 비활성이면 disabled 정책 event를 표시한다.

## 2. event envelope와 신뢰

모든 durable event에 `event_id, event_type, schema_version, tenant_id, workspace_id, request_id, run_id, parent_run_id, producer_id, producer_epoch, producer_seq, occurred_at, ingested_at, trace_id, span_id, parent_span_id, policy_digest, release_digest, payload_ref, payload_digest, authority, sensitivity`를 기록한다. request/run 없는 운영 event는 명시 kind로 분리한다. critical event의 scope/run 연결은 server principal에서 정하고 model JSON에서 신뢰하지 않는다.

producer 재시작 시 epoch가 바뀐다. unique `(producer_id, producer_epoch, producer_seq)`와 event_id로 중복을 제거하며 같은 키·다른 payload는 `EVENT_IDEMPOTENCY_CONFLICT`. 중앙 commit_seq는 durable 저장 순서이지 분산 발생 시각의 전체 순서가 아니다. duration은 같은 process boot의 monotonic 시간으로 측정하고 wall-clock 차감으로 계산하지 않는다. 서로 다른 process의 span latency는 coordinator 측정/수신 시각 기반이면 추정으로 표시한다.

4-2의 주요 producer:

| 영역 | trusted producer | 신뢰할 수 없는 대체 |
|---|---|---|
| 요구·계획·리뷰·승인 | domain service와 approval broker | model의 '승인받음' 문장 |
| 코드 변경 | Action Broker + output snapshot digest | tool가 보여준 diff 단독 |
| test 결과 | runner의 argv/env/exit/artifact | model의 'tests pass' |
| memory injection/application | context binder / application checker | 검색 hit, model 참조만 |
| LLM 실제 attempt | verified provider/native callback observer | after_model 횟수만 |
| promotion·rollback | release service transaction | candidate generator의 주장 |
| 외부 부작용·timeout | runner/connector receipt | timeout을 곧 실행 실패로 단정 |

## 3. native 계측 연결

`events/native_observer.py`는 native model/child callback에 연결한다. `events/tool_observer.py`는 request/deny/start/finish/failure/unknown을 관찰한다. `events/domain_sink.py`는 계획·승인·memory·learning domain event를 수집한다. `events/coverage.py`는 예상 source와 실제 probe를 비교한다. `events/reconcile.py`는 시작했지만 terminal이 없는 attempt를 recovery policy로 정리한다.

main middleware만 보면 child graph, summarization, tool-output offload, auto-classifier, rubric reviewer, SDK 내부 retry가 빠질 수 있다. 각 source/mode에 `observed_verified | unsupported | failed | not_tested`를 기록한다. 실제 native source가 없는 모드는 N/A 사유·inventory 증거가 필요하다. 기능이 존재하는데 계측이 없으면 unsupported/blocked이며 100% coverage로 보정하지 않는다. extension hook의 exit code만으로 전수 계측을 주장하지 않는다.

Cyrano와 native `CostTrackingMiddleware`가 같은 물리 호출을 기록할 수 있으므로 `(provider_request_id 또는 observer binding_id, attempt_no)`의 owner를 하나로 정한다. native 집계값은 비교용 source이고 두 합계를 더하지 않는다. provider request ID가 없으면 local invocation ID와 retry observer의 동일성을 확인하며 확실하지 않으면 metric completeness를 낮춘다.

## 4. 저장·outbox·backpressure

critical domain 상태 변경과 event append는 같은 DB transaction이다. Trace exporter 실패가 그 transaction 안에서 네트워크 대기로 번지면 안 된다. outbox consumer가 exporter를 호출하고 retry/backoff/lease/dead-letter를 관리한다. exporter down은 local 조회를 막지 않는다.

raw payload는 저장 전 분류·redaction·content hash를 수행한다. 승인키/API키/private key·access token은 원문으로 저장하지 않는다. 분류 실패는 quarantine 또는 metadata-only event이며 민감 본문을 임시 일반 로그에 기록하지 않는다. DB에 event는 있는데 payload가 없는 경우 redacted/missing 이유를 명시한다.

audit/control event는 기본 비샘플링이다. 저장 실패 시 governed mutation을 fail-closed한다. 대용량 model streaming chunk는 모두 durable 저장한다고 보장하지 않으며 final assembled message 또는 bounded payload artifact와 transient stream을 구분한다. crash 전 미완료 stream은 unknown/truncated로 기록한다. exporter queue full은 local persistence를 유지하고 lag alert; local audit 저장 자체 full은 해당 mutation 중지. UI용 로그 drop은 `telemetry.gap` 계수와 원인을 남긴다.

## 5. 실행 지표의 정확한 정의

| 지표 | 정의 | 반례 |
|---|---|---|
| request_elapsed_ms | request 접수→terminal의 coordinator monotonic duration | pause 시간을 별도 구분; active compute와 혼합 금지 |
| logical_llm_requests | unique logical_request_id 개수 | 2 retry가 있어도 1 |
| physical_llm_attempts | 실제 provider 전송 시작 attempt 개수 | 전송 전 denied는 제외 |
| llm_retry_count | 명시 retry attempt 수 | child/offload의 새 요청은 retry 아님 |
| tool_requested/started/completed/denied/unknown | 각각 별도 count | denied를 실행 성공 또는 실행 실패로 합치지 않음 |
| memory_* | queried/selected/injected/referenced/applied/effect를 별도 | injected를 applied로 계산 금지 |
| learning_candidates/evaluated/promoted/revoked | 상태 전이 기반 unique candidate count | 같은 outbox 재전송은 중복 아님 |
| input/output/cache_read/write | provider adapter semantics와 coverage 결속 | null→0 치환·총 input과 cached 합산 중복 금지 |
| cost_actual/cost_estimated/cost_unknown | billing source·rate version별 구분 | usage 불명 호출 예약을 성공 반환 금지 |
| p50/p95 latency | 완료/실패/취소 population과 N 명시 | success-only 통계를 전체로 표시 금지 |

예: L1의 A1 failed, A2 failed, A3 success이면 logical=1, physical=3, retries=2. subagent L2/A1은 logical=2, physical=4, retries=2. start only인 A4는 unknown outcome이며 success/completed count에 들어가지 않는다. duplicate event를 두 번 ingest해도 값은 변하지 않는다. finish-before-start ingestion은 pending projection으로 결속하고 시간 오류는 flag, 음수 latency를 0으로 덮지 않는다.

reducer는 순수 함수로 재구성 가능하고 `projection_version + last_commit_seq`를 갖는다. schema 변경 시 이전 projection과 새 projection을 병렬 재생해 비교 후 교체한다. high-cardinality run/model/trace IDs는 metric label에 전부 넣지 않고 trace lookup에서 조회한다.

## 6. 조회 서비스·UI 계약

| 구현할 메서드 | 입력·반환 | 권한/성능 |
|---|---|---|
| `list_requests(filter, cursor, limit)` | workspace/status/time 범위와 stable cursor, 요약 | ACL을 query에서 적용; max limit; 빈 결과/오류 구분 |
| `get_timeline(request_id, after_seq)` | commit_seq 순 event와 causality refs | reconnect cursor·중복 제거; 알 수 없는 stage 표시 |
| `get_trace(trace_id)` | spans tree + orphan/missing markers | 부모가 없다고 다른 scope 검색 금지 |
| `get_failure(run_id)` | first failed stage, cause_evidence, alternative/unknown | model speculation은 hypothesis label |
| `get_artifact(ref)` | redacted content 또는 denied/expired/missing | symlink/path traversal 금지; control root 파일 직접 노출 금지 |
| `stream_request(request_id, cursor)` | SSE 또는 poll adapter | backlog 재전송; client state에서 approve 금지 |
| `export_bundle(request_id)` | scope-redacted event+artifact manifest | export consent·보존·삭제 영향 추적 |

기본 사용자 화면은 dcode 내부 Textual Monitor이며 `/cyrano`의 native 명령·screen·인증 query를 구현한다. 별도 브라우저 dashboard는 필수가 아니다. headless용 read-only JSON 조회도 같은 query service를 사용한다. 자세한 메뉴·stream·focus·권한·원시 evidence 연결은 [Native Monitor 설계](NATIVE_MONITOR_TUI.ko.md)를 따른다. localhost binding은 인증을 대신하지 않으며 mutation은 별도 승인 API로 분리한다.

화면 상태는 `passed`, `failed`, `blocked`, `cancelled`, `unknown`, `not_run`, `disabled`를 구분한다. 오류 상세의 경로·argv·tool result에 비밀이 없는지 렌더 전에도 확인한다. 4-4 수용은 API JSON 존재만이 아니라 새 session/read-only 사용자로 요청을 찾아 실패 step과 원시 근거까지 탐색하는 end-to-end 검사다.

## 7. 복구·보존·성능

writer crash 후 다음 boot에서 orphan attempt를 찾는다. 외부 side effect가 있을 수 있으면 idempotency key/remote receipt 조회로 reconcile하고 무조건 다시 실행하지 않는다. 오래된 worker의 terminal 결과는 fencing token으로 거부하되 새로운 위험 근거는 incident candidate로 별도 보존한다.

보존 기본값은 승인한 policy revision에 기록하며 trace metadata, body, audit 각각 다를 수 있다. 삭제는 memory/learning evidence와 의존성이 있으므로 `source_missing` 상태를 반환하고 성공 근거로 사용하지 않는다. 원장 삭제를 모델 임의 learning candidate로 수행하지 않는다.

부하 시험은 N producer·payload size·retention·database 크기·queue cap·p95 ingest/조회 목표를 사전 고정한다. 초기 개발 수치는 최적값이 아니며 이번 ZIP에 성능 실측을 주장하지 않는다. 지표 coverage가 떨어지면 alert와 평가 invalid/partial 규칙을 적용한다.

## 8. 수용 연결

RC40은 domain timeline과 transactional outbox, RC41은 호출 coverage·retry/latency reducer, RC42는 storage/query/redaction/ACL, RC43은 UI·crash·부하·native 요청 완주 검사를 소유한다. 현재 4-1–4-4 사례와 추가 반례를 모두 수행한다. [실행 계획](../execution/MEMORY_OBSERVABILITY_RUNBOOK.ko.md)에서 실패·취소·재시도·worker crash 주입 절차를 따라야 한다.

## 1. 이벤트와 권위

모든 모델-visible 내용의 출처와 runtime-effective 설정은 참조 가능한 manifest에 남긴다. 다만 secret·개인정보 보호 때문에 원문을 보관하지 않으면 reconstructable이라고 주장하지 않는다. 공개 행동·도구·결과·짧은 근거를 기록하고 비공개 추론 수집을 요구하지 않는다.

Domain event는 producer 권한과 schema를 검증한다. model self-report, external worker report, trusted runner evidence를 구분한다. `work.completed`를 모델이 직접 append할 수 없다. 상태 변경과 대응 event/outbox를 같은 transaction에서 기록한다.

## 2. 모델 호출·비용 집계

logical_request_id, physical_attempt_id, parent_run_id, provider_request_id를 구분한다. 단일 logical 요청에 첫 시도+2 retry이면 attempts=3,retries=2다. provider 내부 retry가 보이지 않으면 coverage gap이며 zero가 아니다. child/offload/reviewer/classifier/warming을 별도 operation_kind로 분류한다.

usage normalization은 provider별 accounting_semantics를 가진다. 입력 총량에 cached input이 포함되는지 확인 전에는 input-cached 계산을 하지 않는다. 누락값은 null이고 coverage 분모에 누락 비율을 함께 표시한다. 과금 확정이 없는 timeout은 예약 budget을 취소된 작업 비용 0으로 즉시 반환하지 않는다.

## 3. 내부 CLI 화면

R5의 `/cyrano` 내부 TUI 설계를 유지한다. 새로운 외부 dashboard를 기본 UI로 만들지 않는다. 요약·흐름·호출·변경/검증·기억·개선·도구/상태 탭에 이 설계의 epoch/normalization/lease/unknown effect를 추가할 목표다. 기존 slash registry와 실제 handler를 검증해 최소 native patch로 연결하며 extension API에 없는 custom command 등록을 가정하지 않는다.

read query는 LLM 없이 event read model로 처리한다. UI 목록은 최근 N개와 전체 aggregate를 별도로 보인다. producer seq·committed event_seq와 wall time을 혼동하지 않는다. 동일 프로세스의 duration은 monotonic으로 계산하고 다른 프로세스 timestamp 차이를 정확한 latency로 사용하지 않는다.

cursor 만료·queue overflow는 gap marker와 snapshot 재동기화로 처리한다. 이벤트를 조용히 버리지 않는다. 권한 거부·연결 오류 발생 시 민감한 이전 상세 view를 비운다. UI에서 화면 닫기를 누른 것은 모델 실행 cancel이 아니다. query 취소와 work cancel의 명령을 구분한다.

## 4. Evidence bundle

Bundle은 source+candidate+runtime+policy+plan+test-suite+release digest와 실행 argv·환경·종료코드·stdout/stderr ref·test ids·coverage·known limitations를 가진다. 의도한 검사와 실행한 검사를 별도로 표시한다. schema fixture 통과는 제품 수용 통과가 아니다. 결과가 zero tests일 때 exit0이더라도 해당 필수 suite는 완료되지 않았다.

해시 체인은 변경 탐지 수단이지 외부 신뢰 root 없는 전면 위조 방지가 아니다. 승인 키·sealed 평가 데이터·전달된 artifact 저장소를 agent와 분리한다. 임의 파일을 evidence라고 제출해도 trusted runner attestation 없이는 완료 근거가 아니다.

## 5. 복구

1. process lease를 확보하고 이전 generation을 종료한다.
2. 마지막 committed state/event/outbox를 읽는다.
3. pending effects를 read-only로 조사한다.
4. provider/remote request id와 workspace manifest로 이미 발생한 효과를 연결한다.
5. 명확한 read-only retry와 검증된 idempotent operation만 재시도한다.
6. source/policy/permit drift가 있으면 필요한 review를 다시 받는다.
7. resume 이벤트와 새 fencing token을 기록한 뒤 dispatch한다.

LangGraph checkpoint는 모델 대화를 복구하는 기반이다. 그것만으로 외부 파일·DB·push가 한 번만 실행되었다고 보장하지 않는다. 노드 재실행에서 effect가 반복될 수 있는 위치를 찾아 task/effect fence로 분리한다. [NS56·NS57](../reference/SOURCES.ko.md#ns56)

## 6. 외부 exporter

OpenTelemetry는 선택 adapter다. 도메인 원장이 진실 원천이며 exporter 실패로 event를 잃지 않는다. local spool에 backpressure 상한을 두고 메타데이터·원문 export 정책을 분리한다. Langfuse/Jaeger/Tempo를 새 필수 서버로 설치하지 않는다. 버전 있는 exporter mapping이 domain schema 변경을 강요하지 않게 한다.

신뢰된 audit 저장이 실패하면 새로운 위험 행동은 차단한다. 비필수 원격 trace 전송 실패는 업무 완료 자체와 분리하되 누락 상태를 표시한다. exporter lag/telemetry gap을 Self-Improvement가 자동으로 무시하도록 수정할 수 없다.

## 이벤트와 UI의 보안·수명주기

모니터 탭의 producer는 일반 모델 도구가 아니다. tool/model 원시 결과는 runner가 발생 사실을 확인한 관측이며 내용 자체는 untrusted일 수 있다. JSON의 `producer=trusted_runner` 문자열만으로 그 출처를 인정하지 않는다. 인증 context와 등록된 producer identity가 일치해야 한다.

단일 호출의 usage가 stream fragment, final response, native aggregate에 중복 나타나면 actual attempt ID로 합친다. final usage는 누적 snapshot인지 delta인지 adapter contract를 확인한 뒤 반영한다. 동일 provider_request_id가 없는 제공자는 service가 발급한 물리 attempt ID를 사용하고 추정 key로 서로 다른 호출을 합치지 않는다.

권한 실패/조회 실패 후 이전 민감 화면을 유지하지 않는다. 서버 쪽 목록 query에서 scope를 먼저 적용하고 정렬·집계를 수행한다. private 내용 없이 상태를 전달할 수 있으면 denied/stale 표시만 유지한다. 종료된 monitor worker가 늦게 도착한 결과를 새 thread 화면에 쓰지 못하도록 view generation을 확인한다. 화면의 닫기는 조회 취소이고 업무의 취소가 아니다.

redaction 실패 시 body를 격리하고 최소 metadata만 저장한다. control audit 저장 실패는 위험 효과를 시작하기 전에 fail closed; 선택적 exporter 장애는 local authoritative 저장이 정상일 때 결과와 분리해 경고한다. 로그 hash chain의 존재는 trusted head·storage/producer 보호·누락 검사가 없으면 완전성 보장이 아니다.
