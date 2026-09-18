---
name: cache-context
description: 정확성·scope를 유지하면서 고정 prefix와 동적 tail을 분리한다.
---

# cache-context

## 사용 시점

정확성·scope를 유지하면서 고정 prefix와 동적 tail을 분리한다. 현재 역할의 허용 skill이고 고정된 release에 포함된 경우에만 적용한다.

## 입력

현재 AgentTask의 scope·base_revision·input_digest, 역할별 input_refs, 허가된 도구 목록을 읽는다. 이 skill은 권한을 발급하지 않는다. 불필요한 전체 대화·다른 workspace를 읽지 않는다.

## 절차

1. 현재 role/release/tool inventory/skill catalogue epoch를 읽는다.
2. static block에 run ID·시간·남은 예산·기억 결과가 없는지 확인한다.
3. metadata→본문→references 순서로 필요한 skill만 읽는다.
4. 선택 근거와 context manifest를 기록하고 native wire 관측 범위를 구별한다.
5. cache-read 사용량이 없으면 unknown으로 남기고 실제 task 품질을 같이 평가한다.

## 산출과 검증

`ContextManifest` 관련 산출물을 작성한다. 최종 워커 응답은 현재 AgentTask.output_schema_ref를 따르며, 커널이 proposal에서 최종 계약을 별도 생성한다. 실제 JSON 필드 이름은 로딩된 schema가 소유한다. 도구/runner evidence와 자기보고를 구분하고 실행하지 않은 검사를 passed로 쓰지 않는다.

## 중단·상향 검토

- token 측정 없이 byte 길이를 hard token limit으로 취급하지 않는다.
- revoked memory를 cache 보존 때문에 유지하지 않는다.
- dummy warming이나 TTL keepalive를 임의 실행하지 않는다.

scope·revision·approval·근거가 맞지 않으면 해당 오류와 다음 허용 행동을 보고한다. 예산 끝을 성공으로 바꾸지 않는다.

## 필요한 경우에만 읽을 자료

[상세 체크리스트](references/checklist.md), [출력 형식 안내](assets/output.example.json)를 필요한 단계에서만 읽는다. 둘을 항상 system prompt에 합치지 않는다.
