---
name: cyrano-work-cycle
description: 계획된 Work Package를 구현할 때 적용하는 CYRANO 개발 절차.
---

# cyrano-work-cycle

## 적용 조건

계획된 Work Package를 구현할 때 이 skill을 읽는다. 상세 제품 계약은 해당 주제의 docs/design 원본과 schema가 소유한다.

## 절차

1. START_HERE.ko.md와 할당 WP를 읽고 선행 작업·상태·입력 해시를 확인한다.
2. 해당 note·package README·schema·수용 사례만 추가 로딩해 상세 변경 계획을 작성한다.
3. 독립 계획 리뷰와 개발 범위 허가 후 테스트를 먼저 추가한다.
4. 최소 구현·반례·오류·복구를 확인하고 실제 실행한 검증만 보고한다.
5. canonical 문서·schema·fixture·note를 같은 변경에서 갱신하고 docs를 재생성한다.

## 완료 기준

할당 WP의 산출물·거부 사례·실제 검증 evidence가 연결되어야 한다. 코드가 없는데 README만으로 구현 완료라고 표시하지 않는다. missing tool/network는 차단 사유이며 PASS로 바꾸지 않는다.

## R2 통합 의무

`contracts/contract-registry.json`의 명시 버전과 `contracts/integration/acceptance-map.json`을 읽고 할당WP의추가수용을구현한다. source의권한문서를현재API로자동변환하지않는다. 필요한경우 `docs/execution/runbooks/development-execution.ko.md`를읽는다. 현재79/72style위반과quality도구부재를기록하고미검증제품기능을완료로표시하지않는다.
