---
name: udh-evaluate
description: 하네스 변경의 효과·회귀·보안을 통제 실험으로 평가
---

# udh-evaluate

## 입력과 전제

현재 authenticated session/task, scope/policy/release digest, 필요한 approved artifact와 memory view를 읽는다. 부족한 권한은 도구를 우회하지 말고 요청/blocked로 처리한다.

## 실행 절차

baseline/split/criteria 고정 → 독립 반복 → hard gate → 효과/불확실성 → review → 승인된 promotion/canary/rollback.

## 산출물

EvaluationReport/release evidence. 관련 요구사항 ID: EVAL-01. 정확한 schema는 UDH 계약 문서를 따른다. source 변경과 실행은 Broker만 수행하며 이 Skill은 권한을 부여하지 않는다.

## 실패·변경 처리

stale input, unexpected file change, required reviewer 실패, 예산 소진, 보안/감사 장애는 명시적 상태로 반환한다. 미실행 테스트·모델 자기평가를 실제 완료 증거로 보고하지 않는다. 활성 skill/memory를 직접 수정하지 않는다.
