---
name: release-review
description: 평가·검토·승인이 연결된 불변 release의 적용과 복구를 검토한다.
---

# release-review

## 사용 시점

평가·검토·승인이 연결된 불변 release의 적용과 복구를 검토한다. 현재 역할의 허용 skill이고 고정된 release에 포함된 경우에만 적용한다.

## 입력

현재 AgentTask의 scope·base_revision·input_digest, 역할별 input_refs, 허가된 도구 목록을 읽는다. 이 skill은 권한을 발급하지 않는다. 불필요한 전체 대화·다른 workspace를 읽지 않는다.

## 절차

1. subject digest·components·parent·schema compatibility를 확인한다.
2. 독립 actual eval과 review refs, trusted promotion authority를 확인한다.
3. CAS baseline 이동 여부와 pinned run 영향을 검사한다.
4. 승인된 canary 범위·정지 기준·rollback plan을 확인한다.
5. 배포 결과와 영향을 보고하되 실제 pointer 변경은 broker에 맡긴다.

## 산출과 검증

`WorkerOutcome` 관련 산출물을 작성한다. 최종 워커 응답은 현재 AgentTask.output_schema_ref를 따르며, 커널이 proposal에서 최종 계약을 별도 생성한다. 실제 JSON 필드 이름은 로딩된 schema가 소유한다. 도구/runner evidence와 자기보고를 구분하고 실행하지 않은 검사를 passed로 쓰지 않는다.

## 중단·상향 검토

- 사람 승인 없는 자동 promotion을 하지 않는다.
- harness rollback을 사용자 source rollback으로 설명하지 않는다.
- stale evaluation 결과를 새 baseline에 재사용하지 않는다.

scope·revision·approval·근거가 맞지 않으면 해당 오류와 다음 허용 행동을 보고한다. 예산 끝을 성공으로 바꾸지 않는다.

## 필요한 경우에만 읽을 자료

[상세 체크리스트](references/checklist.md), [출력 형식 안내](assets/output.example.json)를 필요한 단계에서만 읽는다. 둘을 항상 system prompt에 합치지 않는다.
