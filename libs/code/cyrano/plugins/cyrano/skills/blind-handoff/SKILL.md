---
name: blind-handoff
description: 대화 없이 계약만 읽는 구현자가 추가 가정을 해야 하는 부분을 발견한다.
---

# blind-handoff

## 사용 시점

대화 없이 계약만 읽는 구현자가 추가 가정을 해야 하는 부분을 발견한다. 현재 역할의 허용 skill이고 고정된 release에 포함된 경우에만 적용한다.

## 입력

현재 AgentTask의 scope·base_revision·input_digest, 역할별 input_refs, 허가된 도구 목록을 읽는다. 이 skill은 권한을 발급하지 않는다. 불필요한 전체 대화·다른 workspace를 읽지 않는다.

## 절차

1. 입력에 이전 대화나 다른 reviewer 결론이 없는지 확인한다.
2. 각 요구에서 happy/error/concurrency/cancel 관측 결과를 재구성한다.
3. 추가로 가정해야 하는 조건과 그로 인해 달라지는 사용자 결과를 findings로 기록한다.
4. 동일 결과를 내는 내부 자료구조 차이는 위임된 선택으로 남긴다.
5. 검토 수행 결과를 제출하며 spec approval을 발급하지 않는다.

## 산출과 검증

`WorkerOutcome` 관련 산출물을 작성한다. 최종 워커 응답은 현재 AgentTask.output_schema_ref를 따르며, 커널이 proposal에서 최종 계약을 별도 생성한다. 실제 JSON 필드 이름은 로딩된 schema가 소유한다. 도구/runner evidence와 자기보고를 구분하고 실행하지 않은 검사를 passed로 쓰지 않는다.

## 중단·상향 검토

- 대화에 있었다는 Author 설명만으로 문서 누락을 통과시키지 않는다.
- mandatory review 실패는 통과가 아니다.
- 사용자 승인과 review complete를 분리한다.

scope·revision·approval·근거가 맞지 않으면 해당 오류와 다음 허용 행동을 보고한다. 예산 끝을 성공으로 바꾸지 않는다.

## 필요한 경우에만 읽을 자료

[상세 체크리스트](references/checklist.md), [출력 형식 안내](assets/output.example.json)를 필요한 단계에서만 읽는다. 둘을 항상 system prompt에 합치지 않는다.
