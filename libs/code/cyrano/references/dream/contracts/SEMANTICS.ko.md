# 계약 의미와 서버 측 불변조건

JSON Schema는 구조 검사다. 다음 사항은 trusted service와 통합 테스트에서 반드시 검사해야 한다. 이 문서는 아래 validator가 모두 구현됐다는 뜻이 아니다.

## 1. Record 연결

World의 episode/attempt/slot 참조는 같은 scope에 존재해야 한다. 전체 dependency graph는 비순환이어야 한다. closure watermark 전에 시작된 모든 시도의 terminal/unknown outcome을 확인한다. complete 상태는 모델이 지정하지 않는다. digest는 실제 canonical artifact bytes에서 재계산하며 fixture용 라벨 해시를 제품 검증에 쓰지 않는다.

## 2. View와 action

view는 공개된 prefix만 투영한다. action_id, slot_id, node_id는 각각 유일해야 한다. action의 dependency는 공개 node에만 속해야 한다. action 목록은 온라인 합법성에서 생성하며 replay support로 제한하지 않는다. 원본 outcome store와 모델/endpoint 이름은 policy에 전달하지 않는다.

선택한 action은 해당 view의 목록에 있어야 한다. batch 크기는 worker_cap과 남은 permit budget 이하이고 parent-child 의존 행동을 포함하지 않는다. 같은 view를 다른 release/round에 재사용하지 못하게 view digest와 revision을 검증한다.

## 3. ReplayStep

batch 전이 지원 여부를 모두 검사한 뒤 원자적으로 공개한다. 하나라도 미지원이면 결과를 일부 공개한 성공 step으로 처리하지 않는다. 이미 지원된 이전 round의 prefix는 보존한다. 미래/미지원 score를 생성하지 않는다. replay trace의 지연·비용은 실측 청구가 아니라 정한 가정의 proxy다.

## 4. PolicyIR 타입

모든 node_id는 유일해야 한다. node reference는 존재하고 DAG여야 한다. feature 타입: recoverable_failure, underexplored_direction, has_valid_anchor, information_missing은 bool; 나머지는 number다. missing 수치는 신뢰된 feature builder가 규정한 기본값과 information_missing=true로 함께 투영한다. 원시 null을 0의 확정 관측으로 취급하지 않는다.

add/subtract/multiply/safe_divide/min/max는 number 입력2개→number, clamp는 number 입력3개→number, less_than/greater_than은 number 입력2개→bool, and/or는 bool 입력2개→bool, not은 bool 입력1개→bool이다. score_root는 number, stop_root는 bool, batch_size_root는 number다. batch_size는 floor 후 [1, min(worker_cap, 남은 허가 attempts, 합법 action 수)]로 제한한다. 합법 action 또는 budget이 없으면 stop을 반환한다. stop=false가 무한 실행 권한은 아니다.

safe_divide에서 0 분모는 명시된 상수 fallback 0과 diagnostic을 반환한다. nonfinite 결과는 policy invalid다. 깊이≤16, node≤128, 평가 operation≤max_operations≤2048을 강제한다. 동점에서만 stable opaque action ID 정렬을 사용한다. Python 제안은 이 schema의 op를 확장해 우회하지 않고 별도 검토 경로로 보낸다.

## 5. CandidateExtension

기존 UDH Candidate의 새 extension payload이며 대체 schema가 아니다. verified_effect_class와 classification_receipt는 trusted classifier만 작성한다. 보호 표면 수정·범위 확대를 발견하면 reject한다. extension_code_proposal의 CI/사람 승인 요구를 유지한다. state는 kernel transition API만 변경한다. JSON에 promoted가 있어도 승인·승격 증거가 되지 않는다.

## 6. EvaluationSummary

scheduled_world_count = full_support_count + out_of_support_count + invalid_world_count + incomplete_world_count다. world의 실패 이유는 이 집계에서 상호 배타적으로 분류한다. hard gate failure가 하나라도 있으면 eligible_for_review가 될 수 없다. eligible_for_review는 release 승인/배포가 아니다.

실제 paired test·독립 family·사전 등록 기준·sealed holdout evidence가 없으면 effectiveness_validated를 기록하지 않는다. confidence bounds가 있으면 lower≤upper다. cost_coverage는 관측 비용을 갖는 호출/작업의 명시된 분모에서 계산한다. 평가 종료까지 terminal이 없는 실험은 무효/불확실로 표시한다.

## 7. 권한과 경합

readonly mount, broker-owned writer, OS/container 권한, policy DTO 분리, 별도 holdout evaluator로 정보/행동 경계를 강제한다. schema와 prompt만으로 격리를 주장하지 않는다. 승격은 승인된 artifact/parent/experiment/scope digest에 묶이고 active pointer CAS를 사용한다. 늦은 worker는 fencing token으로 차단한다.

## 8. 기존 문서와의 충돌

기존 R01–R22, 계획/권한/메모리 규칙은 삭제하지 않는다. 구조·문서·fixture가 충돌하면 임의 해석으로 진행하지 말고 버전·migration·테스트를 함께 수정한다. 미지원 dcode API를 가정하거나 코어를 patch하여 테스트를 통과시키지 않는다.
