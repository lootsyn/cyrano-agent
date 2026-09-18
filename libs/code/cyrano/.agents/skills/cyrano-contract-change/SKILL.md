---
name: cyrano-contract-change
description: schema·wire·durable data를 바꿀 때 적용하는 CYRANO 개발 절차.
---

# cyrano-contract-change

## 적용 조건

schema·wire·durable data를 바꿀 때 이 skill을 읽는다. 상세 제품 계약은 해당 주제의 docs/design 원본과 schema가 소유한다.

## 절차

1. 소유 타입·모든 consumer·digest subject projection을 찾는다.
2. 필드·enum 변경을 인접 schema/migration과 함께 계획한다.
3. positive/negative/semantic/authority 사례를 분리해 작성한다.
4. schema가 형식을 통과해도 승인으로 취급하지 않는지 검사한다.
5. 원본 reference는 보존하고 generated catalog만 갱신한다.

## 완료 기준

할당 WP의 산출물·거부 사례·실제 검증 evidence가 연결되어야 한다. 코드가 없는데 README만으로 구현 완료라고 표시하지 않는다. missing tool/network는 차단 사유이며 PASS로 바꾸지 않는다.

## R2 통합 의무

`contracts/contract-registry.json`의 명시 버전과 `contracts/integration/acceptance-map.json`을 읽고 할당WP의추가수용을구현한다. source의권한문서를현재API로자동변환하지않는다. 필요한경우 `docs/execution/runbooks/development-execution.ko.md`를읽는다. 현재79/72style위반과quality도구부재를기록하고미검증제품기능을완료로표시하지않는다.
