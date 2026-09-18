# 첨부 Universal Harness 상세 분석·반영 결과

기준: 제공된 ZIP의 실제 파일 내용. upstream main을 다시 실행하거나 현재 설치 dcode를 확인한 결과가 아니다. source110개는 원문 보존하며 code/config/SQL을 실행 대상으로 등록하지 않았다. 기준 ZIP SHA256은 `references/universal-harness-import.json`에 있다.

## 1. 구조와 의미 분석

첨부는 여섯 소유 문서의 0–32장, 기계 계약15개, 상태·이벤트·40점 catalog, 정책/SQL/역할/fixture, 원본 interview14개, 통합 MD/HTML과 검증 보고서로 구성된다. 통합본문은 원본들을 다시 묶은 projection이므로 중복 장을 새로운 기능으로 세지 않았다. JSON Schema는 shape를, 본문은 authority·동시성·실행 책임을 기술하므로 둘을 함께 분석했다.

기존 프로젝트는 모델 비특화, non-invasive dcode, A/B 개선과 실제 평가, package별 소유권, progressive skills를 더 세분화한다. 첨부의 핵심 추가 가치는 **세션 전체 전이, 명세/계획/실행/원본반영 승인 분리, 정확한 파일 권한, 완료 evidence, full-process monitoring, Python 기준 및 evidence rubric**을 연결하는 데 있다.

단순 덮어쓰기는 계획 ID·role 이름·digest 서명·기본 실행값을 바꾸는 문제를 만든다. 따라서 입력은 보존하고 기존 구조를 기준으로 변환 계약과 구현 의무를 명시했다. 다음은 원본 전체 장의 담당 위치다.

## 2. 0–32장 추적표

| 원본 장 | 현재 소유 설계 | 구현 WP |
|---|---|---|
| 0 · 이 문서의 계약 | `docs/design/architecture/2026-09-16-system-design.ko.md` | WP01 |
| 1 · 확인된 dcode 범위와 구현 경계 | `docs/design/architecture/2026-09-16-runtime-security.ko.md` | WP00 |
| 2 · 전체 아키텍처 | `docs/design/architecture/2026-09-16-system-design.ko.md` | WP03 |
| 3 · 외부 파일·환경 구조 | `docs/design/architecture/2026-09-16-runtime-security.ko.md` | WP22 |
| 4 · 핵심 도메인과 단일 진실 원천 | `docs/design/architecture/2026-09-16-data-api.ko.md` | WP01 |
| 5 · 상태기계: 인터뷰에서 완료·학습까지 | `docs/design/features/2026-09-16-interview-workflow.ko.md` | WP07 |
| 6 · Decision Interview의 고도화 통합 | `docs/design/features/2026-09-16-interview-workflow.ko.md` | WP08 |
| 7 · 개발 시작 전 계획 구체화·리뷰 Workflow | `docs/design/features/2026-09-16-plan-memory-execution.ko.md` | WP09 |
| 8 · 작업 기반 Harness Profiles와 서브에이전트 | `docs/design/architecture/2026-09-16-cache-context.ko.md` | WP05 |
| 9 · 승인과 실행 권한 | `docs/design/architecture/2026-09-16-runtime-security.ko.md` | WP03 |
| 10 · Middleware 설계 | `docs/design/architecture/2026-09-16-runtime-security.ko.md` | WP06 |
| 11 · Prompt Caching과 Context Engineering | `docs/design/architecture/2026-09-16-cache-context.ko.md` | WP05 |
| 12 · Memory: 적극적 사용과 통제 | `docs/design/features/2026-09-16-plan-memory-execution.ko.md` | WP11 |
| 13 · Self-Improving: 강력한 기능을 안전하게 운영 | `docs/design/features/2026-09-16-path-b-improvement.ko.md` | WP16 |
| 14 · 전체 개발 작업 모니터링 | `docs/design/testing/2026-09-16-evaluation-observability.ko.md` | WP13 |
| 15 · Python 개발 품질: PEP8을 실행 가능한 게이트로 | `docs/development/MASTER_DEVELOPMENT_PLAN.ko.md` | WP22 |
| 16 · 네 추가 요구사항의 40점 증거표 | `docs/design/testing/2026-09-16-evaluation-observability.ko.md` | WP22 |
| 17 · 운영 Workflow와 사용자 경험 | `docs/execution/MASTER_EXECUTION_PLAN.ko.md` | WP22 |
| 18 · 장애·복구 계약 | `docs/design/architecture/2026-09-16-runtime-security.ko.md` | WP22 |
| 19 · 설계 충돌 해결 기록 | `docs/design/architecture/2026-09-16-universal-harness-integration.ko.md` | WP01 |
| 20 · 최종 출시 조건 | `docs/execution/MASTER_EXECUTION_PLAN.ko.md` | WP23 |
| 21 · 구현 구조와 의존 방향 | `docs/design/architecture/2026-09-16-system-design.ko.md` | WP01 |
| 22 · 핵심 함수 계약 | `docs/design/architecture/2026-09-16-data-api.ko.md` | WP01 |
| 23 · 외부 API | `docs/design/architecture/2026-09-16-data-api.ko.md` | WP03 |
| 24 · 저장소·트랜잭션·canonicalization | `docs/design/architecture/2026-09-16-data-api.ko.md` | WP02 |
| 25 · 개발 작업 패키지 | `docs/development/MASTER_DEVELOPMENT_PLAN.ko.md` | WP22 |
| 26 · 테스트 계층과 분리 | `docs/design/testing/2026-09-16-evaluation-observability.ko.md` | WP20 |
| 27 · 릴리스 차단 체크리스트 | `docs/execution/MASTER_EXECUTION_PLAN.ko.md` | WP22 |
| 28 · 스키마 적용 규칙 | `docs/design/architecture/2026-09-16-data-api.ko.md` | WP01 |
| 29 · dcode 어댑터와 기능 연결 | `docs/design/architecture/2026-09-16-runtime-security.ko.md` | WP06 |
| 30 · 결정적 알고리즘의 상세 기준 | `docs/design/architecture/2026-09-16-universal-harness-integration.ko.md` | WP01 |
| 31 · 회귀 테스트 명세와 실행 증거 | `docs/design/testing/2026-09-16-evaluation-observability.ko.md` | WP22 |
| 32 · 구현 산출물과 납품 기준 | `docs/execution/MASTER_EXECUTION_PLAN.ko.md` | WP23 |

원본33개 장의 기계 매핑은 `contracts/integration/section-map.json`이다. 110개 모든 파일의 archive/reference/generated/example/test-data 구분과 사용 방식은 `source-file-dispositions.json`이다. generated HTML과 FULL_DESIGN을 current-source로 중복 편집하지 않는다.

## 3. 15개 계약의 변경 결과

| 첨부 schema | 현 타입 | 변환 원칙 |
|---|---|---|
| `work-plan.schema.json` | `GovernedWorkPlan` / `GovernedWorkUnit` | 새 parser·semantic binding 필요; 기존 서명 권한 자동 전환 금지 |
| `approval-receipt-v2.schema.json` | `TrustedApprovalReceipt` | 새 parser·semantic binding 필요; 기존 서명 권한 자동 전환 금지 |
| `execution-permit.schema.json` | `ToolExecutionPermit` | 새 parser·semantic binding 필요; 기존 서명 권한 자동 전환 금지 |
| `verification-result.schema.json` | `RunnerVerification` | 새 parser·semantic binding 필요; 기존 서명 권한 자동 전환 금지 |
| `change-manifest.schema.json` | `ExecutionChangeManifest` | 새 parser·semantic binding 필요; 기존 서명 권한 자동 전환 금지 |
| `run-report.schema.json` | `RunCompletionReport` | 새 parser·semantic binding 필요; 기존 서명 권한 자동 전환 금지 |
| `memory-record.schema.json` | `MemoryAccessBinding` | 새 parser·semantic binding 필요; 기존 서명 권한 자동 전환 금지 |
| `event-envelope.schema.json` | `GovernedEvent` | 새 parser·semantic binding 필요; 기존 서명 권한 자동 전환 금지 |
| `adapter-report.schema.json` | `CompatibilityProbe` | 새 parser·semantic binding 필요; 기존 서명 권한 자동 전환 금지 |
| `api-dtos.schema.json` | `SessionQuery` / `NextActionRequest` / `ApprovalRequest` / `SessionLifecycleRequest` / `TrustedUserEvent` | 새 parser·semantic binding 필요; 기존 서명 권한 자동 전환 금지 |
| `context-manifest.schema.json` | `ContextManifest` | 새 parser·semantic binding 필요; 기존 서명 권한 자동 전환 금지 |
| `review-result.schema.json` | `WorkerOutcome` | 새 parser·semantic binding 필요; 기존 서명 권한 자동 전환 금지 |
| `worker-result-v2.schema.json` | `WorkerOutcome` | 새 parser·semantic binding 필요; 기존 서명 권한 자동 전환 금지 |
| `learning-candidate.schema.json` | `CandidateProposal` / `LearningWorkPlan` / `ImpactAssessment` | 새 parser·semantic binding 필요; 기존 서명 권한 자동 전환 금지 |
| `evaluation-report.schema.json` | `EvaluationReport` / `ExperimentPlan` | 새 parser·semantic binding 필요; 기존 서명 권한 자동 전환 금지 |

원본 adapter-report는 전체 CompatibilityReport였고 현 CompatibilityProbe는 개별 검사 evidence다. 상위 집계는 단계별 필수 probe 목록과 scope/runtime binding을 검증해야 한다. 원본 review-result는 WorkerOutcome 컨테이너만으로 전부 표현된다고 단정하지 않는다. subject/역할/mandatory finding/해결상태와 독립 실행은 각 review payload와 service 계약으로 재검증한다. ContextManifest는 기존 fingerprint·native/wire 관측 계약을 유지하며 proactive view metadata를 추가 binding으로 연결한다.

## 4. 의미 충돌과 결정

| ID/주제 | 차이 | 채택한 결과 | 담당 |
|---|---|---|---|
| INT-01 · 패키지 구조 | 첨부는 단일 cyrano_harness 패키지, 현재는 dcode namespace 아래 13개 기능 모듈이다. | 기존 deepagents_code/cyrano 모듈과 plugins/cyrano 설정을 유지하고 담당 docs/design에서 설계를 관리한다. 원본의 클래스 책임만 기존 소유 package로 이동하며 두 개의 agent loop를 만들지 않는다. | WP01, WP04, WP06 |
| INT-02 · 권위와 구현 상태 | 첨부의 문서·schema 존재와 실행 보장을 혼동할 수 있다. | references는 보존 자료다. 현재 코드, 목표 계약, 실제 실행 증거를 구분한다. 새 v2는 검증 가능한 명세이며 제품 서비스 구현 완료가 아니다. | WP00, WP22 |
| INT-03 · 계약 버전 | PlanBundle·Permit·EventEnvelope@1은 강화된 승인·변경·납품 계약을 다 담지 못한다. | v1 원문을 동결하고 governed 경로는 v2 타입을 선택한다. 명시적인 parser/semantic validation 없이 필드명 변경·default 주입·권한 승격을 하지 않는다. | WP01, WP02 |
| INT-04 · 서명 호환 | 원본 HMAC v1, 첨부 Ed25519 v2, 기존 CYRANO digest 규칙이 다르다. | 구조가 비슷해도 서명 subject는 다르다. 기존 receipt는 기록으로만 보존하고 현 계약의 정확한 화면·subject·scope를 다시 승인받는다. 새 권한으로 자동 전환하지 않는다. | WP01, WP03 |
| INT-05 · 두 상태기계 | 기존 transitions.py는 개선 후보 상태, 첨부 29개 상태는 개발 세션 상태다. | 후보 상태를 교체하지 않는다. session_state/session_guards를 별도 구현하고 세션 terminal event가 learning outbox를 연결한다. 완료한 코드와 실패한 학습은 별도 결과다. | WP07, WP16 |
| INT-06 · 계획과 납품 | 기존 WorkUnit의 write_paths만으로 생성·삭제·원본 적용을 구분할 수 없다. | GovernedWorkUnit에 create/delete/only_write·검증 recipe·preimage를 보강한다. GovernedWorkPlan.delivery_mode는 patch_only/apply_to_source이며 approval subject에 들어간다. | WP09, WP10 |
| INT-07 · only_write | 파일 시스템 mount로 쓰기 전용을 선언해도 읽기와 별칭 접근이 가능할 수 있다. | only_write는 broker가 소유한 쓰기 전용 sink다. agent/test에 읽을 수 있는 fd/mount/별칭을 주지 않는다. 제공 환경이 이를 강제하지 못하면 해당 permission은 unsupported다. | WP03 |
| INT-08 · 리뷰 강도 | 첨부 prose의 위험도별 blind 검토와 config의 필수 reviewer가 완전히 같지 않다. | 모든 spec은 critic+blind, 모든 plan은 plan-reviewer, 모든 최종 산출물은 code-reviewer가 검토한다. high/critical은 security-reviewer를 추가한다. 동일 모델 사용은 독립 통계 표본을 뜻하지 않는다. | WP05, WP08, WP09 |
| INT-09 · 품질 정책 | 첨부는79자/설명72자, 기존 pyproject는88자다. | 이 프로젝트 목표 정책을79/72로 통일한다. 기존 코드 위반은 baseline audit에 남기고 WP00에서 도구 고정, 각 WP와 WP22에서 수정한다. 설정 변경만으로 전 코드 준수를 주장하지 않는다. 고객 프로젝트 규약은 별도 승인 대상으로 유지한다. | WP00, WP22 |
| INT-10 · 학습 기본값 | 첨부 예시에는 learning.enabled=true, 기존 준비 프로젝트는false다. | 실제 실행·학습·자동 승격·canary·원격 trace 모두 기본 비활성을 유지한다. 배포에 대한 동의가 외부 호출이나 자동 변경에 대한 포괄적 동의가 아니다. | WP16, WP23 |
| INT-11 · 보존 정책 | 첨부 본문과 예시 config의 payload/audit 보존 수치가 다르다. | 현재 제안은 metadata30일·redacted body7일·승인/정책 최소 metadata180일·평가 요약365일이다. raw secret은 보존하지 않는다. 숫자는 운영자가 승인할 기본 가설이지 법적 보존 결론이 아니다. | WP11, WP13, WP22 |
| INT-12 · 캐시와 기억 | memory를 고정 prefix에 매번 재작성하면 적극 recall과 cache가 충돌한다. | memory release는 epoch에 고정하되 query view는 task별 동적 tail이다. 선택한 안정 기억만 epoch 시작에 동결할 수 있다. 삭제·보안 철회는 cache 이점보다 우선한다. | WP05, WP11 |
| INT-13 · 로그와 비밀 | model-visible 재현성과 원문 무기한 보관은 같은 요구가 아니다. | 모델에 도달한 구성은 manifest로 식별하고 허가된 본문만 보관한다. 원문이 삭제되거나 처음부터 보존되지 않았다면 exact replay unavailable로 보고한다. 임의로 요약을 원문인 것처럼 대체하지 않는다. | WP13, WP14 |
| INT-14 · 전체 모니터링 | 모델/도구 callback만으로 native summarization·retry·child까지 관측했다고 할 수 없다. | 65개 typed event와 실제 경로 coverage matrix를 따로 둔다. 필수 control/audit 누락은 차단한다. provider가 제공하지 않는 cache metric은 지원 불가/unknown으로 표시하며 필수 보안 누락과 구분한다. | WP06, WP13 |
| INT-15 · 이벤트 revision | 매 token/telemetry가 control revision을 올리면 실행 중 계약이 계속 무효화된다. | event_seq는 저장 순서, producer_seq는 생산자 순서, control_revision은 업무 의미 변경에만 증가한다. subject가 바뀌지 않은 일반 관측은 새 권한 발급 사유가 아니다. | WP02, WP13 |
| INT-16 · 비용 | retry·부모 span 합산과 timeout 즉시 환불은 예산을 잘못 계산한다. | 실제 billable leaf attempt별 기록을 합산하고 parent는 별도 합계가 아니다. 가격/usage 불명은 null이며 미결 비용 예약을 outstanding liability로 유지한다. provider 지원 없는 exactly-once를 보장하지 않는다. | WP09, WP13, WP20 |
| INT-17 · 리플레이와 경로 B | 첨부 generic self-improvement가 기존 DREAM의 조건을 생략할 수 있다. | A는 입력 서명·부모·추가 dependency·모델/endpoint가 같은 지원 전이만 재사용한다. B의 기억/skill/질문/context/recipe/code 변경은 실제 paired 평가가 필요하며 old evaluation 재사용을 거부한다. | WP14–WP20 |
| INT-18 · 테스트 중복 | 원본 R01–R22가 세 개 자료에 존재한다. | 시나리오 내용은 보존하되 canonical INT-R01–22를 재사용한다. source124개 중 나머지102개는 UH- prefix, 새로운 통합 사례24개는 INTEG- prefix로 별도 관리한다. fixture 수가 독립 corpus 수가 되지 않는다. | WP07, WP20, WP22 |
| INT-19 · 개발 작업 번호 | 원본 WP00–21과 기존 WP00–23의 의미가 다르다. | 기존24개 작업 ID를 유지한다. source_work_packages에 universal:WPxx로 이름공간을 넣고 mapping JSON으로 연결한다. 번호순이 아니라 DAG가 실행 순서를 정한다. | 전체 WP |
| INT-20 · 초기 구축 승인 | 전체 governed 검증을 WP00 선행으로 요구하면 아직 만들지 않은 WP03/06에 의존한다. | WP00은 bootstrap 검증만 담당한다. 초기 개발은 외부 사람 리뷰와 제한된 사본으로 승인한다. 실제 adapter/governed/operational 검증은 담당 WP 완료 후 수행하며 자동 advisory fallback은 없다. | WP00, WP03, WP06, WP22 |
| INT-21 · API와 tool | 첨부 resource endpoint와 기존 generic command ingress가 다르다. | 기존 명령형 control ingress를 유지하고 payload_schema_ref로 타입을 고정한다. 필요한 조회/제안 tool만 추가한다. 모델에게 approve/grant/mark_ready/set_state 권한을 주지 않는다. | WP01, WP06, WP09 |
| INT-22 · SQL 병합 | 두 SQL 파일을 순서대로 executescript하면 기존 데이터와 의미를 검증하지 못한다. | 현재 Store schema, 기존 target-schema, 신규 governance extension을 세 단계로 구분한다. versioned migration·backup·dry-run·row/digest/ACL 검사를 WP02에서 구현한다. 첨부 DDL을 자동 적용하지 않는다. | WP02, WP19 |
| INT-23 · 원본 반영 실패 | 멀티파일 적용 중 일부만 바뀌거나 취소된 상태를 rollback 완료로 오인할 수 있다. | prepare/apply/verify journal을 기록한다. 부분 결과와 unknown effect를 먼저 reconcile하고 현재 preimage에 대한 별도 복구 승인을 받는다. harness pointer rollback은 사용자 코드 rollback이 아니다. | WP10, WP21, WP22 |
| INT-24 · 40점 증거표 | 문서와 기반 테스트가 있다고 항목 점수를 미리 줄 위험이 있다. | 사용자 15개 criterion은 제품 실행 증거로만 채점한다. 현재 scorecard는 not_evaluated/0이고 hard gate는 not_tested다. 점수로 승인 우회·비밀 유출·거짓 완료를 상쇄하지 않는다. | WP22, WP23 |

## 5. 구현 준비 변경

계약은 `v1`을 유지하고 `v2` governed 타입과65개 event payload를 추가했다. phase/risk/reviewer/권한/예산은 typed resolved profile로 계산하도록 정책을 배치했다. 현재 role14개 중 security-reviewer는 다른 역할과 동일한 proposal_only다. tool15개는 조회·제안·실행요청 port이며 approval 발급을 모델에 노출하지 않는다.

원본124개 수용 사례 중22개 interview는 기존 INT-R01–22와 내용 동일성을 검사해 재사용한다. 나머지102개는 UH-*로 추가하며24개 새로운 통합 반례를 별도 INTEG-*로 추가했다. 이 의무들은 현재 단일 catalog의 **제품 수용 명세**에 포함되어 있다. 이번 package 검사나 synthetic schema fixture 통과는 해당 제품 시나리오의 실제 실행 완료가 아니다.

24개 기존 WP 번호와 dependency를 보존하고 각 WP에3개씩 총72개의 구체 통합 작업을 추가했다. 더 넓은 의무가 생겨도 모든 WP는 planned 상태다. source의 WP 번호는 universal:WPxx로 구분한다. guard 구현·migration·model/provider 측정·sandbox·40점 evidence는 여전히 해당 제품 작업의 완료 증거가 필요하다.

## 6. 분석에서 확인한 한계

79/72 설정의 채택은 기존 전체 Python 코드를 자동으로 준수하게 만들지 않는다. style audit는 위반 위치를 드러내는 검사이며 Black/Ruff/mypy의 대체물이 아니다. 실제 plugin load/native paths/격리/paired evaluation/rollout은 수행하지 않았다. 과거 검증 보고서는 history/reference로 보존하며 이번 실제 검사 결과와 합산하지 않는다.

## 7. 실행 진입점

`START_HERE.ko.md` → `IMPLEMENTATION_REQUEST.ko.md` → `docs/execution/INTEGRATED_WORK_DETAILS.ko.md` → `.agents/work/plan.json`의 준비된 WP 순서다. 구현 에이전트가 읽을 문서 slice와 실행 증거는 작업별 파일에 지정한다. 전체통합문서를 매 호출 prompt에 넣지 않는다.
