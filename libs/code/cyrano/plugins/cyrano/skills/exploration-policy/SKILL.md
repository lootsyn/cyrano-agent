---
name: exploration-policy
description: 공개된 탐색 관측만으로 다음 branch/action 후보를 결정한다.
---

# exploration-policy

## 사용 시점

공개된 탐색 관측만으로 다음 branch/action 후보를 결정한다. 현재 역할의 허용 skill이고 고정된 release에 포함된 경우에만 적용한다.

## 입력

현재 AgentTask의 scope·base_revision·input_digest, 역할별 input_refs, 허가된 도구 목록을 읽는다. 이 skill은 권한을 발급하지 않는다. 불필요한 전체 대화·다른 workspace를 읽지 않는다.

## 절차

1. frozen episode input과 합법 action 목록을 읽는다.
2. 이미 공개된 branch 결과·예산·dependency만 사용한다.
3. bounded IR로 우선순위·복구·batch·stop 규칙을 제안한다.
4. out_of_support를 실패로 추정하지 말고 실제 탐색 필요로 보고한다.
5. stop exploration 뒤에도 최종 검증·승인 의무를 남긴다.

## 산출과 검증

`WorkerOutcome` 관련 산출물을 작성한다. 최종 워커 응답은 현재 AgentTask.output_schema_ref를 따르며, 커널이 proposal에서 최종 계약을 별도 생성한다. 실제 JSON 필드 이름은 로딩된 schema가 소유한다. 도구/runner evidence와 자기보고를 구분하고 실행하지 않은 검사를 passed로 쓰지 않는다.

## 중단·상향 검토

- 미래 결과·전체 tape·sealed tests를 읽지 않는다.
- signature mismatch 결과를 유사 기록으로 대체하지 않는다.
- 부분 batch 결과를 조기 사용하지 않는다.

scope·revision·approval·근거가 맞지 않으면 해당 오류와 다음 허용 행동을 보고한다. 예산 끝을 성공으로 바꾸지 않는다.

## 필요한 경우에만 읽을 자료

[상세 체크리스트](references/checklist.md), [출력 형식 안내](assets/output.example.json)를 필요한 단계에서만 읽는다. 둘을 항상 system prompt에 합치지 않는다.
