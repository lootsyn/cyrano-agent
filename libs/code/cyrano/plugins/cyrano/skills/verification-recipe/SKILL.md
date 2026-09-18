---
name: verification-recipe
description: 실제 산출물에서 정확성·사용자 acceptance·회귀를 확인한다.
---

# verification-recipe

## 사용 시점

실제 산출물에서 정확성·사용자 acceptance·회귀를 확인한다. 현재 역할의 허용 skill이고 고정된 release에 포함된 경우에만 적용한다.

## 입력

현재 AgentTask의 scope·base_revision·input_digest, 역할별 input_refs, 허가된 도구 목록을 읽는다. 이 skill은 권한을 발급하지 않는다. 불필요한 전체 대화·다른 workspace를 읽지 않는다.

## 절차

1. 검증 대상 snapshot과 recipe digest를 고정한다.
2. setup·명령 argv·환경·scratch side effect를 확인한다.
3. positive/negative/복구/권한 거부 조건을 실행한다.
4. 실행 정상 종료, 산출물 correctness, acceptance를 별도 판정한다.
5. missing/unknown 결과와 영향 scope를 보고하고 완료를 과장하지 않는다.

## 산출과 검증

`WorkerOutcome` 관련 산출물을 작성한다. 최종 워커 응답은 현재 AgentTask.output_schema_ref를 따르며, 커널이 proposal에서 최종 계약을 별도 생성한다. 실제 JSON 필드 이름은 로딩된 schema가 소유한다. 도구/runner evidence와 자기보고를 구분하고 실행하지 않은 검사를 passed로 쓰지 않는다.

## 중단·상향 검토

- replay 기록을 실제 실행 완료로 사용하지 않는다.
- merged artifact는 별도 통합 검증한다.
- 환경 오류로 불리한 task를 분모에서 제거하지 않는다.

scope·revision·approval·근거가 맞지 않으면 해당 오류와 다음 허용 행동을 보고한다. 예산 끝을 성공으로 바꾸지 않는다.

## 필요한 경우에만 읽을 자료

[상세 체크리스트](references/checklist.md), [출력 형식 안내](assets/output.example.json)를 필요한 단계에서만 읽는다. 둘을 항상 system prompt에 합치지 않는다.
