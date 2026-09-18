# 승인·세션·운영 데이터 전환 명세

종류: 목표 reference / 소유 WP02·WP03·WP13·WP19. 현재 Store는 source foundation이며 이 문서는 데이터 migration 완료를 뜻하지 않는다.

## 세 가지 저장 범위

`../deepagents_code/cyrano/sqlite/store.py`의 현재 구현, `contracts/sql/target-schema.sql`의 목표 업무 테이블, `contracts/sql/governance-extension.sql`의 강화 binding/journal/liability/tombstone을 구분한다. 설치 시 세 파일을 임의 순서로 실행하지 않는다. schema version은 운영자가 확인한 현재 DB 값에서 인접 migration만 허용한다. 앞 버전의 schema generation을 자동 덮어쓰지 않는다.

| 첨부 도메인 | 기존 목표 저장소 | 이번 추가 규칙 |
|---|---|---|
| 세션·결정·의무·계획 | sessions/entities/관계 graph에 해당하는 소유 테이블 | business revision과 event_seq 분리; 외부로 같은 scope filter 적용 |
| 승인 receipt·permit | approvals/permits에 해당하는 소유 테이블 | governance_bindings에 v2 kind/version/subject 별도 기록; 원문 서명 변경 금지 |
| 실제 작업·변경·검증 | work unit/attempt/evidence artifact | operation_journal+effect_entries에 부분적용과 원본 pre/postimage 기록 |
| 예산·retry·provider usage | attempt/event/cost 집계 | budget_liabilities로 unknown 예약 유지; decimal을 float로 변환 금지 |
| memory·release·index | memory/release/index 소유 테이블 | 삭제 closure와 backup 복원 tombstone, session/task scope binding |
| learning·eval·promotion | candidate/experiment/evaluation/release | family split·실행 artifact·승인 pointer separate, 단일 terminal outbox identity |

왼쪽 이름은 원본 도메인이고 가운데 표는 개념 연결이다. 실제 테이블·column은 target-schema.sql의 선언을 사용한다. 정확한 table/column diff는 migration 코드를 만들 때 현재 DB introspection 결과와 함께 evidence에 저장한다. 존재하지 않는 컬럼 이름을 추정하여 운영 SQL을 실행하지 않는다.

## WP02 migration 절차

1. 쓰기 중지와 lease 만료/작업 미결 상태를 확인하고 read-only backup을 만든다. backup hash·DB integrity·원래 schema version을 기록한다.
2. 임시 DB에 backup 복원 후 인접 migration을 적용한다. 원본 이벤트 및 signed JSON byte열은 변환하지 않는다. 새 mapping/binding만 추가한다.
3. 모든 행에 tenant/user/workspace를 검증한다. 불명 scope는 global이 아닌 quarantine으로 보낸다. idempotency key의 의미가 바뀌면 이전 receipt를 새 성공으로 재사용하지 않는다.
4. row counts, foreign_key_check, graph dependency closure, active release subject, signature original bytes, deleted-data tombstones, outstanding operations/liabilities를 비교한다.
5. 새 DB로 read-only smoke를 돌린 후 별도 승인에서 writer를 전환한다. 전환 실패 시 원본 backup 경로로 복귀하되 전환 후 외부 작업이 생겼다면 먼저 reconcile한다.
6. rollback은 schema downgrade의 동의어가 아니다. 호환 읽기만 가능한 변경인지, forward repair가 필요한지 migration manifest에 명시한다. 데이터 파괴 변경은 자동 승격 대상이 아니다.

## Transaction과 fencing

명령은 key+scope+request_digest에 유일성을 둔다. 동일 key/동일 digest는 기존 결과, 동일 key/다른 digest는 IDEMPOTENCY_CONFLICT다. business state/event/outbox는 원자 저장하며 claim의 fence를 모든 후속 write에 검증한다. ttl 만료 뒤 old worker result는 새 리더 상태를 바꾸지 못한다. 외부 provider가 지원하지 않는 호출 중복 방지는 operation journal로 보완하되 exactly-once를 주장하지 않는다.

## 비밀·삭제

원문 payload보다 redacted artifact와 최소 metadata를 우선 저장한다. 삭제 closure는 active projection·FTS·선택적 vector·export·backup복원·replay world를 포함한다. 삭제된 evidence로 판정을 계속 유지할 수 있는지 별도 재검토하고 필요한 경우 release를 stale/revoked로 만든다. tombstone 자체에 삭제 본문을 복사하지 않는다.
