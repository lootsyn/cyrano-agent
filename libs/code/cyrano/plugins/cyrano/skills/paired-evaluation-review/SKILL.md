---
name: paired-evaluation-review
description: 사전 등록된 실험과 실제 실행 증거의 공정성·누수·안전을 검토한다.
---

# paired-evaluation-review

## 사용 시점

사전 등록된 실험과 실제 실행 증거의 공정성·누수·안전을 검토한다. 현재 역할의 허용 skill이고 고정된 release에 포함된 경우에만 적용한다.

## 입력

현재 AgentTask의 scope·base_revision·input_digest, 역할별 input_refs, 허가된 도구 목록을 읽는다. 이 skill은 권한을 발급하지 않는다. 불필요한 전체 대화·다른 workspace를 읽지 않는다.

## 절차

1. baseline/candidate 입력 차이가 제안 diff와 일치하는지 검사한다.
2. family/time split·순서 randomization·pair 분모·누락 이유를 확인한다.
3. trusted execution receipts와 evaluator ownership을 검증하도록 요청한다.
4. safety hard failures를 먼저 보고하고 quality/cost intervals를 해석한다.
5. eligible_for_review와 promotion approval을 구별한다.

## 산출과 검증

`WorkerOutcome` 관련 산출물을 작성한다. 최종 워커 응답은 현재 AgentTask.output_schema_ref를 따르며, 커널이 proposal에서 최종 계약을 별도 생성한다. 실제 JSON 필드 이름은 로딩된 schema가 소유한다. 도구/runner evidence와 자기보고를 구분하고 실행하지 않은 검사를 passed로 쓰지 않는다.

## 중단·상향 검토

- replay 점수로 B 효과를 확정하지 않는다.
- 실험 뒤 성공 기준·분모를 유리하게 바꾸지 않는다.
- 같은 family 반복을 독립 표본으로 계산하지 않는다.

scope·revision·approval·근거가 맞지 않으면 해당 오류와 다음 허용 행동을 보고한다. 예산 끝을 성공으로 바꾸지 않는다.

## 필요한 경우에만 읽을 자료

[상세 체크리스트](references/checklist.md), [출력 형식 안내](assets/output.example.json)를 필요한 단계에서만 읽는다. 둘을 항상 system prompt에 합치지 않는다.
