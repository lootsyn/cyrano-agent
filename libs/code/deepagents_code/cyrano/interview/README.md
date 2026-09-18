# cyrano-interview

## 현재 구현

의무별 blocker readiness·dependency 무효화·원본 role/digest worker binding. 이 package는 개발 foundation이며 전체 제품 runtime과 권한·효과 검증을 의미하지 않는다.

## 소유 계약

Python import는 `deepagents_code.cyrano.interview`다. 공개 함수/Protocol의 현재 의미는 [소스](src/deepagents_code.cyrano.interview)와 [subsystem](../../../docs/subsystems/interview.md)에서 확인한다. 외부 JSON은 contracts/v1 schema와 의미 검사를 통과해야 한다. source tree의 private 경로를 다른 package에서 import하지 않는다.

## 의존성과 lifecycle

로컬 dependencies: cyrano-contracts. import-time 네트워크·모델 호출·worker 시작이 없다. stateful provider는 명시 close/dispose를 사용한다. App composition이 구체 provider와 권한을 결합한다.

## Model Experience

모델에 제공되는 정보는 caller scope에 제한된 입력과 결과다. JSON 형식·내부 bool·status 값은 실행 권한이 아니다. unknown/unsupported/failed/not_run을 빈 성공 결과로 바꾸지 않는다. 해당 native dcode tool이 아직 바인딩되지 않았다면 제공한다고 표시하지 않는다.

## 구현할 확장

담당 작업: WP07, WP08. 목표 전체 설계는 `.agents/notes/proposed`와 WP 파일을 따른다. 각 WP의 파일·API·수용 사례는 실제 제공자/소비자·실패 동작을 구현할 때 함께 완성한다.

## 검증과 제한

`python scripts/dev.py test`는 저장소 root에서 실행한다. 현재 테스트는 foundation 동작을 검사한다. signature/OS isolation/실제 dcode/provider/통계 효과를 통과했다고 주장하지 않는다. 세부 제품 검증은 WP별 targeted test와 실제 integration/live evidence가 필요하다.
