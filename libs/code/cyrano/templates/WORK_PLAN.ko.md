# 개발 WorkPlan

문서 유형: 실행 기록 템플릿. 이 빈 양식은 승인이나 실행 완료 증거가 아니다.

## 요구와 범위

request/task/WP/RC ID, user requirement 원문·근거, 포함/제외 범위, 완료 acceptance IDs, source/base/runtime/schema/policy digest, 현재 실패 baseline을 채운다.

## 변경 계획

변경 대상 file/function, 작업 순서·의존성·담당, typed 입력/출력/오류, DB·권한·event 영향, 수정 전 검증, 정상·negative test file/symbol, native regressions, 예상 비용·시간 제한, rollback을 채운다.

## 독립 계획 리뷰

reviewer session/identity, reviewed plan digest, finding ID/severity, 각 finding disposition과 근거, 수정 후 plan digest, unresolved blockers, 재리뷰 verdict를 채운다.

## 승인·scope 변경

신뢰된 승인 출처와 승인 대상 digest/범위/유효기간을 기록한다. 승인 전 코드를 바꾸지 않는다. 파일·목표·권한·예산·시험 범위를 바꾸면 새 계획·리뷰·승인을 요구한다. 템플릿에 서명처럼 보이는 문자열을 넣어 실제 broker 승인을 대신하지 않는다.

## 결과

실제 수행 argv/cwd/exit/artifact, source postimage, acceptance별 status, 독립 코드 review, 알려진 제한, cleanup, 다음 작업을 채운다.
