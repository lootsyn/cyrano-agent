# 5. 작업 계획과 상태 전이

## 5.1 WorkPlan 계약

기존 WorkUnit에 다음 내용을 결합한다. 임의로 두 번째 ID 체계를 만들지 않는다.

- `workspace_id`, `run_id`, `work_unit_id`, `attempt_id`: opaque IDs.
- `requirement_ids`, `acceptance_ids`: 각각 원본 registry에서 조회 가능해야 한다.
- `base_snapshot_digest`, `policy_digest`, `toolchain_digest`: 변경 전 기준.
- `allowed_paths`, `forbidden_paths`: repo-relative POSIX glob; source scope와 보호 정책을 함께 검사.
- `expected_changes`: 파일/동작/호환성 설명. 존재하지 않는 경로는 생성 허가 여부가 필요하다.
- `test_obligations`: acceptance ID → 구체적인 test recipe + 기대 결과.
- `required_checks`: formatter/lint/type/unit 및 변경에 필요한 integration/acceptance IDs.
- `risk`: normal 또는 elevated. 정책·의존성·schema migration·보안·public API 변경은 elevated.
- `repair_budget`: max_repair_rounds=3, max_external_retries=1, max_no_progress=2.
- `dependencies`: WorkUnit IDs. 자기 참조·순환·누락 의존성은 거부한다.
- `non_goals`: 작업 범위 확대를 막는 명시적 항목.

매핑이 없는 acceptance, 빈 mandatory suite, 알 수 없는 check ID, 허용 범위를 벗어난 경로,
“테스트는 나중에” 같은 검증 계획은 승인하지 않는다. 문서로 남겼다는 사실만으로 plan review가 아니다.

## 5.2 PlanReview와 승인

계획의 기계적 검증을 먼저 실행한다. 이후 별도 reviewer가 아래 질문에 근거로 답한다.
요청이 실제 동작으로 표현되는가? 기존 호환성이 유지되는가? 변경하지 않아도 되는 파일이 포함됐는가?
오류·경계 사례·실패 경로를 검증하는가? dependency/권한 상승이 필요한가?

review output: `review_id`, `reviewer_execution_id`, `subject_digest`(계획 digest),
`disposition=approve|request_changes|blocked`, `findings[]`, `evidence_refs[]`.
`findings`는 severity와 blocking 여부를 가진다. unresolved blocker가 있으면 approve는 무효다.
기계 검증 PASS + 실제 review receipt + 정책상 필요한 사람 승인으로 controller가 PlanPermit을 발급한다.
모델이 JSON에 `approved=true`를 써 넣어도 permit이 생기지 않는다.

소규모 작업도 계획 artifact는 필요하지만 짧게 만들 수 있다. 파일명 오타 수정에 긴 질문 인터뷰를
강제하지 않는다. 기존 InterviewOutcome가 있으면 requirement/acceptance IDs를 재사용한다.

## 5.3 상태 전이

```text
RECEIVED → INSPECTING → PLAN_DRAFTED → PLAN_REVIEW
PLAN_REVIEW → IMPLEMENTING         [유효 PlanPermit]
PLAN_REVIEW → PLAN_DRAFTED          [request_changes]
IMPLEMENTING → VERIFYING           [snapshot 봉인]
VERIFYING → REPAIRING              [수정 가능한 새 실패 + 예산]
REPAIRING → IMPLEMENTING           [수정 round 증가]
VERIFYING → CODE_REVIEW            [기계 gate PASS 또는 PASS_WITH_BASELINE]
CODE_REVIEW → IMPLEMENTING         [정당한 변경 요청 + 예산]
CODE_REVIEW → COMPLETION_PENDING   [approve]
COMPLETION_PENDING → COMPLETE      [최종 CAS 성공, clean gate]
COMPLETION_PENDING → COMPLETE_BASELINED [명시적 legacy permit]
어느 실행 상태 → BLOCKED / FAILED / CANCELLED [원인에 따라]
```

모델의 답변 종료와 작업 완료는 다르다. “계속할 수 없음”을 설명하고 대화를 끝낼 수는 있으나
work status를 COMPLETE로 바꿀 수 없다. 사용자 취소는 언제든 우선한다.

## 5.4 코드 변경 후 증거 무효화

source/test/config/resource bytes가 하나라도 바뀌면 해당 snapshot의 최종 PASS와 code review는
현재 후보 완료에 재사용할 수 없다. 같은 Git HEAD와 같은 파일 개수도 동일 snapshot이 아니다.

같은 immutable snapshot에서 formatter와 lint를 병렬 실행하는 것은 가능하지만 첫 구현은 순차다.
피드백 단계의 partial check는 최종 gate를 대체하지 않는다. v1에서는 최종 full gate receipt를
항상 새로 만들고 과거 PASS 재사용 최적화를 하지 않는다.

## 5.5 오류 분류와 복구

| 분류 | 예 | 다음 동작 |
|---|---|---|
| CODE_VIOLATION | F401, 잘못된 타입, 회귀 테스트 fail | cause 수정, 새 snapshot, gate 재실행 |
| POLICY_VIOLATION | 승인 없는 noqa/config/test scope 축소 | 변경 철회 또는 별도 정책 승인 요청 |
| EXISTING_DEBT | 동일 immutable baseline의 기존 lint | legacy 규칙 적용, 부채를 유지·표시 |
| ENV_BLOCKER | 필요한 interpreter/stub/격리 service 없음 | 승인된 환경 복구 1회, 미해결 시 BLOCKED |
| TOOL_ERROR | 잘못된 JSON, 내부 오류, 알 수 없는 exit code | ERROR; 코드 위반으로 오분류하지 않음 |
| FLAKY | 같은 snapshot/환경에서 상충 결과 | INCONCLUSIVE 취급, quorum으로 덮지 않음 |
| NO_PROGRESS | 동일 patch digest 또는 동일 진단이 2회 지속 | 재계획 또는 BLOCKED_NO_PROGRESS |
| BUDGET | 허가된 round/time/cost 소진 | BLOCKED_BUDGET; 성공을 꾸미지 않음 |

다른 수정과 함께 예산을 초기화하지 않는다. 예산 증가에는 trusted permit이 필요하다.
비용/시간은 controller가 측정한다. 모델이 token 사용량을 보고하지 못하면 unknown을 기록하고
금액 hard budget을 보증할 수 없는 backend에서는 보수적인 호출 상한을 병행한다.
