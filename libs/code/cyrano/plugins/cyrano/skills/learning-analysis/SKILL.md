---
name: learning-analysis
description: 업무 episode에서 근거 있는 반복 원인과 반례를 찾고 개선 작업계획을 작성한다.
---

# learning-analysis

## 사용 시점

업무 episode에서 근거 있는 반복 원인과 반례를 찾고 개선 작업계획을 작성한다. 현재 역할의 허용 skill이고 고정된 release에 포함된 경우에만 적용한다.

## 입력

현재 AgentTask의 scope·base_revision·input_digest, 역할별 input_refs, 허가된 도구 목록을 읽는다. 이 skill은 권한을 발급하지 않는다. 불필요한 전체 대화·다른 workspace를 읽지 않는다.

## 절차

1. trusted observations와 model self-report를 분리한다.
2. TDD red·올바른 거부·사용자 취소·환경 장애를 성능 실패와 구별한다.
3. 원인 가설·대안 설명·scope·반증 가능한 효과를 작성한다.
4. 예상 이익과 총 평가 비용을 비교한 LearningWorkPlan을 제출한다.
5. 독립 review·실험 권한 전에는 paid 평가를 시작하지 않는다.

## 산출과 검증

`LearningWorkPlan` 관련 산출물을 작성한다. 최종 워커 응답은 현재 AgentTask.output_schema_ref를 따르며, 커널이 proposal에서 최종 계약을 별도 생성한다. 실제 JSON 필드 이름은 로딩된 schema가 소유한다. 도구/runner evidence와 자기보고를 구분하고 실행하지 않은 검사를 passed로 쓰지 않는다.

## 중단·상향 검토

- 단발 사건으로 범용 규칙을 확정하지 않는다.
- meta_depth1 학습 작업이 다시 자동 학습을 시작하지 않는다.
- 승인·검증·audit 제거를 개선 후보로 삼지 않는다.

scope·revision·approval·근거가 맞지 않으면 해당 오류와 다음 허용 행동을 보고한다. 예산 끝을 성공으로 바꾸지 않는다.

## 필요한 경우에만 읽을 자료

[상세 체크리스트](references/checklist.md), [출력 형식 안내](assets/output.example.json)를 필요한 단계에서만 읽는다. 둘을 항상 system prompt에 합치지 않는다.
