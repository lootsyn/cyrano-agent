# R4 상세 계약의 적용 범위

문서 유형: 목표 계약 설명. v1/v2 base 계약을 무단 migration하지 않는다. R4는 아직 구현할 서비스의 추가 detail DTO다. `MemoryRevisionDetail`, `MemoryApplicationDetail`, `PhysicalAttemptObservation`, `ImprovementEvidenceChain`을 서로 다른 API 이름으로 유지한다.

v1 `Scope{tenant,user,workspace}`와 detail `scope{tenant_id,user_id,workspace_id,session_id}` 사이에는 WP01의 명시 adapter가 필요하다. tenant→tenant_id, user→user_id, workspace→workspace_id를 같은 trusted identity로 매핑하고 session-only scope는 새 session ID 없이는 확장하지 않는다. `MemoryRecord.version`은 detail revision과 동일한 immutable revision을 가리킨다. mapping round-trip·unknown field·scope mismatch 테스트가 필요하다. active 승인/서명은 이전 이름의 artifact에서 자동 변환하지 않는다.

memory의 canonical rows는 기존 `memories`이며 r4 SQL의 `memory_revision_details`는 외래키로 연결한 추가 metadata다. 두 독립 active memory store를 만들지 않는다. events도 기존 원장이 기준이다. observer epoch를 기존 producer identity에 포함해 sequence 재시작 충돌을 막는다. R4 FTS는 version을 포함하며 기존 FTS를 active query path에서 대체할 때 snapshot 재구성과 삭제 검증을 수행한다.

Schema validation은 필드 검증에 한정한다. 유효 승인·서명·artifact 내용·수치 단위·실행 측정의 참 여부는 별도의 semantic validators/broker/evaluator에서 확인한다. 다음 run binding이 nullable인 promoted chain은 승격만 증명하며 3-4 전체 통과가 아니다. `semantic-rules.json`의 NEXT-RUN 검사가 별도로 필수다.
