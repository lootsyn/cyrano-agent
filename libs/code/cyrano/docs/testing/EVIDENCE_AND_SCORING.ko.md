# 증거 수집·채점·변조 방지 계약

## 소유권

`AssessmentRegistry`는 후보 workspace 밖의 control plane이 소유한다. 모델은 `assessment_status()`로 결과를 읽거나 실행을 제안할 뿐 verdict/score/approval/signing key를 쓰지 못한다. suite와 rubric의 변경은 별도 정책 PR·독립 승인·새 evaluation series를 필요로 한다. candidate가 자기 검사기를 always-0으로 바꾸어도 평가 결과를 등록할 수 없어야 한다.

## 데이터 모델

`AssessmentSession`: assessment_id, tenant/user/workspace, source_digest, requirements_digest, plan_digest, policy_digest, runtime_digest, suite_digest, rubric_digest, task_manifest_digest, opened_at, evaluation_mode, authorized_budget, status.

`CaseAttempt`: case_id, attempt_id, assessment_id, input_digest, command_recipe_digest, source_digest, executor_principal, started/finished UTC, duration_ns, executed bool, status(passed/failed/error/blocked/not_run/cancelled/not_applicable), expected_denial bool, observed_product_status, assertion_results, collected_node_ids, executed_node_ids, mandatory_node_ids, stdout/stderr refs, resource_cleanup, evidence_refs. 실행 안 했으면 exit_code=null; count가 unknown이면 null. passed인 경우 executed=true이며 mandatory node가 실제 정상 수행되어야 한다.

`ArtifactReceipt`: artifact_id, bytes_digest, content_type, size, storage_ref, producer_id, sensitivity, availability, created_at, attestation_ref. basename이나 모델 문자열 경로로 원시 파일을 임의 조회하지 않는다. 증거 내용의 hash와 인증된 발신자라는 사실은 다르다.

`AtomDecision`: criterion_id, atom_id, awarded(0/1), case_attempt_ids, evidence_refs, scope, reviewer_principal, review_model_attempt_id(optional), rationale, subject_digest, signed_receipt. 모델의 판단은 조언이며 최종 attestation은 신뢰된 evaluator policy로 발급한다.

`AssessmentReport`: criteria 15개 전부, atom decisions, maximum=40, verified_points, official_score, unavailable IDs, hard_gate_results, release_eligible, report_digest, authorized_reviewer_receipt. 채점 payload의 source/policy/runtime/suite/rubric은 같은 AssessmentSession과 같아야 한다. file/config 한 byte 변경 후 과거 report로 현재 결과 점수를 발급할 수 없다.

## 수집 transaction

1. evaluator가 사전 선언 suite와 task list를 봉인하고 후보에 쓰기 권한을 주지 않는다.
2. trusted runner는 case별 시작을 append하고 lease/fence를 획득한다.
3. 실제 프로세스·모델·tool 결과와 artifact를 저장한다. test plugin 기록은 보조이며 arbitrary candidate Python이 스스로 출력한 JSON을 trusted oracle로 승격하지 않는다.
4. artifact hashes 검증 후 CaseAttempt settlement와 event/outbox를 같은 transaction에 기록한다. 죽은 lease는 재사용할 수 없다.
5. 독립 reviewer가 결과와 원시 로그를 검토하고 동일 subject digest로 AtomDecision을 제출한다.
6. reducer는 15개 항목을 전부 열거하고 mandatory case completeness, authentic receipts, scope·freshness를 확인한 뒤 산술 합계만 계산한다. missing record를 0 tests passed로 처리하지 않는다.
7. report와 revocation check를 같은 control revision에 결속한다. approval·suite가 변경되면 새 assessment 또는 stale 처리한다.

## 채점 알고리즘

각 항목은 rubric의 mandatory_case_ids 전부가 사전 정의된 expected outcome을 충족해야 원자 점수를 심사할 수 있다. 이 필수조건 미충족이면 항목의 `status`는 failed/blocked/incomplete 중 실제 원인으로 두고 점수는 0이다. 충족된 항목도 각 1점 원자에 별도의 충족 evidence가 없으면 0이다. reviewer 의견만 있고 actual LLM/coding/runtime evidence가 없으면 evidence gap이다. 사례 subset 재선택·실패 시도 삭제·skip/xfail를 pass에 더하기를 금지한다.

partial credit는 이 보수적 기본 계약이다. 공식 평가자가 다른 부분점수 규칙을 적용하려면 series 시작 전에 승인 rubric revision을 바꾼다. 사용자 제공 15개 최대 배점은 바꾸지 않는다. 같은 artifact를 여러 항목의 연결 증거로 재사용할 수는 있으나 동일 사실을 서로 다른 기능의 증명으로 과장하지 않는다.

안전 hard gate 결과에 failed가 있으면 release_eligible=false다. unknown/not_run이 있어도 release_eligible=false다. 40점이 계산되어도 운영 승인은 별도다. 전체 미평가는 official_score=null이다. 로컬 `assessment.py`가 출력하는 것은 구조적 completeness와 미평가 scaffold이며 서명 없는 입력으로 공식 점수를 발급하지 않는다.

## 필수 공격 테스트

소스/정책/환경/루브릭 digest mismatch, 다른 workspace의 실제 PASS 영수증 재사용, 임의 JSON으로 producer=trusted 주장, report path symlink/.., 증거 한 byte 수정, 오래된 review·revoked key, duplicate case settlement, 다른 payload의 idempotency key, future schema version, 0 tests·모든 mandatory skipped·setup failure, malformed JUnit+exit0, missing terminal event, filter로 실패 사례 제거, 동시 두 reporter CAS를 테스트한다.

## 개인정보와 보존

synthetic secret canary만 fixture로 사용한다. 실제 API 키·원시 private prompt·사용자 source를 기본 export하지 않는다. content deletion은 log/view/cache/export까지 추적하고 metadata에는 unavailable 이유를 남긴다. 원시 증거가 삭제되어 재심사가 불가능하면 기존 인증 영수증의 존재와 현재 원문 재검증 불가를 따로 표시한다. 코드 입력·provider error·worker log는 모두 prompt injection 가능 데이터다.


## 내장 구조검사의 정확한 범위

`deepagents_code.cyrano.evaluation.assessment`의 `rubric_errors`와 `evidence_structure_errors`는 dictionary 구조·가중치·필수 결과·binding 일관성만 확인한다. `actual_execution` 문자열과 `review_ref`를 제출자가 만들 수 있으므로 이 함수의 errors=[]는 권한이나 진실성 증명이 아니다. TS01은 반드시 서명·키권한·producer registration·artifact bytes·현재 subject·reviewer scope·시간·revocation을 검증하는 별도 trusted service를 구현해야 한다. `scorecard_template`는 항상 미평가/null 공식 점수를 반환한다.

현재 명령 `assessment.py report`는 준비된 미평가 파일을 읽을 뿐이다. `validate_assessment_schema.py`의 synthetic cases는 불법 필드·없는 binding·bool count를 거부하는 schema를 검사하며 점수를 발생시키지 않는다. 서명을 JSON Schema에 넣는 것만으로 신뢰가 만들어지지 않는다.

## Trusted evaluator 구현 예외와 원자성

`register_case_attempt(session_id, case_id, attempt_id, producer_receipt)`는 session의 expected_case_ids 안에 있는 case만 받는다. unique(session_id, case_id, attempt_id) 충돌 시 기존 같은 payload digest는 idempotent, 다른 payload는 EVIDENCE_CONFLICT다. retries는 새 attempt_id로 보존하며 과거 실패를 삭제하지 않는다. quorum이 아닌 지정 final verdict policy가 어떤 attempt를 최종 판정에 쓰는지 사전에 봉인한다.

`verify_evidence_bindings`는 current source snapshot, read-only evaluator suite, runtime lock, resolved policy, run permit, actual raw artifact의 digest가 모두 일치하는지 검사한다. validity 검사는 지금의 UTC와 issuer allowlist로 수행하고, signature 종류·canonical encoding은 기존 v2 trust subject 규칙을 재사용한다. 외부 수신자가 보낸 producer 이름만으로 runner 권한을 인정하지 않는다.

`decide_atom`는 case들 통과 여부와 atom-specific independent review를 별개로 판단한다. 필수 case 하나라도 미실행/불명/필수skip이면 해당 기준은 not_evaluated 또는 blocked이며 예시 점수로 채우지 않는다. 공식 결과를 발급하는 주체는 승인된 평가자이고 사후 임계치 수정은 새 평가 session을 필요로 한다. 점수와 release_eligible을 분리해 중요 안전 failure를 평균 품질로 상쇄하지 않는다.
