# R4 추가 검증·수용 프로토콜

문서 유형: 테스트 설계. 기존 사례와 52개 세분 사례를 현재 단일 catalog에 연결한다. 명세 수와 실제 실행 완료 수를 구분한다. R4의 복사·문서 준비 사례와 native 제품·실제 효과 사례는 서로 다른 test_layer이며 준비 검사를 제품 채점에 사용하지 않는다.

[전체 R4 사례](../../tests/r4/cases.json)는 각 사례의 Given/When/Then, target test path/symbol, fixture contract, raw evidence, cleanup을 가진다. 실제 구현 후 pytest collection과 실행 결과가 있어야 제품 evidence로 인정한다.

## 실행 계층

L0: manifest·문서 링크·schema·routing·DAG·SQL syntax 준비 검사. L1: 순수 함수·DB transaction·reducer·validator unit. L2: 실제 native graph/adapters에 fake provider를 연결해 control logic 검사. L3: 실제 OS process·sandbox·승인·child·resume·UI. L4: 승인된 actual provider baseline/candidate 효과 평가.

3-1은 L3 새 process 지속성, 3-2는 L2/L3의 실제 plan/code/test 반영, 3-3은 L2 이상 근거 기반 생성과 L4 표본, 3-4는 L4 비교 및 L3 next-run 적용을 함께 요구한다. 4번은 mode별 L2/L3 coverage와 실제 source의 보장 범위를 명시한다. L0/L1만 통과하면 평가 결과는 미평가/부분 증거다.

## 평가 부정 방지

candidate가 자기 fixture·oracle·expected result·승인·원장·분모를 바꾸면 invalid 또는 hard fail. sealed data 접근은 별도 principal. source/runtime/policy/suite digest가 다르면 이전 result 재사용 금지. byte-hash는 파일 일치만 보장하며 결과 작성자의 권위를 대신하지 않는다. 기준별 partial credit은 사전 rubric과 독립 reviewer가 판단하고 document count를 점수로 바꾸지 않는다.

## 무조건 거부할 위장 통과

0 tests, pytest skip을 제품 pass로 보고, native 대신 독립 SDK loop 호출, model self-report만으로 applied/promoted, 미관측 호출을 0회, unknown usage를 비용 0, 수정하지 않은 문서를 implemented로 이동, current source와 다른 오래된 evidence로 채점, 숨은 평가 변경, 실제 제품이 아닌 synthetic tree copy test를 real clone 적용으로 설명하는 행동을 거부한다.
