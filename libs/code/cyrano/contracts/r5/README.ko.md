# R5 계약 · canonical 상태와 화면 projection 분리

기존 v1/v2 및 R4 canonical event 원장은 유지한다. 이 폴더의 MonitorViewEvent는 query service가 검증된 canonical events와 model_attempt_observations를 변환한 **읽기용 파생 형식**이다. `model.attempt_started`를 기존 원장 catalog에 무검증으로 추가하거나 외부 tool이 권위 있는 이벤트를 제출하게 하지 않는다.

## 변환 규칙

`model.started` canonical event 및 `model_attempt_observations`/`model_invocations` 결속을 확인한 경우에만 view의 `model.attempt_started`를 만든다. `attempt_id`는 physical_attempt_id, logical_request_id는 DB FK, is_retry는 attempt_no>1 또는 검증된 retry_of 관계에서 유도한다. native SDK의 내부 retry가 관측되지 않으면 합성 attempt를 만들어 count를 채우지 않고 missing_observers에 표시한다.

`memory.applied`는 memory_applications.status=applied와 checker/evidence 존재를 확인하여 application_id를 붙인다. `learning.proposed`/`release.promoted`는 해당 원장의 후보/release digest를 연결한다. 모든 view event는 source_event_ids와 projection_version을 가져야 한다. view event_id는 version+source-event-set+kind의 결정적 식별자다. 하나의 canonical event에서 여러 view 행을 만들 때 global seq 공유를 허용하는 복합 cursor가 필요하므로 기본 구현은 행을 하나로 합친다. 순수 MonitorProjection은 seq 소유권 1:1만 지원하며 다른 가정을 조용히 허용하지 않는다.

## snapshot와 cursor

인증된 scope에서 같은 read transaction의 summary·recent_events·high_watermark를 만든다. cursor는 request/scope/filter/projection/generation/retention epoch를 서버가 서명한 opaque token이다. recent_events는 마지막1000개 이하이고 summary는 전체 원장에서 계산한다. client가 최근행만 계산한 값을 전수 count로 표시하지 않는다. 변환 불가/실패 event는 명시적인 missing 상태다.

## 코드와 wire 책임

`entry-delta.schema.json`은 목표 wire 계약이며 구현된 순수 EntryDelta보다 조건·연결 필드가 많다. RF05는 명시적인 adapter/validator와 link operation을 구현해야 한다. schema만 추가하고 runtime에서 모르는 필드를 조용히 버리지 않는다. feature-state는 인벤토리 판정, 설치 receipt는 개발 설치 증거이며 product authorization이 아니다.

숫자 limits는 초기 운영 상한이다. hash·enum·schema 검사 뒤에도 scope/참조/상태/revision/권한/동시성 의미 검사가 필요하다. JSON Schema PASS는 원본 실행이나 OS 격리 보장이 아니다.
