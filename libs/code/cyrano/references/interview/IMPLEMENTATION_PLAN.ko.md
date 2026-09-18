# 구현 요청서와 작업 순서

## 작업자에게 전달할 지시

`DESIGN.ko.md`를 기준으로 모델 독립적인 인터뷰 커널을 구현한다. 이 문서는 구현 요청의 설계 입력이며 사용자 대신 운영 환경 변경을 승인하지 않는다. 먼저 작업 저장소의 실제 언어·도구·제약을 확인하고, 기존 계약과 충돌하는 부분을 구체적으로 기록한다. 예시 수치나 디렉터리 이름을 불변 요구사항으로 오해하지 않는다.

## 권장 파일 구조

```text
src/decision_interview/
  domain/       types, decisions, obligations, scenarios, authority
  kernel/       transitions, readiness, invalidation, budgets, reducer
  persistence/  transactions, event store, snapshots, idempotency
  agents/       tasks, result validation, bounded dispatch
  routing/      classification, action selection, duplicate suppression
  contracts/    compiler, canonicalization, export
  adapters/     cli, mcp, host events, capability broker
  evaluation/   replay, hidden-intent harness, metrics
```

패키지 이름과 구현 언어는 변경 가능하지만 커널을 호스트 프롬프트에 종속시키지 않는다.

## P0 — 상태·권한 핵심

산출물: 정형 도메인 모델, 사건 로그, transactional store, revision+digest CAS, idempotency, authority validator, 상태 전이 표와 타입화된 오류.

완료 기준: 모델이 직접 결정 확정·승인 생성·준비도 변경을 수행할 수 없다. 재시작 후 승인된 이벤트를 재생하면 같은 파생 상태를 얻는다. 동일 요청 재시도는 단일 이벤트만 만든다. 충돌한 새 payload는 명시적 오류다. 취소·일시정지·예산 소진이 완료로 바뀌지 않는다.

## P1 — 작동하는 최소 인터뷰

산출물: 실제 사용자 이벤트 ingestion, 단일 질문 진행자, 읽기 전용 코드 조사, 의도/관측/가설 분리, decision ID, 범위와 적용 의무, 후보 행동 라우터.

완료 기준: 명백히 이미 답한 내용은 다시 묻지 않는다. 코드로 확인할 사실을 무조건 사용자에게 넘기지 않는다. 질문이 없어도 초기 입력만으로 충분하면 다음 단계로 간다. 답변할 수 없는 질문에는 자료 조사·예시·보류·제한적 위임을 사용한다. 원문과 해석을 분리해서 보존한다.

## P2 — 검증 가능한 계약

산출물: 성공·실패 시나리오, Counterexample Critic, 고위험 계약의 Blind Handoff Reviewer, 준비도 검사, 계약 생성 및 승인 영수증.

완료 기준: 모든 필수 검토가 같은 계약 digest에 연결된다. 근거 없는 포괄적 비판으로 무한 차단하지 않는다. 제품의 관측 결과를 바꾸는 모호함은 다시 결정으로 열린다. 원문 대화를 보지 않은 검토자가 추가 가정을 명시한다. 최종 승인과 실행 승인이 분리된다.

## P3 — 변경·실패·위협 모델

산출물: 의존관계 기반 무효화, stale worker 격리, 새 반증의 재검토 큐, 근거 freshness, trusted-host attestation, 샌드박스 capability broker.

완료 기준: 요구 변경이 관련 승인만 무효화한다. 중요한 늦은 근거는 잃지 않는다. repo 문서의 악성 지시가 실행되지 않는다. MCP 연결 또는 prompt 문자열만으로 권한을 확대하지 못한다. 실제 호스트가 제공하지 않는 보안 경계를 제공한다고 주장하지 않는다.

## P4 — 비교 평가와 비용 개선

산출물: 같은 executor 기반 평가 하네스, 원본 프로젝트 단위 분리된 과제 집합, 모의 사용자와 실제 사용자 평가, 기능 제거 실험, 비용·지연·인간 부담 계측.

완료 기준: 자체 모호도 평균이 아니라 false-ready, 의도 위반, 후속 테스트, 사용자 부담을 보고한다. 실패와 중단을 표본에서 삭제하지 않는다. 같은 원본 과제의 반복은 독립 표본처럼 세지 않는다. 제품 기본값 비교와 모델/예산 통제 비교를 따로 보고한다.

## 계약의 의미 검증 — 스키마 외 필수 구현

1. 모든 참조 ID가 같은 세션에 존재하는지 검사한다.
2. worker input digest와 base revision이 현재 작업 snapshot과 일치하는지 확인한다.
3. evidence 존재와 실제 claim 지지 여부를 구분한다. 후자는 검토 대상이다.
4. 필수 finding에는 구체적 반례 또는 누락 의무가 있어야 한다.
5. 결정 권한은 user event 또는 범위 안의 사전 위임으로 추적한다.
6. approval 서명/호스트 신뢰/표시된 bundle digest를 모두 검증한다. JSON 통과만으로 승인하지 않는다.
7. 결정·범위·시나리오·정책 변경은 해당 bundle 승인을 무효화한다.
8. export는 초안/승인 상태를 정확히 표기하고 execution authorization을 만들지 않는다.

## 평가 결과 보고 형식

무엇을 구현했는지, 어떤 코드/스냅샷에서 어떤 명령을 실행했는지, 실패·스킵·미검증 항목이 무엇인지 구분한다. 의도적으로 시뮬레이션한 사용자·도구 응답을 실제 관측과 섞지 않는다. 준비도 사례 fixture가 있다는 이유로 구현 테스트가 통과했다고 쓰지 않는다.
