---
name: scoped-memory
description: 작업 단계에 맞는 검증된 기억을 선택하고 사용 근거를 남긴다.
---

# scoped-memory

## 사용 시점

작업 단계에 맞는 검증된 기억을 선택하고 사용 근거를 남긴다. 현재 역할의 허용 skill이고 고정된 release에 포함된 경우에만 적용한다.

## 입력

현재 AgentTask의 scope·base_revision·input_digest, 역할별 input_refs, 허가된 도구 목록을 읽는다. 이 skill은 권한을 발급하지 않는다. 불필요한 전체 대화·다른 workspace를 읽지 않는다.

## 절차

1. intake/plan/implement/verify 중 현재 phase를 확인한다.
2. tenant/user/workspace exact scope와 active 상태를 query에 지정한다.
3. dependency digest·expiry·supersedes·충돌을 검토한다.
4. 직접 관련된 기억만 budget 안에 주입하고 적용한 ID를 계획·검증에 연결한다.
5. 새 교훈은 후보로 제안하고 active record를 직접 수정하지 않는다.

## 산출과 검증

`WorkerOutcome` 관련 산출물을 작성한다. 최종 워커 응답은 현재 AgentTask.output_schema_ref를 따르며, 커널이 proposal에서 최종 계약을 별도 생성한다. 실제 JSON 필드 이름은 로딩된 schema가 소유한다. 도구/runner evidence와 자기보고를 구분하고 실행하지 않은 검사를 passed로 쓰지 않는다.

## 중단·상향 검토

- query hit와 applied/effective를 구분한다.
- stale fact·candidate는 authoritative advice가 아니다.
- 사용자 선호를 다른 tenant에 일반화하지 않는다.

scope·revision·approval·근거가 맞지 않으면 해당 오류와 다음 허용 행동을 보고한다. 예산 끝을 성공으로 바꾸지 않는다.

## 필요한 경우에만 읽을 자료

[상세 체크리스트](references/checklist.md), [출력 형식 안내](assets/output.example.json)를 필요한 단계에서만 읽는다. 둘을 항상 system prompt에 합치지 않는다.
