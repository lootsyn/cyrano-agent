# 8. 데이터 계약과 최종 완료 판정

## 8.1 공통 wire 규칙

모든 계약은 `schema_version="1.0"`, extra field 금지, UTF-8 JSON을 사용한다.
ID는 UUID 문자열처럼 opaque 값이며 성공/실패를 encode하지 않는다. digest는
`sha256:` + 소문자 64자리 hex다. 시간은 offset을 포함한 ISO 8601 UTC 기록을 사용한다.
원본 소스/로그 bytes hash와 정규화 계약 hash는 별도다. [U01]

이 패키지 `contracts/reference_models.py`는 아래 QualityPolicy, CheckResult, QualityReport,
CompletionRequirement의 wire 구조와 주요 cross-field 검사에 대한 실행 가능한 참조다.
이는 approval authentication/sandbox/실제 도구 실행을 구현하지 않는다. schema validation은
서명/실행 증거 인증과 다르다. fixture의 ID와 digest는 synthetic이다.

## 8.2 QualityPolicy

| 필드 | 형식/제약 | 의미 |
|---|---|---|
| schema_version | literal 1.0 | wire 버전 |
| policy_id | opaque string | 정책 identity |
| style_profile | team88-doc72 / pep8-79-doc72 | 팀 합의 구분 |
| python_version | major.minor | 대상 코드 최소 Python |
| formatter | literal black | formatter 중복 금지 |
| type_checker | mypy / pyright | 하나의 필수 checker |
| mode | clean / legacy | baseline 허용 여부 |
| source_roots | 비어 있지 않은 상대 경로 배열 | 실제 소스 범위 |
| test_roots | 상대 경로 배열 | 승인된 테스트 범위 |
| required_check_ids | 유일한 check ID 배열 | 최종 필수 검사 |
| max_repair_rounds | 0..10, default 3 | 복구 상한 |
| max_external_retries | 0..3, default 1 | 외부 장애 retry |
| max_no_progress | 1..10, default 2 | 정체 중단 |

profile rule들은 pyproject에 있고 policy는 그 승인본 digest와 결합해 ResolvedQualityPolicy가 된다.
상반된 black/ruff line length, 지원 Python target 불일치는 configuration 오류다.

## 8.3 CheckResult

`check_id`, `tool`, `raw_status=PASS|FAIL|ERROR|BLOCKED|SKIPPED`, `exit_code`,
`diagnostic_count`, `baseline_covered`, `baseline_comparison_digest`, `duration_ms`,
`stdout_digest`, `stderr_digest`, `receipt_id`, `executed`를 가진다.

`baseline_covered=true`는 raw_status=FAIL이고 비교 artifact digest가 있을 때만 허용한다.
검사 결과 FAIL을 PASS로 변경하지 않는다. `baseline_covered`는 controller의 별도 비교 서비스만
설정하며 candidate tool 입력으로 받지 않는다. tests/type/format의 baseline 적용 가능 여부는
해당 정책과 9장의 제한을 따른다. stdout/stderr가 없으면 null이며 허위 hash를 채우지 않는다.

`executed=false`이면 exit_code는 null, raw_status는 BLOCKED 또는 SKIPPED여야 한다.
실행했는데 return code를 확보하지 못한 timeout도 executed=true/exit_code=null/ERROR다.

## 8.4 QualityReport

`report_id`, `workspace_id`, `attempt_id`, `plan_digest`, `policy_digest`,
`toolchain_digest`, `suite_digest`, `snapshot_before`, `snapshot_after`,
`required_check_ids`, `checks[]`, `verdict`, `verification_level`, `created_at`.

`snapshot_before`/`snapshot_after`는 **같은 후보를 검사하기 직전과 직후의 snapshot**이다.
구현 전 base snapshot과 구현 후 후보 snapshot을 비교하는 필드가 아니다. 구현 시작점은
WorkPlan의 `base_snapshot_digest`와 guard의 preimage에 따로 보존한다.
QualityReport verdict에는 취소를 넣지 않는다. CANCELLED는 orchestration의 작업 상태이며
취소 artifact로 남긴다. 누락된 검사에 임의 성공 report를 생성하지 않는다.

`verification_level=local_advisory|governed`는 보고서의 선언 필드지만, 실제 신뢰는 controller 저장소의
등록 경로/인증된 runner receipt에서 결정한다. 모델이 값을 governed로 바꿔도 권한은 생기지 않는다.
예제 JSON을 복사한 파일을 service가 report ID로 자동 import하지 않는다.

필수 check ID가 없거나 중복이면 PASS 금지. required check의 SKIPPED는 BLOCKED다.
추가 optional check가 FAIL이어도 mandatory verdict와 분리할 수 있지만 보고서에 그대로 노출한다.
보호 정책상 blocking security/review finding은 optional로 분류할 수 없다.

## 8.5 reducer: 우선순위와 합격식

첫 구현은 순수 함수 `derive_verdict(report_inputs)`로 만든다.

사용자 취소는 orchestration이 우선 처리하며 작업을 CANCELLED로 끝낸다. 아래 gate reducer에
취소된 작업의 성공을 요청하지 않는다. reducer의 정확한 우선순위는 다음과 같다.

1. snapshot_before != snapshot_after이면 STALE.
2. required check에 ERROR가 있으면 ERROR.
3. required check 누락/중복 또는 BLOCKED/SKIPPED이면 BLOCKED.
4. baseline으로 승인되지 않은 required FAIL이 있으면 FAIL.
5. approved baseline으로만 덮이는 required FAIL이 하나 이상이면 PASS_WITH_BASELINE.
6. 나머지 required checks가 모두 PASS이면 PASS.

중복 required ID 또는 check ID는 wire validator가 먼저 거부한다. reducer를 직접 호출해도
이런 입력으로 PASS가 나와서는 안 된다. 참조 코드와 테스트는 이 순서를 고정한다.
검사 대상 없는 작업에 임의 empty required set을 주어 PASS를 만들지 않는다. not applicable은
상위 plan에서 Python gate 비대상으로 처리하고 `NOT_APPLICABLE` 별도 artifact를 남긴다.

## 8.6 완료 서비스: 모델이 통과시킬 수 없는 조건

`request_completion(attempt_id, report_id, expected_revision)`만 제공한다. 모델 입력으로
`required_checks`, `policy`, `approved`, `allow_baseline`, `status=COMPLETE`를 받지 않는다.

서비스 처리 순서:

1. authenticated session이 attempt를 소유하며 허가된 상태인지 조회한다.
2. PlanPermit, CodeReview, required-check manifest를 trusted store에서 읽는다.
3. report ID가 trusted runner channel에서 등록된 receipt인지 확인한다.
4. workspace/attempt/plan/policy/toolchain/suite digest가 모두 일치하는지 확인한다.
5. plan code-review 대상 snapshot과 report snapshot 및 현재 승인 후보 snapshot이 일치하는지 확인한다.
6. required check IDs를 plan/policy에서 다시 계산하여 report와 비교한다.
7. semantic reducer를 다시 실행한다. report.verdict 문자열을 그대로 믿지 않는다.
8. review approve와 unresolved blocker=0, 필요한 사람 승인, 유효 exception/baseline permit을 확인한다.
9. `expected_revision`, snapshot, permit revision, review revision을 하나의 transaction/CAS로 검사한다.
10. event append + WorkUnit 상태 변경 + outbox를 원자적으로 저장한다.

clean PASS는 COMPLETE, 명시적 legacy approval이 있는 PASS_WITH_BASELINE은 COMPLETE_BASELINED다.
그 외에는 상태를 성공으로 바꾸지 않고 구체적인 rejection code를 반환한다.
검사 통과 후 자동 commit/push/merge는 별도 권한이므로 수행하지 않는다.

## 8.7 저장과 idempotency

report/log은 content-addressed blob store에 tmp write → fsync → rename으로 저장한다.
metadata는 기존 SQLite event store 확장 migration으로 추가한다. 새 독립 승인 저장소를 만들지 않는다.
`quality_reports(report_id PK, attempt_id, snapshot_digest, report_digest UNIQUE, runner_receipt_id,
created_at)` 및 `quality_requests(request_id PK, payload_digest, report_id, state)`를 추가한다.

같은 idempotency key와 같은 payload의 재요청은 기존 결과를 반환한다. 같은 key/다른 payload는
CONFLICT다. crash 후 이미 등록된 result를 다시 실행해서 중복 청구/중복 완료하지 않는다.
진행 중 lease가 만료되면 ERROR_RUNNER_LOST이며 절대 성공으로 복원하지 않는다.
다른 attempt/report를 재사용하는 replay는 attempt/snapshot binding으로 차단한다.

log/report 원본에는 보존 정책을 적용한다. 기본 로컬 raw log 14일, normalized result 90일,
승격된 improvement evidence는 release 감사 기간 동안 유지하도록 설정한다. 이 기간은 제품 기본값이며
조직 retention 규정에 맞춰 승인 변경한다. 원본 삭제 뒤에도 evidence available=false를 표시한다.
