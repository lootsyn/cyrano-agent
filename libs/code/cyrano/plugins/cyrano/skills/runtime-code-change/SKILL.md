---
name: runtime-code-change
description: 하네스/skill 실행 코드를 별도 개발 작업으로 수정·검증·패키징한다.
---

# runtime-code-change

## 사용 시점

하네스/skill 실행 코드를 별도 개발 작업으로 수정·검증·패키징한다. 현재 역할의 허용 skill이고 고정된 release에 포함된 경우에만 적용한다.

## 입력

현재 AgentTask의 scope·base_revision·input_digest, 역할별 input_refs, 허가된 도구 목록을 읽는다. 이 skill은 권한을 발급하지 않는다. 불필요한 전체 대화·다른 workspace를 읽지 않는다.

## 절차

1. 코드 lane 승인과 baseline CYRANO source snapshot을 확인한다.
2. 재현 테스트·계획 review를 거친 최소 변경을 작성한다.
3. dependency/schema 변경과 보안 영향을 분류한다.
4. 정적 검사·clean wheel·실제 dcode 통합·복구 실험을 수행한다.
5. 사람 code review와 새 runtime 승인 후 재시작 단위 배포를 요청한다.

## 산출과 검증

`WorkerOutcome` 관련 산출물을 작성한다. 최종 워커 응답은 현재 AgentTask.output_schema_ref를 따르며, 커널이 proposal에서 최종 계약을 별도 생성한다. 실제 JSON 필드 이름은 로딩된 schema가 소유한다. 도구/runner evidence와 자기보고를 구분하고 실행하지 않은 검사를 passed로 쓰지 않는다.

## 중단·상향 검토

- 현재 interpreter나 extension.py를 직접 덮어쓰지 않는다.
- DB forward migration 뒤 무조건 old code로 rollback하지 않는다.
- 보호된 권한 로직 변경을 단순 성능 후보로 배포하지 않는다.

scope·revision·approval·근거가 맞지 않으면 해당 오류와 다음 허용 행동을 보고한다. 예산 끝을 성공으로 바꾸지 않는다.

## 필요한 경우에만 읽을 자료

[상세 체크리스트](references/checklist.md), [출력 형식 안내](assets/output.example.json)를 필요한 단계에서만 읽는다. 둘을 항상 system prompt에 합치지 않는다.
