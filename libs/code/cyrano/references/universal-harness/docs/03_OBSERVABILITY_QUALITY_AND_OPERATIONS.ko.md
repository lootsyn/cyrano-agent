# 전체 개발 과정 모니터링·Python 품질·운영·출시 판정

## 14. 전체 개발 작업 모니터링

### 14.1 관측 범위

모니터링은 LLM token 표 한 장이 아니다. 사용자 접수, 인터뷰 질문·결정, evidence 수집, 명세·계획 리뷰, 승인·거부·철회, worker dispatch, 모델 attempt, tool 실행, 파일 변경, 테스트/리뷰, 메모리 사용, 학습·평가·promotion·rollback, 중단·복구까지 하나의 session timeline으로 연결한다.

“전체”는 **UDH에 등록되어 실행되는 dcode 및 그 통제된 자식 작업의 관측 가능한 활동**을 뜻한다. 모델 내부의 비공개 추론, 계측하지 않은 다른 IDE assistant, provider 내부 인프라를 모두 감시할 수 있다고 주장하지 않는다. 모델의 공개 행동·짧은 근거·도구·결과를 기록하며 private chain-of-thought 수집을 요구하지 않는다.

### 14.2 관측 경로

| 관측 대상 | 1차 수집 | 보완 경로 |
|---|---|---|
| 사용자 입력/세션 lifecycle | dcode client hooks, trusted host adapter | launcher 시작/종료·heartbeat |
| 요구·계획·리뷰·승인 | Kernel/Broker 원장 | immutable bundle manifest |
| 모델 호출/stream/retry | middleware + runtime callback | 검증된 transport/usage adapter |
| tool 호출/허용/거부/결과 | ToolMediator + Action Broker | sandbox runner process record |
| subagent | Scheduler/worker binding | native task lifecycle hooks |
| 파일 변경 | Broker pre/postimage + sandbox diff | 원본 적용 전후 manifest |
| memory/skill | Memory service + context manifest | 파일/tool 조회 이벤트 |
| self-improvement | Learning/Evaluation/Promotion service | outbox/job state |
| 장애 | process supervisor·durable event store | reconciliation watchdog |

hooks만으로 모델 호출 전체를 계측했다고 하지 않는다. middleware callback이 놓치는 summarization 호출/child graph/내부 retry를 compatibility test로 드러낸다. 최종 `coverage_report`에는 수집 경로, 테스트 ID, 관측 성공 여부, 공백을 명시한다.

### 14.3 식별자와 event envelope

모든 event는 `schema_version`, `event_id`, `event_type`, `session_id`, `workspace_id`, `run_id`, `parent_run_id`, `task_id`, `trace_id`, `span_id`, `parent_span_id`, `producer`, `producer_seq`, `occurred_at`, `ingested_at`, `control_revision`, `policy_digest`, `release_digest`, `payload`, `payload_digest`, `sensitivity`를 가진다. worker가 존재하지 않는 부모/다른 workspace를 지목하면 거부한다.

`producer_seq`는 producer별 단조 증가다. 중앙 `event_seq`는 commit 순서이며 분산 이벤트 발생 순서와 동일하다고 가정하지 않는다. 소요 시간은 같은 프로세스의 monotonic clock으로 계산하고, UTC wall time은 표시/상관관계용이다. source signal은 trusted runner 관측과 model self-report를 구분한다.

### 14.4 핵심 event 종류

`session.started`, `session.paused`, `session.resumed`, `session.cancelled`, `session.completed`, `interview.question_proposed`, `interview.question_asked`, `user.answer_received`, `decision.proposed`, `decision.decided`, `decision.superseded`, `evidence.collected`, `evidence.stale`, `spec.compiled`, `plan.compiled`, `review.requested`, `review.completed`, `review.failed`, `approval.requested`, `approval.granted`, `approval.denied`, `approval.revoked`, `permit.issued`, `permit.denied`, `work.started`, `work.finished`, `work.rework`, `model.started`, `model.finished`, `model.failed`, `model.retry`, `tool.requested`, `tool.denied`, `tool.started`, `tool.finished`, `tool.failed`, `tool.unknown_outcome`, `file.changed`, `verification.finished`, `memory.queried`, `memory.selected`, `memory.injected`, `memory.referenced`, `memory.applied`, `memory.stale`, `learning.proposed`, `eval.finished`, `release.promoted`, `release.rolled_back`, `telemetry.gap`, `recovery.reconciled`를 초기 catalog로 고정한다.

세부 payload schema는 이벤트 유형별로 버전 관리한다. 임의 JSON body를 원장에 저장한 뒤 나중에 의미를 맞추지 않는다. 자유형 trace payload는 redacted blob로 저장하되 domain state 변경 API와 분리한다.

### 14.5 지표

| 영역 | 지표/정의 |
|---|---|
| 품질 | task outcome, false-ready, 중요 의도 위반, regression, rework |
| 인터뷰 | 질문 수, 중복 질문, 사용자가 답할 수 없는 질문, 보류·철회·승인 지연 |
| 계획 | requirement coverage, 추가 가정 수, plan review 실패, 승인 범위 이탈 |
| 실행 | tool attempts, logical operations, 실패/거부/재시도, execution vs approval wait |
| 모델 | 호출/attempt, input/output/cache tokens, first token/전체 latency, usage missing |
| 컨텍스트 | stable digest 유지, dynamic bytes, offload 크기, compaction, 근거 누락 |
| 메모리 | query/selected/injected/applied, stale 비율, cross-scope 차단, 효과 평가 |
| 학습 | 후보→평가→승격 수, inconclusive/reject, canary regression, rollback |
| 관측 품질 | event gap, orphan span, unmatched start/end, duplicate suppression, queue lag |

parent agent span 비용에 child model 비용을 더해서 이중 집계하지 않는다. 비용은 **실제 billable attempt leaf** 단위로 합산한다. retry 사용량이 provider 총계에 이미 포함되었는지 source별로 기록한다. provider가 비용을 제공하지 않으면 버전 있는 가격표로 추정하거나 unknown이다. 알려지지 않은 모델에 임의 0원 또는 다른 모델 가격을 대입하지 않는다.

cache tokens가 total input의 부분집합인지 별도 과금 항목인지 adapter의 `usage_semantics`로 정규화한다. 총 입력에서 cached input을 빼는 공식도 해당 semantics가 확인됐을 때만 쓴다. metric 없는 호출은 0이 아닌 null이며 `usage_coverage`를 함께 표시한다.

평균 latency 외에 p50/p95, 실패/취소 표본을 보존한다. model ID·prompt·session ID를 Prometheus식 high-cardinality metric label로 무제한 넣지 않고 상세 trace/event에서 조회한다.

### 14.6 trace 구조

```text
session S
  interview I
    evidence E
    model attempt M1
    review R1
  approval A1
  planning P
    planner worker W1
    independent reviewer W2
  approval A2 / execution permit A3
  work-unit T1
    model attempts
    tool operation O1
      approval_wait
      sandbox_execution
      postimage_capture
  verification V
  final-review F
  report Q
  learning-job L (별도 root, S에 link)
    candidate C / evaluation EV / promotion PR
```

OpenTelemetry로 traces/metrics/logs를 내보낼 수 있게 하되 UDH domain schema가 진실 원천이다. GenAI semantic conventions는 변경 가능성이 있으므로 exporter mapping version을 고정한다. 조회 당시 관련 문서는 별도 GenAI 저장소로 이동을 안내한다. unstable field명을 DB column 전체에 직접 박지 않는다. [S10]

LangSmith는 선택적 trace backend다. 특정 서비스 가입을 필수로 만들지 않으며 local event store/dashboard만으로 핵심 모니터링이 동작해야 한다. 외부 tracing을 켜기 전 payload 전송·민감정보·보존 정책을 승인받는다. [S11]

### 14.7 로컬 Dashboard

최소 화면은 Session List, Run Timeline, Plan DAG, Approvals, Changes & Verification, Memory Inspector, Learning & Evaluation, Runtime Health의 8개다. 목록 필터는 workspace/phase/status/risk/date로 제한하고 상세 trace에서 model/runtime 조건을 조회한다.

Timeline 항목을 누르면 관련 requirement/decision/plan/task/evidence/test를 왕복 탐색할 수 있다. 성공·실패·미실행·미확인·권한 거부를 색뿐 아니라 문구/아이콘으로 구분한다. model 주장과 runner 결과가 다르면 둘 다 표시하고 trusted 결과로 상태를 계산한다.

화면 갱신은 server-sent events 또는 polling adapter로 제공하며 cursor는 `event_seq`다. 재연결 시 마지막 seq 이후를 읽고 중복 event_id를 제거한다. 승인 mutation은 dashboard read stream과 분리된 authenticated POST를 사용한다. localhost binding만으로 인증이 됐다고 보지 않으며 origin/CSRF/session token 검사를 수행한다.

### 14.8 알림·복구

즉시 경보: 승인 우회, protected path 접근, cross-workspace memory, audit 쓰기 불가, unknown execution outcome, plan drift, 필수 검증 누락, 비밀 유출 의심. 일반 경보: budget 80% 사용, long-running 작업, 반복 실패, exporter queue lag, cache metrics missing.

threshold는 초기 policy이고 실제 작업 특성에 따라 조정 가능하다. 안전 경보를 Self-Improving이 자동으로 낮추지 못한다. 알림은 동일 incident key로 dedupe하고, acknowledge는 해결과 구분한다.

### 14.9 감사·개인정보

control events와 승인 이벤트는 기본 비샘플링이다. 대용량 model/tool 본문은 privacy policy에 따라 excerpt/hash/reference만 저장할 수 있다. 전체 prompt/source 본문을 기본적으로 외부 전송하지 않는다. 비밀 masking은 표시 시뿐 아니라 저장/전송 전 수행한다. 모델 context에 비밀이 필요하지 않도록 설계하는 것이 우선이다.

redaction 실패 또는 분류 불가 payload는 quarantine하고 body 없는 metadata를 남긴다. 개인정보 보존 기간 기본 예시는 일반 trace metadata 30일, 상세 payload 7일, 승인·정책 이력 90일이며 운영자가 목적과 의무에 맞게 승인한다. 법적 보존 의무를 이 설계만으로 판단하지 않는다.

hash chain은 변조 탐지 보조이고 동일 권한 공격자에 대한 불변 저장 증명이 아니다. governed 저장소는 agent/execution plane과 권한 분리하며, 필요한 운영에서는 서명 checkpoint와 별도 백업을 둔다.

## 15. Python 개발 품질: PEP8을 실행 가능한 게이트로

### 15.1 적용 범위

UDH 자체 Python 코드는 모든 quality gate 대상이다. 대상 프로젝트 Python 코드는 기존 프로젝트 규칙을 우선 조사하고 승인된 변경 범위에 적용한다. 설정 파일을 자동 삽입하거나 전체 저장소를 무관하게 재포맷하지 않는다. PEP8도 기존 프로젝트 관례와 호환성의 중요성을 인정한다. [S07]

본 UDH 기본 규칙: indentation 4 spaces, snake_case 함수/변수, CapWords class, UPPER_CASE 상수, import 그룹 분리, wildcard import 금지, 불필요한 compound statement 금지, public API docstring, 명시적 예외, 자원 context manager, typing 및 async cancellation 처리.

PEP8 기본 line length는 코드 79, prose comment/docstring 72이다. 팀 합의 88 같은 확장은 예외 profile로 기록할 수 있지만 “Black 기본 88이 PEP8의 원래 79와 같다”고 설명하지 않는다. UDH 자체는 기본 79/72를 채택한다. formatter만으로 PEP8 전체가 검증되지는 않는다. [S07]

### 15.2 도구 역할

Black을 유일한 formatter로 사용하고 Ruff는 lint/import/naming/docstring 검사를 담당한다. Ruff formatter와 Black을 동시에 자동 실행하지 않는다. mypy strict는 타입, pytest는 동작·회귀, 별도 security/dependency scan은 보안, 인간/독립 reviewer는 의미·설계·가독성을 확인한다. 타입 검사·보안 검사는 PEP8 그 자체가 아니라 추가 개발 품질 기준이다.

권장 configuration은 `config/python-quality.toml`에 제공한다. 실제 실행 버전은 uv.lock과 quality evidence에 고정한다. docstring/comment 72 검사는 별도 check를 추가하거나 검증된 lint rule 조합으로 수행한다. URL/표/예시 코드 등 예외는 사유와 경로를 기록하고 무차별 noqa로 숨기지 않는다.

### 15.3 품질 실행 순서

환경·기존 baseline 확인 → compile/import smoke → formatter check → Ruff lint → docstring/comment length → mypy → unit → integration → scoped acceptance → 필요 성능/보안 검사 → diff/contract review 순서다. 독립적으로 실행 가능한 읽기/검사는 병렬화할 수 있으나 모두 같은 postimage를 기준으로 해야 한다.

예시 명령은 UDH 개발 저장소에서만 다음 형태다. 대상 저장소의 명령은 조사 후 WorkPlan recipe로 고정한다.

```bash
uv run black --check --diff src tests
uv run ruff check src tests
uv run mypy src
uv run pytest tests/unit tests/contracts
uv run pytest tests/integration
```

코드 format 수정과 `ruff --fix`는 mutation이다. 계획·scope 허용이 있어야 한다. CI에서는 기본 check-only다. formatter가 바꾼 뒤에는 관련 tests를 동일 변경 상태로 재실행한다.

### 15.4 Python 세부 계약

Pydantic v2 DTO는 strict validation과 `extra='forbid'`를 사용한다. 파일·네트워크·subprocess 처리는 service/adapter 계층에서 하고 순수 domain 함수에 숨기지 않는다. `except Exception: pass`, shell=True 사용자 인수, unsafe YAML load, pickle 외부 입력, eval/exec 외부 payload는 금지한다.

모든 public 함수에 타입·docstring, typed error code, 취소/timeout 정책을 정의한다. 로그에 API key·raw credential을 넣지 않는다. retry는 재시도 가능한 오류만 bounded backoff로 수행한다. DB transaction 중 LLM/네트워크 장기 호출은 금지한다. asyncio loop 안에서 blocking subprocess/DB/file 작업을 무분별하게 수행하지 않는다.

재현 가능한 테스트를 위해 clock/UUID/random/provider/runner를 의존성 주입한다. 테스트는 fake를 사용한 것과 실제 sandbox/provider를 사용한 것을 명확히 분리한다. 정책 커널은 LLM 없이도 검사 가능해야 한다.

### 15.5 기존 실패 처리

기존 저장소의 lint/test 실패는 baseline에 기록한다. 새 변경이 만든 실패와 기존 실패를 구분하되 기존 실패가 관련 기능의 정확성에 영향을 주면 완료를 차단한다. “원래 실패”라는 이유로 모든 실패를 제외하지 않는다. 예외 승인은 specific finding/check ID·사유·책임자·만료·영향을 가진다.

Black의 기본 행 길이와 formatter가 구현하는 규칙 범위는 공식 문서와 구분해 적용한다. formatter 통과가 PEP8 전체 준수의 증명은 아니다. [S16]

## 16. 네 추가 요구사항의 40점 증거표

각 행은 2점이다. 실제 실행 증거가 없으면 0점, 일부/미검증이면 부분 점수를 사전 rubric에 따라 부여한다. 한 항목의 실패를 다른 항목 점수로 보상하지 않는다. release는 점수 외 hard gate도 통과해야 한다.

| 항목 | 2점씩의 다섯 기준 | 필수 산출물 |
|---|---|---|
| Python 기준 [10] | 스타일 정책, formatter/lint, typing/docstrings, tests/exception/security, 변경 범위 내 검토·CI | quality-policy, commands, versions, check results, review |
| 작업 전 계획·리뷰 [10] | 요구 추적, 구체 task DAG, 파일·명령·검증·복구, 독립 plan review, 실행 전 정확한 승인 | SPEC/PLAN/TRACEABILITY/review/receipt |
| Memory·Self-Improving [10] | persistence/scope, proactive recall 적용 증거, freshness/삭제/충돌, 후보+eval, 승인된 promotion+rollback | memory events, candidate, eval, release history |
| 개발 전체 모니터링 [10] | lifecycle/trace 연결, 모델·tool·변경·검증, 비용·cache·memory·learning, 장애·누락·복구, dashboard/privacy/완료보고 | event coverage, trace, report, incident drills |

hard gate: 무승인 실행 0, 위조 승인 통과 0, cross-scope 비밀 접근 0, 중요 요구 누락을 READY로 표시 0, 필수 검증 실패를 COMPLETED로 표시 0. 설계 문서·가짜 trace·미실행 fixture로 점수를 채우지 않는다.

## 17. 운영 Workflow와 사용자 경험

### 17.1 부트스트랩

`udh doctor` → 사용자 영역 runtime 생성 → plugin 및 policy digest 고정 → broker/sandbox 연결 → read-only smoke → safe fixture에서 전체 lifecycle 검사 → operator 승인 → governed 사용 순서다. 설치 전후 대상 repo manifest가 동일해야 한다. 승인키·서비스 계정·cloud trace 연결은 별도 setup 권한이다.

### 17.2 사용자 명령 표면

다음은 **개발할 UDH CLI**다. dcode built-in 명령으로 제시하지 않는다.

```text
udh doctor --runtime <runtime>
udh workspace register <path>
udh launch --workspace <id> --assurance governed -- dcode
udh session status <id>
udh session pause|resume|cancel <id>
udh approval show <request-id>
udh approval grant|deny <request-id>
udh memory search --workspace <id> <query>
udh memory revoke <id> --reason <text>
udh learning evaluate <candidate-id>
udh release promote|rollback <id>
udh report export <session-id>
```

`-- dcode`는 사용자가 지정한 검증된 executable을 런처가 시작한다는 의미다. 실제 dcode CLI flag는 `--help`와 adapter 검증으로 결정하며 존재하지 않는 flag를 만들어 호출하지 않는다. custom slash commands가 필요하면 나중에 공식 command surface가 제공되는지 확인하되 핵심 기능은 여기에 의존하지 않는다.

### 17.3 정상 개발 예

“CSV 처리 버그 수정” 접수 → memory에서 해당 workspace의 검증된 과거 회귀 조회 → 현재 소스·테스트 조사 → 오류 행 정책이 미정이면 결과 중심 질문 → 결정/acceptance 작성 → spec critic/blind review → spec 승인 → 구체 WorkUnit과 failing test 계획 → plan review → plan+실행 scope 승인 → 외부 사본에서 수정 → 각 작업 증거 → 품질/acceptance 실행 → 독립 diff review → 검증된 patch 및 보고 → 원본 반영 승인 → terminal episode → 후보 생성·eval·promotion workflow.

기존 원문에 오류 행 정책이 있으면 같은 질문을 다시 하지 않는다. read/test 권한이 없으면 조사·실험 요청을 분리한다. 모델 교체는 model/runtime 조건으로 기록하지만 별도 특화 설계를 만들지 않는다.

### 17.4 취소·외부 변경 예

사용자가 도중에 “부분 저장이 아니라 전체 취소”로 변경 → DECISION supersede → 관련 acceptance/work plan/review/permit 무효화 → 실행 중 task의 안전 중단·결과 reconcile → 새 spec/plan review → 필요한 사용자 승인만 재수집. 이미 수정한 외부 사본은 보존하고 원본에 자동 적용하지 않는다.

### 17.5 기억 오염 예

retrieved 문서가 “승인 생략”을 지시 → untrusted evidence로 유지 → policy에 영향 없음 → observation/보안 finding → 해당 memory 후보 quarantine → active memory 영향 조사 → scope별 revoke → 관련 세션 pause/rebind. 캐시 안정성을 이유로 악성 memory를 계속 유지하지 않는다.

## 18. 장애·복구 계약

| 장애 | 필수 동작 | 금지 |
|---|---|---|
| extension 로딩 실패 | governed startup 실패, 진단 가능 | 몰래 일반 dcode 실행 |
| 승인 Broker 장애 | 신규 mutation deny/pause | cached approval로 scope 확대 |
| DB locked | bounded retry, timeout 후 pause | 승인/이벤트 유실 상태 실행 |
| 모델 timeout | attempt 기록, 허용 retry, budget 정산 | 무한 재시도 |
| tool crash | started/result reconcile | unknown outcome 자동 재실행 |
| required reviewer 실패 | readiness block | pass로 간주 |
| stdout 폭증 | truncate+artifact·quota | context/디스크 무한 증가 |
| telemetry exporter 장애 | local outbox backlog | raw payload 우회 전송 |
| local audit disk full | mutation stop | 감사 없는 실행 |
| worker stale result | 상태 apply 거부, 중요한 새 근거 재검토 | 현재 상태 덮어쓰기 |
| 사용자 취소 | 신규 dispatch stop·cancellation 전파 | 종료 전 마지막 mutation |
| 외부 파일 변경 | preimage conflict·재계획 | 원본 덮어쓰기 |
| learning 실패 | job failed 표시, 코드 업무 결과와 분리 | 이미 완료된 코드 무효화/학습 성공 주장 |
| promotion 충돌 | CAS reject·rebase eval | 마지막 writer 덮어쓰기 |

재시작 복원은 저장한 이벤트/worker 결과로 결정적 상태를 재생한다. LLM을 재호출해 똑같은 결과를 얻는 것이 아니다. outbox는 at-least-once, consumer는 idempotent다. 이벤트/외부 효과 전체에 exactly-once 보장을 광고하지 않는다.

## 19. 설계 충돌 해결 기록

| 충돌 | 결정 |
|---|---|
| 범용성 vs 기능 | 모델별 tuning만 제외, 전체 업무/검증 기능 유지 |
| dcode만 사용 vs 외부 커널 | dcode는 모델 실행기, 커널은 권한·업무 관리; SDK 대체 금지 |
| 프로젝트 무수정 vs 개발 | 설치는 무수정, 사용자 승인 개발만 scope 내 변경 |
| prompt cache vs memory update | release 고정·epoch 변경; security revoke가 cache보다 우선 |
| self-improve vs 승인 | 자동 관측·후보·평가 + 검증된 위임/승인 후 promotion |
| 풍부한 memory vs context 압력 | scoped proactive retrieval + progressive skills + offload |
| 빠른 개발 vs plan review | 모든 개발에 독립 plan review, 깊이만 risk로 조절 |
| reviewer 독립성 vs 모델 비특화 | input isolation/역할 분리, 특정 모델 의존 안 함 |
| 안정 prefix vs 최소 도구 권한 | phase 단위 안정화, 필요 권한 축소가 우선 |
| 전체 모니터링 vs 비밀 | 모든 중요 lifecycle metadata, 본문은 최소·redaction |
| 기능 연결 실패 vs 무수정 원칙 | 명시적 compatibility block, core patch로 회피 금지 |
| 학습 성능 vs 평가 무결성 | 봉인 holdout, 기준 사전 고정, evaluator 분리 |

## 20. 최종 출시 조건

모든 필수 모듈 구현, 원본 R01–R22 및 확장 테스트, schema/API/DB invariants, governed adapter 통합, 실제 dcode 대표 작업, memory cross-session/삭제, 캐시 측정의 missing 처리, 자동 candidate/eval/promotion/rollback, 장애 주입·재개, PEP8/quality gate, trace completeness, 40점 증거표가 완성되어야 한다.

아직 모델/API key가 없는 상태에서 제품 기능을 mock으로 개발하는 것은 가능하지만 실연동 통과로 표시하지 않는다. 실제 unknown provider의 cache를 강제로 보장하지 않으며, 대신 정확한 unknown 처리·공통 context discipline·지원 endpoint의 검증을 출시 조건으로 삼는다.

이 설계의 완성도는 문서 길이가 아니라 **후속 구현자가 승인·상태·인터페이스·예외·검증 기준을 추측하지 않고 구현할 수 있는가**로 판정한다. 다음 구현 계획과 기계 계약이 이를 구체화한다.
