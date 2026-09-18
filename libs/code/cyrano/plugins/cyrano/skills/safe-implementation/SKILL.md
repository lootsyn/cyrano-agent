---
name: safe-implementation
description: 허가된 WorkUnit만 외부 작업 사본에서 구현하고 변경·검증 근거를 제출한다.
---

# safe-implementation

## 사용 시점

허가된 WorkUnit만 외부 작업 사본에서 구현하고 변경·검증 근거를 제출한다. 현재 역할의 허용 skill이고 고정된 release에 포함된 경우에만 적용한다.

## 입력

현재 AgentTask의 scope·base_revision·input_digest, 역할별 input_refs, 허가된 도구 목록을 읽는다. 이 skill은 권한을 발급하지 않는다. 불필요한 전체 대화·다른 workspace를 읽지 않는다.

## 절차

1. 승인된 WorkUnit·source snapshot·허용 write paths를 확인한다.
2. 실패/반례 테스트를 먼저 추가하거나 기존 baseline을 기록한다.
3. broker patch 요청과 허가된 실행 도구만 사용한다.
4. PEP8·타입·docstring·오류·취소·동시성을 검사한다.
5. 실제 변경 diff와 실행한 검증 receipt, 미실행 항목을 제출한다.

## 산출과 검증

`WorkerOutcome` 관련 산출물을 작성한다. 최종 워커 응답은 현재 AgentTask.output_schema_ref를 따르며, 커널이 proposal에서 최종 계약을 별도 생성한다. 실제 JSON 필드 이름은 로딩된 schema가 소유한다. 도구/runner evidence와 자기보고를 구분하고 실행하지 않은 검사를 passed로 쓰지 않는다.

## 중단·상향 검토

- 테스트 expected output을 바꾸어 실패를 숨기지 않는다.
- 원본 repo 반영·commit·push는 별도 허가다.
- 보호 경로나 운영 runtime 자기수정을 하지 않는다.

scope·revision·approval·근거가 맞지 않으면 해당 오류와 다음 허용 행동을 보고한다. 예산 끝을 성공으로 바꾸지 않는다.

## 필요한 경우에만 읽을 자료

[상세 체크리스트](references/checklist.md), [출력 형식 안내](assets/output.example.json)를 필요한 단계에서만 읽는다. 둘을 항상 system prompt에 합치지 않는다.
