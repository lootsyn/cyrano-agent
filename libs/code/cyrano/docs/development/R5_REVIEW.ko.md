# 현재 설계 정합성 및 개발 시작 판정

## 구조와 책임

dcode가 유일한 agent loop다. Cyrano 제품 namespace·테스트·개발자료 위치는 그대로 유지했다. 연구팩의 설계는 기존 owner에 직접 반영하며 설치할 별도 보완팩이 없다. runtime audit/approval/release 이력은 제품 기능이고, 준비 ZIP의 revision 역사와 구분한다.

## 해결한 설계 충돌

계획 승인과 ExecutionPermit를 분리했다. WorkflowIR에 자기 허가 receipt를 넣어 subject digest가 순환하는 구조를 제거했다. Control revision과 관측 seq를 분리해 정상 이벤트가 매번 승인을 무효화하지 않도록 했다. 초기 seed release와 학습 승격을 분리해 부팅 의존 순환을 없앴다. Memory와 관측을 계획 실제 실행의 선행 조건으로 명시했다. LangGraph resume 전역 효과 중복, 늦은 비용 결과 누락, 제품 권한과 개발용 skill 지침 혼동을 상세 설계에 반영했다.

## 남는 구현 의무

현재 제품 서비스·권한 강제·provider 계측·native TUI/승인 UI의 모든 연결이 구현 완료된 것은 아니다. 자기개선 효과는 실제 비교 실험으로 확인해야 한다. 문서와 schema의 구조 통과는 사용자 평가 점수가 아니다. 현재 검사 결과는 evidence의 최신 report를 참조하고 과거 납품 PASS를 현재 소스 판정으로 재사용하지 않는다.

## 독립성

이번 문서 대조는 작성자 검토다. 별도의 인증된 모델 reviewer 또는 사람 승인 절차를 실제로 실행했다고 하지 않는다. 구현 단계에서 입력·리뷰 assignment·finding·검증 evidence를 연결해 독립 리뷰를 수행한다.
