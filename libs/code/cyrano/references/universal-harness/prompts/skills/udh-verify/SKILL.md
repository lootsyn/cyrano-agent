---
name: udh-verify
description: 현재 코드 상태의 Python 품질·테스트·수용 조건을 실제 검사하는 작업
---

# udh-verify

## 입력과 전제

현재 authenticated session/task, scope/policy/release digest, 필요한 approved artifact와 memory view를 읽는다. 부족한 권한은 도구를 우회하지 말고 요청/blocked로 처리한다.

## 실행 절차

현재 hash 확인 → formatter/lint/type/test/acceptance → 실행 증거 수집 → zero/skip/unknown 처리 → requirement 연결.

## 산출물

VerificationResult/quality report. 관련 요구사항 ID: PY-01. 정확한 schema는 UDH 계약 문서를 따른다. source 변경과 실행은 Broker만 수행하며 이 Skill은 권한을 부여하지 않는다.

## 실패·변경 처리

stale input, unexpected file change, required reviewer 실패, 예산 소진, 보안/감사 장애는 명시적 상태로 반환한다. 미실행 테스트·모델 자기평가를 실제 완료 증거로 보고하지 않는다. 활성 skill/memory를 직접 수정하지 않는다.
