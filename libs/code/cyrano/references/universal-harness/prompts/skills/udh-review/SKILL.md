---
name: udh-review
description: 명세·계획·코드 결과를 독립적으로 검토하는 작업
---

# udh-review

## 입력과 전제

현재 authenticated session/task, scope/policy/release digest, 필요한 approved artifact와 memory view를 읽는다. 부족한 권한은 도구를 우회하지 말고 요청/blocked로 처리한다.

## 실행 절차

정확한 input digest 확인 → 체크리스트와 실제 evidence → 반례/회귀/권한 → findings → 수정 후 재검토.

## 산출물

ReviewResult. 관련 요구사항 ID: PLAN-01. 정확한 schema는 UDH 계약 문서를 따른다. source 변경과 실행은 Broker만 수행하며 이 Skill은 권한을 부여하지 않는다.

## 실패·변경 처리

stale input, unexpected file change, required reviewer 실패, 예산 소진, 보안/감사 장애는 명시적 상태로 반환한다. 미실행 테스트·모델 자기평가를 실제 완료 증거로 보고하지 않는다. 활성 skill/memory를 직접 수정하지 않는다.
