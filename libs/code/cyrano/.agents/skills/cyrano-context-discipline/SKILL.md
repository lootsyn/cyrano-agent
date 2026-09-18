---
name: cyrano-context-discipline
description: 에이전트 지침·skill·context를 바꿀 때 적용하는 CYRANO 개발 절차.
---

# cyrano-context-discipline

## 적용 조건

에이전트 지침·skill·context를 바꿀 때 이 skill을 읽는다. 상세 제품 계약은 해당 주제의 docs/design 원본과 schema가 소유한다.

## 절차

1. root AGENTS에는 상시 규칙만 유지하고 상세 절차를 skill로 옮긴다.
2. static prefix와 dynamic task tail의 변동 원인을 분리한다.
3. metadata·본문·references의 로딩 단계를 검증한다.
4. role/model 특화 분기·duplicate skill·dynamic timestamp를 찾는다.
5. actual cache 실험이 없으면 stable bytes 검사까지만 보고한다.

## 완료 기준

할당 WP의 산출물·거부 사례·실제 검증 evidence가 연결되어야 한다. 코드가 없는데 README만으로 구현 완료라고 표시하지 않는다. missing tool/network는 차단 사유이며 PASS로 바꾸지 않는다.
