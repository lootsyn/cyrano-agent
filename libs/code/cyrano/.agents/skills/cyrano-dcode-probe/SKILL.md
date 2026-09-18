---
name: cyrano-dcode-probe
description: dcode 확장 연결·native tool을 다룰 때 적용하는 CYRANO 개발 절차.
---

# cyrano-dcode-probe

## 적용 조건

dcode 확장 연결·native tool을 다룰 때 이 skill을 읽는다. 상세 제품 계약은 해당 주제의 docs/design 원본과 schema가 소유한다.

## 절차

1. runtime/requirements.in은 조사 기준이지 설치 검증이 아님을 확인한다.
2. 실제 wheel/entrypoint/dependency metadata를 기록한다.
3. 공식 registrar API와 실제 callback/tool/child 경로를 probe한다.
4. setup 실패·권한 우회·virtual shell 경계를 adversarial test한다.
5. 미지원 연결을 다른 SDK loop로 바꾸지 말고 governed launch를 차단한다.

## 완료 기준

할당 WP의 산출물·거부 사례·실제 검증 evidence가 연결되어야 한다. 코드가 없는데 README만으로 구현 완료라고 표시하지 않는다. missing tool/network는 차단 사유이며 PASS로 바꾸지 않는다.
