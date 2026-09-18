# 12. 관측과 제한적 자기개선

## 12.1 이벤트

기존 UDH Attempt 이벤트 흐름에 다음을 추가한다.
`quality.policy_resolved`, `quality.plan_reviewed`, `quality.snapshot_sealed`,
`quality.check_started`, `quality.check_finished`, `quality.gate_finished`,
`quality.repair_requested`, `quality.repair_exhausted`, `quality.completion_rejected`,
`quality.completion_accepted`, `quality.improvement_proposed`.

공통: schema_version, event_id, timestamp_utc, workspace_id, run_id, work_unit_id,
attempt_id, parent_event_id, policy_digest, snapshot_digest, artifact_refs.
check 이벤트: check_id, tool/version, raw/effective status, duration_ms, diagnostic counts,
exit_code, receipt_id. check start만 있고 finish가 없으면 success가 아닌 missing observation이다.

모델 내부 사고 내용을 수집할 필요는 없다. 계획, 도구 호출, patch, 실행 결과, reviewer 근거 같은
관측 가능한 산출물로 감사한다. 전체 prompt/비밀/코드를 원격 tracing에 자동 업로드하지 않는다.
로컬 이벤트 저장이 기본이며 remote export는 별도 동의와 redaction 정책을 따른다.

## 12.2 지표의 분모

`first_pass_rate`: 최초 최종 gate에서 PASS 또는 명시적 baseline pass를 얻은 WorkUnit / 실제 gate를
실행한 WorkUnit. clean/base-lined 비율을 분리한다. 환경 BLOCKED를 분모에서 제외할 때 제외율을 함께 표시한다.

`repair_rounds`: 코드 수정 round 수. 같은 test 재시도 횟수와 분리한다.
`new_violation_rate`: 정확한 baseline comparison 이후 새 위반 WorkUnit 비율.
`verification_coverage`: required checks 중 실행·증거가 있는 checks 비율. PASS 비율과 다르다.
`completion_integrity`: 잘못된 completion 요청 중 실제 수락된 수. 항상 0이 목표다.
`semantic_acceptance_rate`: 보호된 동작/요구 테스트의 성공률.
`cost`: 실제 확인된 비용만 합산; 일부 provider usage가 누락되면 unknown coverage도 표시한다.

동일 Attempt의 모델 호출 20개를 20개의 독립 사례로 세지 않는다. 같은 코드에 대한 반복 실행도
별도 task 성공처럼 부풀리지 않는다. [U01,U02]

## 12.3 관측에서 개선 후보까지

예: 서로 다른 작업에서 B006이 반복되면 “새 함수 기본 인자의 mutable 값을 pre-review에서 확인”하는
Skill 변경을 제안할 수 있다. 그러나 초기 관측만으로 원인을 확정하지 않는다. traceback 오독,
외부 템플릿, 잘못된 profile 등이 원인일 수 있으므로 hypothesis와 확인된 사실을 분리한다.

초기 제안 기준은 최근 eligible WorkUnit 20개에서 서로 다른 3개 이상에 같은 실패 family가 나타나는
정도로 둔다. 작은 표본에서는 단순 개선 제안만 하고 자동 배포하지 않는다.
`failure_family`, evidence report IDs, 가설, 대안 원인, 대상 Skill section, 최소 patch,
예상 효과, 위험, 평가 계획, rollback release를 proposal에 포함한다.

## 12.4 경로 A와 경로 B

경로 A: 복구 순서/검색 예산/시도 선택 같은 탐색 정책 개선. 과거 실행을 replay할 수 있는 범위와
실제 행동 의미를 유지하는 범위를 명시한다. 기록되지 않은 후보 결과를 가정해 보상하지 않는다.

경로 B: Skill 문장, 계획 검토 절차, memory, 코드, 검사 recipe를 바꾸는 개선.
입력/동작이 달라지므로 과거 실행 점수 replay만으로 효과가 입증되지 않는다.
격리 환경에서 기준안과 후보의 실제 실행을 비교해야 한다. [U02]

품질 규칙 완화, baseline 확대, acceptance/test 삭제, 예외 자동 승인, 권한 확대는 protected surface다.
일반 self-improvement가 이를 변경하거나 승인할 수 없다. 별도 정책 변경 작업과 사람 검토가 필요하다.

## 12.5 평가와 승격

데이터를 failure family/프로젝트군 기준으로 development/holdout으로 분리한다.
비슷한 코드 복사본이 양쪽에 들어가 leakage가 나지 않게 한다. 후보 author는 holdout 정답을 보지 않는다.
같은 task/policy/toolchain/model routing 조건으로 A/B 실행을 pairing하고, 확률성을 고려해 반복한다.

정확성·승인 위반·검증 무결성이 우선이다. cached tokens·latency·lint round 개선만으로 승격하지 않는다.
최소 gate는 다음과 같다.

- policy bypass 또는 잘못된 completion 수락 0건.
- 보호된 acceptance의 새 regression 0건.
- 사전 등록된 task 성공률 비열등 기준을 만족해야 함.
- 선언한 주요 효율 지표가 사전 등록한 최소 개선 기준을 만족해야 함.
- 비용/latency 악화가 승인 budget을 넘지 않아야 함.

통계 표본/interval이 부족하면 INCONCLUSIVE로 유지한다. 임의 “5% 개선” 숫자를 측정 없이 붙이지 않는다.
초기 자동 승격은 disabled, paid evaluation budget은 0이다. 사용자/관리자가 평가 실행을 승인한 뒤만
실제 유료 모델 호출을 수행한다. 후보를 생성했다는 것과 배포했다는 것을 구분한다.

승격은 proposal → experiment approval → paired rerun → independent review → human release approval
→ immutable Skill/policy release → canary → regression detection → rollback 순서다.
동작을 바꾸는 Skill은 다음 attempt부터 적용한다. 실행 중인 task의 캐시를 유지하려고 옛/새 정책을
섞거나 유료 dummy warming 요청을 보내지 않는다.
