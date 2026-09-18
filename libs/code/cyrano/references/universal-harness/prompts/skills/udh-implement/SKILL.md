---
name: udh-implement
description: 승인된 범위의 기능·버그·리팩터링을 구현하는 작업
---

# udh-implement

## 입력과 전제

현재 authenticated session/task, scope/policy/release digest, 필요한 approved artifact와 memory view를 읽는다. 부족한 권한은 도구를 우회하지 말고 요청/blocked로 처리한다.

## 실행 절차

현재 lease/permit 확인 → 기존 코드·테스트 읽기 → bounded patch → 승인 recipe → postimage 검증 → 범위 변경 시 중단/재계획.

## 산출물

change manifest/verification evidence. 관련 요구사항 ID: AUTH-01. 정확한 schema는 UDH 계약 문서를 따른다. source 변경과 실행은 Broker만 수행하며 이 Skill은 권한을 부여하지 않는다.

## 실패·변경 처리

stale input, unexpected file change, required reviewer 실패, 예산 소진, 보안/감사 장애는 명시적 상태로 반환한다. 미실행 테스트·모델 자기평가를 실제 완료 증거로 보고하지 않는다. 활성 skill/memory를 직접 수정하지 않는다.
