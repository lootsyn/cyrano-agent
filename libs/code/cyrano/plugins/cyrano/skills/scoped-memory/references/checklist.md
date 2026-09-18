# scoped-memory: 상세 검토

## 검토 1

query hit와 applied/effective를 구분한다.

충족 근거는 실제 event/artifact ID로 연결한다. 근거가 없으면 unknown 또는 blocked로 표시한다.

## 검토 2

stale fact·candidate는 authoritative advice가 아니다.

충족 근거는 실제 event/artifact ID로 연결한다. 근거가 없으면 unknown 또는 blocked로 표시한다.

## 검토 3

사용자 선호를 다른 tenant에 일반화하지 않는다.

충족 근거는 실제 event/artifact ID로 연결한다. 근거가 없으면 unknown 또는 blocked로 표시한다.

## 회귀 사례

적용 조건을 만족하는 positive case와 적용하면 안 되는 counterexample을 모두 검증한다. 실행 시 표준 수용 catalog의 해당 skill 항목과 연결한다.

## 컨텍스트 유지

본문은 release마다 고정하고 run ID·날짜·경로·실시간 결과를 본문에 삽입하지 않는다. 동적 값은 AgentTask tail에서 받는다.
