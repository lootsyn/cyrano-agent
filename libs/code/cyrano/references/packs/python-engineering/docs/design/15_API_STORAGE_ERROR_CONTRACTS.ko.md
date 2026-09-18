# 15. 구현 API, 저장 DDL, 오류 계약

## 15.1 공개 API와 권한 주입

도메인 서비스는 모델에게 노출된 함수와 별도로 AuthContext를 받는다.
AuthContext는 인증된 controller가 주입하며 모델 입력 schema에 포함하지 않는다.
`workspace_id`, `attempt_id`, `session_id`, `principal_id`, `capabilities`, `request_id`를 가진다.

| Model tool | 모델이 전달 가능한 필드 | controller가 조회할 값 | 반환 |
|---|---|---|---|
| quality_inspect | 없음 | 현재 workspace/attempt/policy | effective policy summary, capabilities, blockers |
| quality_verify | 없음 | approved plan/snapshot recipe/check IDs | report_id, verdict, check summary, evidence refs |
| quality_status | 없음 | 현재 attempt의 최신 registered report/state | state, report_id, fresh 여부, 다음 허가 동작 |
| request_completion | report_id, expected_revision | 계획/리뷰/permit/현재 revision | accepted bool, actual work status, rejection codes |

`quality_verify` 모델 인자에서 policy, check list, baseline flag, arbitrary argv, output path,
source roots를 받지 않는다. 사용자가 CLI에서 다른 저장소를 요청해도 AuthContext/permit을 발급하는
상위 경계를 먼저 통과해야 한다. CLI `--workspace` 문자열만으로 다른 workspace에 접근할 수 없다.

모델 tool 함수들의 모든 인자/반환 타입을 명시하고 docstring을 작성한다. `@tool` 또는 extension의
schema 추론이 성공하는지 import 단위 테스트와 실제 tool 호출 테스트로 확인한다.
한 모델에 종속적인 schema shortcut을 넣지 않는다.

## 15.2 내부 Protocol의 필수 메서드

아래 이름·입출력 관계를 유지하되 공용 타입은 `udh_contracts`가 소유한다.

```text
PolicyResolver.resolve(workspace, approved_release) -> ResolvedQualityPolicy
InventoryService.discover(snapshot, policy) -> PythonInventory
SnapshotService.seal(attempt, expected_revision) -> SourceSnapshot
PolicyGuard.compare(base_snapshot, candidate_snapshot, permit) -> GuardResult
CommandFactory.build(check_spec, snapshot, toolchain) -> ToolInvocation
ProcessRunner.run(invocation, cancellation) -> ToolReceipt
ToolAdapter.parse(receipt, config) -> NormalizedCheckResult
BaselineService.compare(base_report, candidate_report, permit) -> BaselineComparison
EvidenceStore.register(authenticated_runner, draft_report) -> RegisteredReport
QualityService.verify(auth_context) -> RegisteredReport
ReviewStore.get_approved(subject_digest, review_kind) -> ReviewReceipt | None
CompletionService.request(auth_context, report_id, expected_revision) -> CompletionResult
RepairPolicy.decide(failure_summary, attempt_budget) -> RepairDecision
```

`ResolvedQualityPolicy`: policy wire + original_config_digest + rendered_config_digest +
policy_release_digest + toolchain_digest + mandatory-check manifest digest.
`PythonInventory`: Python file entries, analyzed roots, exclusions, unsupported entries,
changed file set, inventory_digest. 누락을 빈 배열 성공으로 반환하지 않는다.
`ToolInvocation`: tool kind/version, executable identity, immutable argv tuple, cwd snapshot ID,
env_recipe_digest, timeout_ms, output_limit_bytes, check_id. 사용자 문자열 shell은 없다.
`ToolReceipt`: invocation_digest, started/finished UTC, duration_ms, executed, exit_code,
termination_reason, stdout/stderr refs+digests, runner identity, sandbox identity.
`NormalizedCheckResult`: CheckResult wire + structured Diagnostic[] + coverage manifest digest.
`Diagnostic`: tool/rule/severity/path/start/end/message/fingerprint/raw diagnostic reference.
`RegisteredReport`: report wire + report_digest + authenticated channel receipt + storage revision.
`CompletionResult`: accepted, work_status, report_id, source_snapshot_digest,
rejection_codes[], resulting_revision. accepted=false이면 resulting_revision은 읽은 현재 revision이다.
`RepairDecision`: action=repair|retry_environment|replan|stop, reason_code, remaining_budget,
allowed_scope_digest. agent가 remaining_budget을 늘릴 수 없다.

정상적인 코드 위반은 Python 예외를 던지는 service crash가 아니라 result 상태로 반환한다.
잘못된 내부 계약/스토리지 실패는 typed domain exception으로 변환하고 외부에는 안전한 오류 코드와
trace ID만 노출한다. 사용자 취소는 별도 cancellation path다.

## 15.3 저장 DDL 초안

기존 event store migration 규약으로 아래 table을 추가한다. 외래키가 가리킬 기존 테이블 이름은
실제 UDH 저장소에서 확인해야 하므로 존재를 확인하지 않은 이름으로 FK를 만들지 않는다.
Workspace/Attempt 존재·소유·revision 검증은 기존 kernel transaction 안에서 수행한다.

```sql
CREATE TABLE quality_requests (
    request_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL,
    payload_digest TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('RUNNING', 'FINISHED', 'ERROR')),
    report_id TEXT,
    lease_owner TEXT,
    lease_expires_at TEXT,
    created_at TEXT NOT NULL,
    CHECK (state != 'FINISHED' OR report_id IS NOT NULL)
);

CREATE TABLE quality_reports (
    report_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL,
    snapshot_digest TEXT NOT NULL,
    policy_digest TEXT NOT NULL,
    toolchain_digest TEXT NOT NULL,
    suite_digest TEXT NOT NULL,
    report_digest TEXT NOT NULL UNIQUE,
    runner_receipt_id TEXT NOT NULL UNIQUE,
    verdict TEXT NOT NULL CHECK (
        verdict IN (
            'PASS', 'PASS_WITH_BASELINE', 'FAIL',
            'ERROR', 'BLOCKED', 'STALE'
        )
    ),
    report_blob_ref TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX quality_reports_attempt_idx
ON quality_reports(attempt_id, created_at);
```

위 두 table은 별도 승인/인증 DB가 아니다. report blob 등록과 기존 event/outbox/상태 전이를
같은 신뢰 경계에서 묶는 인덱스다. 모델이 직접 INSERT할 권한은 없다. SQLite CHECK나 hash 일치만으로
발신자 인증이 되지 않는다. request RUNNING row crash 복구는 lease를 확인한 뒤 ERROR로 전환하고,
이미 등록된 report가 있다면 request/report 연결을 같은 transaction에서 복구한다.

## 15.4 오류 코드

| 범주 | 코드 | 처리 |
|---|---|---|
| 설정/환경 | POLICY_CONFIG_MISMATCH, UNSUPPORTED_CAPABILITY, UNSUPPORTED_ISOLATION_BACKEND, ENV_SETUP_FAILED, STALE_LOCK | 실행 전 차단 또는 ERROR |
| 경로/입력 | PATH_POLICY_VIOLATION, UNSUPPORTED_PATH_ENCODING, EMPTY_SCOPE, MISSING_REQUIRED_RESOURCE | 봉인/실행 차단 |
| 도구 | TOOL_PROTOCOL_ERROR, TOOL_INTERNAL_ERROR, TOOL_TIMEOUT, OUTPUT_LIMIT, RUNNER_LOST | ERROR, PASS 발급 없음 |
| 코드 | FORMAT_VIOLATION, LINT_VIOLATION, TYPE_VIOLATION, TEST_FAILURE | 정해진 예산 내 복구 |
| 테스트 | NO_TESTS, REQUIRED_TEST_SKIPPED, TEST_COLLECTION_ERROR, EXISTING_TEST_FAILURE | 검사 의무 미충족 |
| 정책 | UNAUTHORIZED_POLICY_CHANGE, UNAPPROVED_SUPPRESSION, EXCEPTION_EXPIRED, TEST_SCOPE_WEAKENED | 일반 구현 범위 밖, 별도 승인 |
| baseline | STALE_BASELINE, UNSUPPORTED_BASELINE, NEW_DIAGNOSTIC, BASELINE_NOT_AUTHORIZED | 자동 면제 금지 |
| 완료 | UNTRUSTED_REPORT, IDENTITY_MISMATCH, STALE_SNAPSHOT, STALE_REVIEW, REQUIRED_CHECK_MISSING, REVIEW_BLOCKED, REVISION_CONFLICT | 완료 요청 거부 |
| 예산/취소 | REPAIR_BUDGET_EXHAUSTED, NO_PROGRESS, USER_CANCELLED | BLOCKED 또는 CANCELLED |

외부 오류 message는 설명용이며 자동 분기에는 error code를 사용한다. unknown error code는
ERROR_UNKNOWN으로 보존하고 실패로 처리한다. 파서가 모르는 도구 버전을 조용히 허용하지 않는다.

## 15.5 동시성 및 순서

같은 Attempt에는 동시에 하나의 final verify lease만 허용한다. 서로 다른 Attempt는 격리 snapshot으로
병렬 실행할 수 있다. completion request가 verify보다 먼저 오면 REQUIRED_CHECK_MISSING으로 거부한다.
code review 후 새 patch가 생기면 review 재실행이 필요하다. same request ID retry는 중복 실행이 아니다.

기존 UDH lease/fence·event revision 규약을 사용하고 별도 quality 전용 weaker lock을 만들지 않는다.
원자적 완료에는 snapshot뿐 아니라 policy/plan/review/permit revocation 상태를 다시 확인한다.
모든 controller permission 확인은 모델의 주장이나 로컬 파일 flag가 아닌 trusted registry에서 수행한다.

