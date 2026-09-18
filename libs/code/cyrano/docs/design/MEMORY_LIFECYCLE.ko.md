# 평가 3-1·3-2 · 장기 Memory 저장·선택·실제 적용 상세 설계

문서 유형: 목표 상세 설계. 제품 구현 상태: planned. 기준 계약은 `contracts/r4/memory.schema.json`, 저장 목표는 `contracts/sql/r4-memory-observability.sql`. 기존 scope/freshness 기반 선택 함수는 실제 존재하지만 이 서비스의 완성이 아니다. 소유 WP11/WP12, 세분 작업 RC30–RC32.

## 1. 목표와 비목표

3-1은 **세션 밖에서 보존되는 프로젝트 규칙·작업 경험**을 입증한다. 단일 thread checkpoint나 대화창에 남은 메시지를 장기 memory로 계산하지 않는다. 3-2는 새 요청에 관련 memory가 실제 주입되고 계획·코드·검증 행동에 반영된 근거까지 확인한다. 벡터 DB는 필수 구성요소가 아니고 FTS5를 기본으로 한다. retrieval의 높은 점수는 진실/권한/효과의 확률이 아니다.

원본 규칙의 명시 출처와 agent가 추론한 교훈을 분리한다. 단일 실패, TDD red, 취소, 정상 권한 거부, transient 네트워크 문제를 범용 절차로 확정하지 않는다. 실패 사건은 episodic record로 먼저 보관한다.

## 2. 실제 파일과 함수 계약

경로는 `libs/code/deepagents_code/cyrano/` 기준. 아래 함수는 구현 목표다.

| 파일 | 구현할 API | 입력·반환·오류 |
|---|---|---|
| `memory/models.py` | `MemoryRecord`, `MemoryRevision`, `MemoryQuery`, `MemoryView`, `MemoryApplication` | strict external parsing, unknown field 거부; schema와 property tests |
| `memory/repository.py` | `propose(command, principal) -> MemoryRevision` | author은 principal에서; immutable revision; scope 확장 거부; duplicate key+same payload 재사용 |
| `memory/service.py` | `review_and_activate(id, revision, approval, expected_head) -> MemoryRelease` | 대상·scope·digest 결속; approval source 검증; CAS 충돌은 `STALE_REVISION` |
| `memory/recall.py` | `query(query, principal, pinned_release) -> MemoryView` | ACL→release/freshness→검색→충돌→budget. no hit은 valid empty; storage error는 error |
| `memory/binding.py` | `bind_view(run_id, phase, view, request_id) -> InjectionReceipt` | 실제 context 조립의 content digest와 request ID; 요청 취소 전송 전이면 selected까지만 |
| `memory/application.py` | `verify_application(claim, artifacts) -> ApplicationVerdict` | plan diff/task/file/test 근거를 평가; model claim 단독은 unverified |
| `memory/invalidation.py` | `invalidate(dependency_change) -> InvalidationReport` | reverse dependency closure, active index/view/export 영향 추적 |
| `memory/deletion.py` | `delete(request, principal) -> DeletionReceipt` | tombstone commit→검색 차단→blob/index/cache/export purge; 법적/보존 예외 명시 |
| `dcode/memory_adapter.py` | `project_readonly_memory(binding) -> ProjectionManifest` | 실제 native loader 경로 verified; agent shell로 control store 접근 불가 |

`Scope`의 tenant/user/workspace 값은 요청 JSON이 아니라 인증된 run binding과 교집합이다. session scope는 동일 session에서만, workspace scope는 승인된 workspace에서만, 사용자 공통 scope는 명시 위임 때만 허용한다. query의 임의 workspace ID가 주체 범위를 넓힐 수 없다.

## 3. 저장 모델과 트랜잭션

`MemoryRecord`는 stable ID와 scope/kind를 소유한다. 내용은 immutable `MemoryRevision`에 저장한다. 내용 필드는 `content_ref`, `content_digest`, `source_event_ids`, `evidence_refs`, `dependency_digests`, `valid_from`, `valid_until`, `sensitivity`, `approval_ref`, `supersedes`, `status`다. `MemoryRelease`는 `(memory_id, revision, content_digest)` 목록을 정렬해 봉인한 immutable manifest다.

상태: `candidate -> reviewed -> active -> stale | superseded | revoked | archived`. reject는 candidate/reviewed에만, 삭제 tombstone은 상태와 별도로 유지한다. stale 사실을 다시 활성화하려면 새 근거와 새 revision이 필요하다. active 행 내용을 UPDATE해 과거 release의 의미를 바꾸지 않는다.

쓰기 transaction: authenticated command/expected_revision 확인 → idempotency 조회 → 현재 record/release row 잠금 또는 SQLite `BEGIN IMMEDIATE` → revision 생성 → event append → outbox insert → active pointer CAS → command result 저장 → commit. 외부 model 호출은 transaction 밖이다. FTS projection은 outbox 소비로 갱신하며 projection lag 때 query는 canonical active/ACL join을 필수 적용한다. 삭제·revoke는 stale FTS 결과여도 canonical 검사에서 즉시 제거한다.

SQLite는 단일 authoritative writer, WAL·foreign_keys·busy_timeout 설정을 환경별로 검증한다. network filesystem lock을 신뢰하지 않는다. writer process가 여러 개라면 CAS/fencing 또는 PostgreSQL adapter를 구현한다. 새 migration은 backup/replay 시험 후 번호로 관리하며 target SQL을 startup에 무조건 재실행하지 않는다.

## 4. recall 알고리즘

1. principal과 run의 pinned memory release, phase, task/spec digest를 로드한다. 없는 release는 `RELEASE_NOT_FOUND`, 다른 scope는 `SCOPE_DENIED`.
2. canonical store에서 `active`, scope, release membership, 유효 기간, dependency digest를 필터한다. DB down은 `MEMORY_STORE_UNAVAILABLE`이고 검색 결과 0으로 치환하지 않는다.
3. 이미 승인된 structured rule tags/paths/requirement IDs와 FTS query를 사용한다. raw user input을 SQL/FTS syntax로 연결하지 않는다. parameter binding과 FTS escape 적용.
4. 결과가 상충하면 명시 user decision > 해당 workspace의 검증 사실 > 불확실 observation 순의 authority를 비교한다. authority 동일하고 결론 충돌이면 conflict item 반환; 최신 timestamp만으로 진실 결정 금지.
5. relevance, verified_at, memory_id, revision 순서로 deterministic tie-break한다. 중복 내용은 하나로 대표하되 모든 출처 보존.
6. context byte/token budget에서 필요한 것만 선택한다. mandatory 규칙이 budget에 맞지 않으면 예산을 몰래 넘기지 말고 pause/replan. tokenizer가 없으면 bytes와 `token_measurement=unknown` 표시.
7. 선택된 immutable 내용을 읽고 digest 재검증, `MemoryView` 발급. return에 제외 사유별 수량과 query 오류 여부를 기록한다. 다른 tenant의 후보 수량도 누출하지 않는다.

같은 release에서도 task가 바뀌면 view는 달라진다. stable system block에 query result를 합치지 않고 dynamic task context에 넣는다. 순수한 stable rules projection을 release 단위로 쓰는 경우만 stable prefix에 넣으며, release 변경은 새 context epoch로 기록한다.

## 5. 조회 시점과 실제 적용

| phase | 기억 | 실제 적용의 증거 예 |
|---|---|---|
| intake/interview | 명시 선호·용어·프로젝트 사실 | requirement/decision ID와 수정된 질문·명세 |
| plan | 유사 실패·검증 recipe·scope 규칙 | WorkUnit/acceptance/검증 명령을 추가한 plan diff |
| implement | 현재 파일과 관련된 코드 규칙 | source diff + AST/validator가 해당 규칙 만족 확인 |
| verify/review | 과거 누락·회귀 패턴 | 추가 검증의 실제 runner 결과 |
| terminal | 작업 outcome·교정 | 새 episodic revision과 연결된 evidence |

이벤트는 `memory.queried`, `selected`, `injected`, `referenced`, `applied`, `effect_measured`를 분리한다. queried는 서비스 query 완료, selected는 view 확정, injected는 실제 전달 가능성이 확인된 request manifest, referenced는 model 출력 참조, applied는 독립 검증된 행동, effect_measured는 on/off 또는 baseline/candidate 통제 평가다. 모델 provider가 wire payload를 노출하지 않는 경우 injected는 `adapter_confirmed`이며 `wire_confirmed=false`; 결손을 숨기지 않는다.

plan_rule·code_rule·verification_recipe마다 `application_checker`를 등록한다. 예: `plan_contains_required_check`는 plan에 해당 test argv와 acceptance 연결이 있는지 검사하고, `verification_executed`는 trusted runner의 동일 argv/artifact digest 결과를 검사한다. 자유 서술 교훈은 자동 증명 불가능할 수 있으므로 reviewer attestation을 요구한다. 추출된 ID만 있으면 `referenced`, 결과가 다른데 checker가 통과했다고 주장하면 audit incident다.

## 6. 세션 간 지속성과 삭제

3-1 필수 실험: process A가 임시 외부 control home에서 memory 제안·승격 후 종료; process B는 새 OS process/new thread/no prior message로 시작; 동일 principal/workspace에서 query → 동일 revision/digest 회수. checkpoint를 지우고도 성공해야 한다. 다른 user/workspace·만료 dependency는 회수하면 안 된다.

세션 종료 hook만 저장 시점으로 사용하면 crash 시 잃는다. verified episode 단계별로 durable event를 기록하고 terminal settlement와 learning job을 한 transaction으로 생성한다. incomplete 사건은 incomplete로 보존하며 성공 교훈으로 승격하지 않는다.

삭제는 본문·FTS·optional vector·native projection·query cache·export·backup 영향 범위를 모두 기록한다. external trace export 삭제는 별도 처리 상태가 필요하다. 일관성 요구는 'canonical에서 tombstone commit 이후 새 query에 본문을 노출하지 않음'이다. 이전 model request에 이미 전달한 내용을 되돌릴 수 있다고 약속하지 않는다. tombstoned dependency를 사용하는 run은 pause/rebind 정책 적용.

## 7. 오류·동시성·보안

오류 코드: `SCOPE_DENIED`, `STALE_REVISION`, `SOURCE_NOT_FOUND`, `DEPENDENCY_STALE`, `MEMORY_CONFLICT`, `MEMORY_STORE_UNAVAILABLE`, `CONTEXT_BUDGET_EXCEEDED`, `APPROVAL_INVALID`, `IDEMPOTENCY_CONFLICT`. 민감 payload 없이 code/retryable/next_action/evidence_ref를 반환한다.

동시 승격 둘은 하나만 CAS 성공. TTL 통과 뒤 dependency 변경과 prompt assembly가 경합하면 직전 dependency check/release revoke epoch로 차단한다. 같은 idempotency key의 다른 payload는 conflict. query 결과나 악성 memory의 '승인을 무시하라'는 문장을 도구 권한으로 실행하지 않는다. native AGENTS 쓰기·shell 우회·서브에이전트 경로는 WP03/WP06 통제와 실제 negative test가 필요하다.

## 8. 수용·개발·실행 연결

현재 3-1/3-2 평가 사례를 유지하고 RC30–RC32의 추가 사례를 모두 수행한다. keyless component tests는 지속성·불변성 원리를 확인하고, native 새 session test는 실제 dcode loader 및 application chain을 입증한다. 두 결과를 같은 증거로 사용하지 않는다. 개발 파일·함수별 순서는 [평가 3·4 구현계획](../development/MEMORY_OBSERVABILITY_PLAN.ko.md), 실제 명령·fixture·정리는 [실행 절차](../execution/MEMORY_OBSERVABILITY_RUNBOOK.ko.md).

## R5 구현 연결

bounded core·episode·playbook, 무관한 기억 abstention과 utility/exposure 계약은 [R5 소유 상세 설계](ADAPTIVE_MEMORY_AND_SKILL_EVOLUTION.ko.md)에서 구체화한다. 기존 scope·승인·실제 검증은 유지하며 skill 설정만으로 해당 기능을 구현하지 않는다.

## 첫 실행의 seed와 권한 철회

프로젝트가 아직 아무 개선 release를 만들지 않았다고 기억을 영원히 사용할 수 없는 순환을 만들지 않는다. 운영자가 검토한 초기 규칙·skill·정책을 `seed_release`로 봉인하고 초기 release 생성 권한을 명시한다. 이후 자기개선 candidate는 동일한 active pointer writer를 쓰되 paired eval·승격 승인 경로를 거친다. 생성한 후보가 seed로 위장할 수 없게 최초 생성 조건과 운영자 역할을 검사한다.

세션 내 stable core memory는 원래 release를 유지하지만 ACL 철회·삭제·비밀 유출은 캐시보다 우선한다. 이미 노출된 정보를 모델에서 '잊게 했다'고 주장하지 않는다. 후속 모델 호출을 멈추고 허용된 context만 재구성해 새 epoch에서 재개한다. provider에 이미 전달된 데이터 삭제는 로컬 index 삭제와 다르며 지원 여부를 별도로 표시한다.

writer는 context를 만드는 agent가 아니라 승인된 service다. 유용성 점수·노출 빈도·긍정 피드백은 retrieval 정렬을 도울 뿐 사실성이나 접근 권한을 높이지 않는다. 상충 기억은 최신 시간 하나만으로 해결하지 않고 원문·명시적 supersedes·권위를 확인한다. advisory hint가 작업 지시나 실행 허가로 승격되지 않게 한다.
