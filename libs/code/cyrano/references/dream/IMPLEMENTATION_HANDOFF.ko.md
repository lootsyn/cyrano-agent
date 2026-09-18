# 구현 담당 에이전트 작업 지시

목표는 기존 UDH의 기능을 유지하면서 DREAM 방식의 탐색 정책 개선과 지식·절차 개선을 결합하는 것이다. 본 패키지에는 완성된 runtime 코드가 없으며 `udh dream` 명령도 새로 구현할 인터페이스다.

## 첫 작업

기존 UDH 계약과 본문의 §0–6, §14–17, §21–22를 읽고 구체적 구현 계획·리뷰를 먼저 제출하라. 사용자의 현재 설치 runtime을 조사해 버전/hash/확장 API/도구/비동기 자식 관측/격리 경계의 CompatibilityReport를 만들어라. 사용자가 사용하지 않는 SDK loop로 dcode를 대체하거나 dcode core를 patch하지 마라. target repository에 설치용 설정/의존성을 넣지 마라.

## 구현 순서

WP-D00 기존 UDH 정합성과 실제 API → WP-D01 계약/state/권한 migration → WP-D02 관측/snapshot/outbox → WP-D03 replay 정합성 kernel → WP-D04 온라인 dcode discovery 연결 → WP-D05 정책 후보 생성 → WP-D06 실제 paired/holdout 평가 → WP-D07 memory/skill/interview 연결 → WP-D08 release/canary/rollback → WP-D09 관측/경제성/출시 검토 순서로 의존성을 확인하라. 구체적인 WP 범위와 산출물은 본문 §21을 따른다.

## 필수 경계

모델별 특화를 추가하지 않는다. 모든 변경을 replay로 처리하지 않는다. 기록 없는 결과를 생성하지 않는다. 정책은 미래 결과와 private world store를 읽지 않는다. policy stop은 업무 완료가 아니다. 후보는 평가 기준·권한·비밀·승인 원장을 수정하지 않는다. 실행 중인 extension 코드를 자기수정하지 않는다. 각 제품 실행은 immutable release에 묶고 승격에는 CAS와 승인 receipt를 요구한다.

## 검증

JSON 구조에는 동봉 schema를 사용하고 cross-record/정책 타입/권한에는 SEMANTICS의 service 검사를 구현하라. 56개 수용 시나리오를 실제 unit/component/integration/effectiveness tests로 작성하라. fixture 통과를 제품 검증으로 재사용하지 마라. 결과가 불명확하면 not_tested/inconclusive/unsupported를 남겨라. 외부 효과가 timeout으로 불명확하면 무조건 재시도하지 말고 reconcile하라.

## 매 작업 보고

변경 파일, 요구사항 연결, 실행한 검사와 결과, 미실행 검사, 확인된 제약, 원래 실패와 새 회귀, 다음 작업을 보고하라. 계획 승인·실험 허가·하네스 승격·원본 코드 반영·commit/push는 각각의 실제 사용자 권한 범위를 따르라. 이 문서만으로 원격 저장소 push나 Library 덮어쓰기 권한이 생기지 않는다.
