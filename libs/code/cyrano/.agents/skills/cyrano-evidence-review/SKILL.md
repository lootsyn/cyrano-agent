---
name: cyrano-evidence-review
description: 변경 검토·완료 판정을 할 때 적용하는 CYRANO 개발 절차.
---

# cyrano-evidence-review

## 적용 조건

변경 검토·완료 판정을 할 때 이 skill을 읽는다. 상세 제품 계약은 해당 주제의 docs/design 원본과 schema가 소유한다.

## 절차

1. Author 결론과 별개로 계약·diff·실제 실행 evidence를 읽는다.
2. 잘못된 입력·scope·권한·상태·복구 반례를 확인한다.
3. unit/fixture/integration/live의 증거 수준을 분리한다.
4. 성공 수치나 구현 상태가 실제 명령 출력과 맞는지 확인한다.
5. 필수 미실행 gate를 blocked/not_run으로 기록한다.

## 완료 기준

할당 WP의 산출물·거부 사례·실제 검증 evidence가 연결되어야 한다. 코드가 없는데 README만으로 구현 완료라고 표시하지 않는다. missing tool/network는 차단 사유이며 PASS로 바꾸지 않는다.
