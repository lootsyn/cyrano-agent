---
name: cyrano-path-b-change
description: memory·skill·코드 자기개선을 구현할 때 적용하는 CYRANO 개발 절차.
---

# cyrano-path-b-change

## 적용 조건

memory·skill·코드 자기개선을 구현할 때 이 skill을 읽는다. 상세 제품 계약은 해당 주제의 docs/design 원본과 schema가 소유한다.

## 절차

1. approved LearningWorkPlan과 baseline을 확인한다.
2. 입력 의미 변경은 B이며 actual paired eval이 필요함을 유지한다.
3. protected evaluator·approval·audit 변경은 수동 정책 review로 분류한다.
4. 한 가설 최소 diff와 대안 설명·반례·rollback을 남긴다.
5. 현재 runtime을 직접 덮어쓰지 않고 immutable release를 사용한다.

## 완료 기준

할당 WP의 산출물·거부 사례·실제 검증 evidence가 연결되어야 한다. 코드가 없는데 README만으로 구현 완료라고 표시하지 않는다. missing tool/network는 차단 사유이며 PASS로 바꾸지 않는다.
