# Python Quality Harness 구현 계획

모든 WorkUnit 상태는 이 문서 전달 시 `PLANNED`다. 문서/계약 fixture의 검증 완료를 제품 구현
완료로 표시하지 않는다. 아래 순서와 테스트를 따라 구현한다. task 별 PR을 권장하지만 commit/push는
별도 사용자 요청이 있을 때만 한다.

## PY-W01 — 현황 조사 및 정책 ADR

의존성: 없음. 소유: architect.
수정: `docs/design/python-quality/`, `configs/quality/` 제안, 현재 workspace metadata.
실행: 실제 repository HEAD/dirty state 기록 → Python/lock/tooling roots 조사 → 기존 AGENTS/Skill
중복 조사 → 79/88와 mypy/Pyright 충돌 정리 → ADR-PY-001 승인 → 대상 repo/제품 자체 구분.
테스트: PY-T14/15/53의 계획. 산출물: 승인된 profile, toolchain candidate, 기존 실패 inventory.
완료: 원본 pyproject/lock을 무단 덮어쓰지 않고 정확한 migration diff와 PlanPermit이 존재한다.

## PY-W02 — 공용 계약과 reducer

의존성: W01. 소유: implementer + 별도 reviewer.
수정: `udh_contracts/quality.py`, `udh_quality/reducer.py`, JSON schemas, unit tests.
실행: reference models를 공용 계약 규약으로 이식 → extra-field/enum/digest/path validation →
required-check reducer → report/requirement binding → positive/negative fixtures.
테스트: PY-T26..31/35/36. 완료: malformed/누락/duplicate/forged verdict가 PASS를 만들지 않는다.
아직 trusted receipt가 구현되지 않았다면 schema PASS를 인증 PASS로 노출하지 않는다.

## PY-W03 — inventory 및 immutable snapshot

의존성: W02.
수정: discovery.py, snapshot.py, path helpers, backend capability contract.
실행: .py/.pyi/fixtures/config inventory → fixed exclusions → raw bytes manifest → write lease →
seal/read-only mount → original mutation/unsupported path handling.
테스트: PY-T13..21/32/37. 완료: HEAD 동일 dirty 변경 탐지, race/escape 검증, 증거 identity 재현.

## PY-W04 — policy resolver와 policy guard

의존성: W02/W03.
수정: policy.py, guard.py, suppression.py, config renderer.
실행: approved pyproject와 UDH policy 병합 → 실제 도구 config 렌더링 → protected diff →
tokenize/AST suppression 탐지 → narrow exception permit 조회.
테스트: PY-T03/14/22..25/51/54. 완료: 문자열 오탐 없이 신규 우회와 scope 축소 차단.
정규식으로 모든 테스트 의미를 판정했다는 문구를 문서/코드에서 제거한다.

## PY-W05 — process runner와 format/lint adapters

의존성: W03/W04.
수정: runner.py, adapters/base.py, black.py, ruff.py, toolchain probe.
실행: shell=False/absolute tool paths/env allowlist → stdout/stderr 동시 처리 → deadline/cleanup →
version-pinned parsers → inventory coverage → safe fix와 final check 분리.
테스트: PY-T01..06/12/17/29..34. 완료: 실제 고정 Black/Ruff 실행의 raw receipt와 parse fixture가 있다.

## PY-W06 — type/test adapters

의존성: W05.
수정: mypy.py, pyright.py, pytest.py, observer plugin, suite registry.
실행: UDH mypy strict first → 대상 repo Pyright adapter → roots/import environment → test collection
및 phase accounting → JUnit/raw/observer consistency → plugin/config protection.
테스트: PY-T07..11/13/30/42/43/54. 완료: no-tests/skip/xfail/collection error가 거짓 PASS가 되지 않는다.

## PY-W07 — baseline과 예외 저장

의존성: W04/W05/W06.
수정: baseline.py, store extensions, BaselinePermit/ExceptionRecord schemas.
실행: base snapshot 수집 → exact multiset fingerprint → unchanged files 제한 →
changed-file full clean → policy/toolchain mismatch invalidation → approved debt summary.
테스트: PY-T24/25/38..43. 완료: same count/different diagnostics 실패, 테스트 실패 baseline 금지.

## PY-W08 — evidence와 완료 transaction

의존성: W02..W07.
수정: evidence.py, service.py, udh_sqlite/quality_store.py, udh_kernel/quality_completion.py.
실행: trusted runner channel → report registration → CAS completion → idempotency →
crash recovery/outbox → local_advisory와 governed 구분.
테스트: PY-T18/19/26..29/34..37/46/51. 완료: 임의 JSON/옛 snapshot/다른 attempt로 COMPLETE 불가.

## PY-W09 — Skill, 계획 리뷰, repair loop

의존성: W08.
수정: `.agents/skills/python-engineering`, product Skill 원본, role prompts, repair.py,
기존 udh_workflow/InterviewOutcome bridge.
실행: AGENTS 짧게 merge → resolved Skill receipt → plan structure/review → finite repair →
code review → 완료 요청 → failure evidence linking.
테스트: PY-T44/45/46/49/50. 완료: 요청 이해→계획 검토→실행→검증→독립 리뷰가 실제 artifact로 연결.

## PY-W10 — dcode adapter 및 Hook

의존성: W08/W09.
수정: quality_bridge.py, reviewed extension entry, hook handler, runtime probes.
실행: 실제 설치 pin 확인 → experimental extension opt-in → register tools → session binding →
Stop status lookup → native timeout/상한/cancel behavior → protected launcher aggregate.
테스트: PY-T45..50. 완료: actual dcode live test receipt가 있어야 integration-supported 표시.
권한·credential이 없으면 BLOCKED_ACCESS로 남기고 fake tool transcript로 대체하지 않는다.

## PY-W11 — CI와 운영

의존성: W08/W10.
수정: approved workflow/runner distribution, branch protection setup record, runbook.
실행: CI candidate/trusted runner 분리 → locked sandbox env → aggregate check → artifacts →
required check enforcement 확인 → 정책 변경 PR 흐름 → rollback drill.
테스트: PY-T51..54/60. 완료: 실제 CI 실패가 merge를 차단하는 설정까지 검증해야 배포 완료.
권한이 없어 settings를 적용하지 못했으면 구현 완료와 운영 blocker를 별도 표시한다.

## PY-W12 — 관측·자기개선

의존성: W09/W10/W11.
수정: events/metrics, udh_improvement bridge, evaluation fixtures/holdout manifest, release policy.
실행: attempt 단위 지표 → 실패 family → proposal → A/B 구분 → paid budget default 0 →
실제 paired rerun → independent approval → release/canary/rollback.
테스트: PY-T55..60. 완료: runtime policy를 자동 약화할 수 없고 holdout/승인/rollback 증거가 있다.

## 작업 종료 산출물

각 WorkUnit은 변경 파일, 요구/acceptance 연결, 실행 명령·환경·exit code, 결과 artifact IDs,
미실행 사유, 남은 blocker, 다음 dependency를 보고한다. test 개수를 실제 실행 로그 없이 쓰지 않는다.
전체 완료는 W01..W12와 60개 인수 조건의 실행 범위/미실행 영역을 정직하게 표시해야 한다.
