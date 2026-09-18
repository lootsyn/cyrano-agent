# Cyrano Agent · 문서 유형별 전체 목차

생성 문서. 직접 편집하지 않는다. 작은 시작점은 [NAVIGATION](NAVIGATION.ko.md)이다.
개발 agent는 전체 목차 본문을 매번 prompt에 넣지 않고 task router를 사용한다.

## 상세 설계(구현 목표) · 21개

- [적응형 Memory·Skill 개선 상세 설계](design/ADAPTIVE_MEMORY_AND_SKILL_EVOLUTION.ko.md) — `docs/design/ADAPTIVE_MEMORY_AND_SKILL_EVOLUTION.ko.md`
- [Code Intelligence·문서 검색·프로젝트 설치 상세 설계](design/CODE_INTELLIGENCE_AND_TOOL_ISOLATION.ko.md) — `docs/design/CODE_INTELLIGENCE_AND_TOOL_ISOLATION.ko.md`
- [Cyrano Agent · dcode 기반 코드와 복사 경계](design/DCODE_INTEGRATION.ko.md) — `docs/design/DCODE_INTEGRATION.ko.md`
- [문서 소유권·자동 등록·작업별 읽기](design/DOCUMENT_GOVERNANCE.ko.md) — `docs/design/DOCUMENT_GOVERNANCE.ko.md`
- [평가 3-1·3-2 · 장기 Memory 저장·선택·실제 적용 상세 설계](design/MEMORY_LIFECYCLE.ko.md) — `docs/design/MEMORY_LIFECYCLE.ko.md`
- [dcode 내부 Cyrano Monitor · 메뉴·화면·스트림 설계](design/NATIVE_MONITOR_TUI.ko.md) — `docs/design/NATIVE_MONITOR_TUI.ko.md`
- [평가 4-1–4-4 · 실행 원장·호출 계측·지표·Trace 조회 상세 설계](design/OBSERVABILITY_PIPELINE.ko.md) — `docs/design/OBSERVABILITY_PIPELINE.ko.md`
- [제품 완성도·배포·안전한 운영에 필요한 보완](design/RELEASE_ASSETS_AND_OPERATIONAL_COMPLETENESS.ko.md) — `docs/design/RELEASE_ASSETS_AND_OPERATIONAL_COMPLETENESS.ko.md`
- [기능 책임과 개발용·제품용 도입 결정](design/RESPONSIBILITY_AND_ADOPTION.ko.md) — `docs/design/RESPONSIBILITY_AND_ADOPTION.ko.md`
- [평가 3-3·3-4 · 자기개선 제안·실제 평가·다음 작업 반영](design/SELF_IMPROVEMENT_LIFECYCLE.ko.md) — `docs/design/SELF_IMPROVEMENT_LIFECYCLE.ko.md`
- [캐시 친화적 Context·Skill·역할 설정](design/architecture/2026-09-16-cache-context.ko.md) — `docs/design/architecture/2026-09-16-cache-context.ko.md`
- [데이터·API·Schema·Migration 계약](design/architecture/2026-09-16-data-api.ko.md) — `docs/design/architecture/2026-09-16-data-api.ko.md`
- [dcode source-native 통합과 사용자 평가 기준](design/architecture/2026-09-16-native-dcode-assessment.ko.md) — `docs/design/architecture/2026-09-16-native-dcode-assessment.ko.md`
- [dcode 연결·승인·격리·복구](design/architecture/2026-09-16-runtime-security.ko.md) — `docs/design/architecture/2026-09-16-runtime-security.ko.md`
- [CYRANO 전체 시스템과 소유권](design/architecture/2026-09-16-system-design.ko.md) — `docs/design/architecture/2026-09-16-system-design.ko.md`
- [Universal Harness 통합 상세 설계](design/architecture/2026-09-16-universal-harness-integration.ko.md) — `docs/design/architecture/2026-09-16-universal-harness-integration.ko.md`
- [경로 A: 지원 범위가 명시된 탐색 정책 개선](design/features/2026-09-16-dream-path-a.ko.md) — `docs/design/features/2026-09-16-dream-path-a.ko.md`
- [인터뷰에서 실행 가능한 계약까지](design/features/2026-09-16-interview-workflow.ko.md) — `docs/design/features/2026-09-16-interview-workflow.ko.md`
- [경로 B: 지식·절차·코드 개선 전체 구현](design/features/2026-09-16-path-b-improvement.ko.md) — `docs/design/features/2026-09-16-path-b-improvement.ko.md`
- [계획·독립 리뷰·사람의 결정·실행 통제](design/features/2026-09-16-plan-memory-execution.ko.md) — `docs/design/features/2026-09-16-plan-memory-execution.ko.md`
- [실제 개선 평가·관측·출시 판정](design/testing/2026-09-16-evaluation-observability.ko.md) — `docs/design/testing/2026-09-16-evaluation-observability.ko.md`

## 개발계획·작업 명세 · 67개

- [WP00: 실제 runtime·개발 도구 호환성 고정](../.agents/work/WP00.ko.md) — `.agents/work/WP00.ko.md`
- [WP01: 데이터 계약·digest·semantic validation](../.agents/work/WP01.ko.md) — `.agents/work/WP01.ko.md`
- [WP02: 원장·scope ACL·outbox·migration](../.agents/work/WP02.ko.md) — `.agents/work/WP02.ko.md`
- [WP03: 신뢰된 승인·Action Broker·sandbox](../.agents/work/WP03.ko.md) — `.agents/work/WP03.ko.md`
- [WP04: plugin 구성·lifecycle·역순 정리](../.agents/work/WP04.ko.md) — `.agents/work/WP04.ko.md`
- [WP05: context·skill catalog·native binding](../.agents/work/WP05.ko.md) — `.agents/work/WP05.ko.md`
- [WP06: dcode extension와 actual attempt port](../.agents/work/WP06.ko.md) — `.agents/work/WP06.ko.md`
- [WP07: 인터뷰 결정·의무·준비도 kernel](../.agents/work/WP07.ko.md) — `.agents/work/WP07.ko.md`
- [WP08: 인터뷰 역할·blind handoff·export](../.agents/work/WP08.ko.md) — `.agents/work/WP08.ko.md`
- [WP09: 계획·review·WorkUnit dispatcher](../.agents/work/WP09.ko.md) — `.agents/work/WP09.ko.md`
- [WP10: 실제 구현·검증·patch settle](../.agents/work/WP10.ko.md) — `.agents/work/WP10.ko.md`
- [WP11: 범위화 Memory 저장·조회·무효화](../.agents/work/WP11.ko.md) — `.agents/work/WP11.ko.md`
- [WP12: Skill registry·검증·release 투영](../.agents/work/WP12.ko.md) — `.agents/work/WP12.ko.md`
- [WP13: 전수 이벤트·대시보드·비용관측](../.agents/work/WP13.ko.md) — `.agents/work/WP13.ko.md`
- [WP14: Episode·world·replay 정합성](../.agents/work/WP14.ko.md) — `.agents/work/WP14.ko.md`
- [WP15: 경로 A bounded policy 학습](../.agents/work/WP15.ko.md) — `.agents/work/WP15.ko.md`
- [WP16: 경로 B 분석·학습계획·impact](../.agents/work/WP16.ko.md) — `.agents/work/WP16.ko.md`
- [WP17: 경로 B Memory·Skill 실제 평가](../.agents/work/WP17.ko.md) — `.agents/work/WP17.ko.md`
- [WP18: 경로 B 인터뷰·계획·context·recipe](../.agents/work/WP18.ko.md) — `.agents/work/WP18.ko.md`
- [WP19: 경로 B 코드·wheel·migration 제안](../.agents/work/WP19.ko.md) — `.agents/work/WP19.ko.md`
- [WP20: paired·sealed 평가·분석·budget](../.agents/work/WP20.ko.md) — `.agents/work/WP20.ko.md`
- [WP21: release·CAS·canary·rollback](../.agents/work/WP21.ko.md) — `.agents/work/WP21.ko.md`
- [WP22: packaging·품질·격리·복구 출시 gate](../.agents/work/WP22.ko.md) — `.agents/work/WP22.ko.md`
- [WP23: 실제 효과 검증과 승인된 초기 운영](../.agents/work/WP23.ko.md) — `.agents/work/WP23.ko.md`
- [평가 기준 기반 R4 보완 점검](development/ASSESSMENT_GAP_REVIEW.ko.md) — `docs/development/ASSESSMENT_GAP_REVIEW.ko.md`
- [개발계획: 선행 관계·담당·산출물](development/MASTER_DEVELOPMENT_PLAN.ko.md) — `docs/development/MASTER_DEVELOPMENT_PLAN.ko.md`
- [평가 3·4 보완 개발계획](development/MEMORY_OBSERVABILITY_PLAN.ko.md) — `docs/development/MEMORY_OBSERVABILITY_PLAN.ko.md`
- [Cyrano Agent · 통합 개발계획](development/R5_MASTER_PLAN.ko.md) — `docs/development/R5_MASTER_PLAN.ko.md`
- [현재 설계 정합성 및 개발 시작 판정](development/R5_REVIEW.ko.md) — `docs/development/R5_REVIEW.ko.md`
- [개발·테스트 실행계획 — 하위 구현 모델용](development/TEST_DEVELOPMENT_PLAN.ko.md) — `docs/development/TEST_DEVELOPMENT_PLAN.ko.md`
- [RC00 · dcode 복사·native import·wheel 검증](development/refinements/RC00.ko.md) — `docs/development/refinements/RC00.ko.md`
- [RC01 · 문서 라우팅·품질·계획 시작 규칙](development/refinements/RC01.ko.md) — `docs/development/refinements/RC01.ko.md`
- [RC30 · Memory durable 저장·revision·scope](development/refinements/RC30.ko.md) — `docs/development/refinements/RC30.ko.md`
- [RC31 · Recall·native prompt binding·캐시 epoch](development/refinements/RC31.ko.md) — `docs/development/refinements/RC31.ko.md`
- [RC32 · Memory 적용 증명·정정·삭제](development/refinements/RC32.ko.md) — `docs/development/refinements/RC32.ko.md`
- [RC33 · Episode→가설→학습계획→후보](development/refinements/RC33.ko.md) — `docs/development/refinements/RC33.ko.md`
- [RC34 · 실제 paired·회귀·sealed 평가](development/refinements/RC34.ko.md) — `docs/development/refinements/RC34.ko.md`
- [RC35 · 승격·next-run binding·revoke](development/refinements/RC35.ko.md) — `docs/development/refinements/RC35.ko.md`
- [RC36 · 경로 B 코드·resource·migration](development/refinements/RC36.ko.md) — `docs/development/refinements/RC36.ko.md`
- [RC40 · 요청 timeline·transactional event/outbox](development/refinements/RC40.ko.md) — `docs/development/refinements/RC40.ko.md`
- [RC41 · native 호출 coverage·지표 정확성](development/refinements/RC41.ko.md) — `docs/development/refinements/RC41.ko.md`
- [RC42 · Trace 조회·원인·privacy·권한](development/refinements/RC42.ko.md) — `docs/development/refinements/RC42.ko.md`
- [RC43 · native E2E·부하·40점 증거 패키지](development/refinements/RC43.ko.md) — `docs/development/refinements/RC43.ko.md`
- [RF00 · 책임·권한·도구 inventory 정합성](development/refinements/RF00.ko.md) — `docs/development/refinements/RF00.ko.md`
- [RF01 · 프로젝트 로컬 도구 설치·lock·probe](development/refinements/RF01.ko.md) — `docs/development/refinements/RF01.ko.md`
- [RF02 · 읽기 전용 LSP lifecycle·snapshot gateway](development/refinements/RF02.ko.md) — `docs/development/refinements/RF02.ko.md`
- [RF03 · Graphify·SCIP·QMD 승인 corpus/index](development/refinements/RF03.ko.md) — `docs/development/refinements/RF03.ko.md`
- [RF04 · bounded core·episodic recall·실제 적용](development/refinements/RF04.ko.md) — `docs/development/refinements/RF04.ko.md`
- [RF05 · typed skill delta·consolidation queue](development/refinements/RF05.ko.md) — `docs/development/refinements/RF05.ko.md`
- [RF06 · memory utility·ablation·next-run 효과](development/refinements/RF06.ko.md) — `docs/development/refinements/RF06.ko.md`
- [RF07 · native /cyrano 진입·인증 query](development/refinements/RF07.ko.md) — `docs/development/refinements/RF07.ko.md`
- [RF08 · Textual 화면·통계·안전 렌더](development/refinements/RF08.ko.md) — `docs/development/refinements/RF08.ko.md`
- [RF09 · Pilot·native CLI 통합·관측 증거](development/refinements/RF09.ko.md) — `docs/development/refinements/RF09.ko.md`
- [RF10 · 배포 asset·SBOM·upgrade·복구](development/refinements/RF10.ko.md) — `docs/development/refinements/RF10.ko.md`
- [RF11 · 전체 수용·40점 evidence·최종 handoff](development/refinements/RF11.ko.md) — `docs/development/refinements/RF11.ko.md`
- [TS00 · native 배치·버전·평가 대상 고정](development/test-work/TS00.ko.md) — `docs/development/test-work/TS00.ko.md`
- [TS01 · 평가 계약·신뢰된 증거·점수 판정](development/test-work/TS01.ko.md) — `docs/development/test-work/TS01.ko.md`
- [TS02 · Python 스타일·명명·import 실행](development/test-work/TS02.ko.md) — `docs/development/test-work/TS02.ko.md`
- [TS03 · Docstring·주석의 내용 검토](development/test-work/TS03.ko.md) — `docs/development/test-work/TS03.ko.md`
- [TS04 · 요구사항·계획·AI 리뷰](development/test-work/TS04.ko.md) — `docs/development/test-work/TS04.ko.md`
- [TS05 · 승인 전 수정 차단·재검토 강제](development/test-work/TS05.ko.md) — `docs/development/test-work/TS05.ko.md`
- [TS06 · 세션 간 Memory 유지·실제 적용](development/test-work/TS06.ko.md) — `docs/development/test-work/TS06.ko.md`
- [TS07 · 실패 분석·개선 후보 생성](development/test-work/TS07.ko.md) — `docs/development/test-work/TS07.ko.md`
- [TS08 · 개선 전후·회귀·다음 작업 적용](development/test-work/TS08.ko.md) — `docs/development/test-work/TS08.ko.md`
- [TS09 · 전 과정·LLM 도구 기억 학습 계측](development/test-work/TS09.ko.md) — `docs/development/test-work/TS09.ko.md`
- [TS10 · Trace 조회·실패 원인·접근권한](development/test-work/TS10.ko.md) — `docs/development/test-work/TS10.ko.md`
- [TS11 · 실제 통합·CI·점수·출시 evidence](development/test-work/TS11.ko.md) — `docs/development/test-work/TS11.ko.md`

## 실행·준비·복구 절차 · 12개

- [Cyrano Agent 개발 준비·실행 안내](execution/DEVELOPER_GUIDE.ko.md) — `docs/execution/DEVELOPER_GUIDE.ko.md`
- [통합 개발 실행계획](execution/INTEGRATED_WORK_DETAILS.ko.md) — `docs/execution/INTEGRATED_WORK_DETAILS.ko.md`
- [실행계획: 첫 부팅부터 실제 운영까지](execution/MASTER_EXECUTION_PLAN.ko.md) — `docs/execution/MASTER_EXECUTION_PLAN.ko.md`
- [Memory·자기개선·모니터링 개발 실행 절차](execution/MEMORY_OBSERVABILITY_RUNBOOK.ko.md) — `docs/execution/MEMORY_OBSERVABILITY_RUNBOOK.ko.md`
- [Cyrano Agent · 개발 수행 가이드](execution/R5_EXECUTION_GUIDE.ko.md) — `docs/execution/R5_EXECUTION_GUIDE.ko.md`
- [R3 실제 실행·인수 Runbook](execution/TEST_RUNBOOK.ko.md) — `docs/execution/TEST_RUNBOOK.ko.md`
- [통합 개발 실행 안내](execution/runbooks/development-execution.ko.md) — `docs/execution/runbooks/development-execution.ko.md`
- [A/B 실제 개선 평가](execution/runbooks/effectiveness-study.ko.md) — `docs/execution/runbooks/effectiveness-study.ko.md`
- [검증된 dcode 운영 시작](execution/runbooks/governed-launch.ko.md) — `docs/execution/runbooks/governed-launch.ko.md`
- [승인·비밀·평가 오염 사건 대응](execution/runbooks/incident.ko.md) — `docs/execution/runbooks/incident.ko.md`
- [release rollback과 영향 작업 재검토](execution/runbooks/rollback.ko.md) — `docs/execution/runbooks/rollback.ko.md`
- [경로 B runtime 코드 배포](execution/runbooks/runtime-upgrade.ko.md) — `docs/execution/runbooks/runtime-upgrade.ko.md`

## 테스트 전략·사례 · 32개

- [증거 수집·채점·변조 방지 계약](testing/EVIDENCE_AND_SCORING.ko.md) — `docs/testing/EVIDENCE_AND_SCORING.ko.md`
- [R4 추가 검증·수용 프로토콜](testing/R4_ACCEPTANCE_PROTOCOL.ko.md) — `docs/testing/R4_ACCEPTANCE_PROTOCOL.ko.md`
- [R5 실행 증거의 수준](testing/R5_VALIDATION_LEVELS.ko.md) — `docs/testing/R5_VALIDATION_LEVELS.ko.md`
- [프로젝트 평가 기준 기반 테스트 전략 — R3](testing/STRATEGY.ko.md) — `docs/testing/STRATEGY.ko.md`
- [1-1 · 들여쓰기·공백·줄바꿈 등 PEP8 코드 스타일](testing/cases/1-1.ko.md) — `docs/testing/cases/1-1.ko.md`
- [1-2 · 변수·함수·클래스 명명과 import 정리](testing/cases/1-2.ko.md) — `docs/testing/cases/1-2.ko.md`
- [1-3 · 주요 함수 docstring·입출력·필요한 주석](testing/cases/1-3.ko.md) — `docs/testing/cases/1-3.ko.md`
- [2-1 · 개발 전 요구사항·범위·완료 조건](testing/cases/2-1.ko.md) — `docs/testing/cases/2-1.ko.md`
- [2-2 · 수정 대상·작업 순서·테스트 계획](testing/cases/2-2.ko.md) — `docs/testing/cases/2-2.ko.md`
- [2-3 · AI 계획 리뷰·의견 반영](testing/cases/2-3.ko.md) — `docs/testing/cases/2-3.ko.md`
- [2-4 · 계획 승인 전 변경 금지·범위 변경 재검토](testing/cases/2-4.ko.md) — `docs/testing/cases/2-4.ko.md`
- [3-1 · Memory 저장·세션 종료 후 유지](testing/cases/3-1.ko.md) — `docs/testing/cases/3-1.ko.md`
- [3-2 · 새 작업에서 Memory 검색·실제 활용](testing/cases/3-2.ko.md) — `docs/testing/cases/3-2.ko.md`
- [3-3 · 실패·평가에 근거한 Agent 개선안 생성](testing/cases/3-3.ko.md) — `docs/testing/cases/3-3.ko.md`
- [3-4 · 개선 전후·회귀 검증 후 다음 작업 반영](testing/cases/3-4.ko.md) — `docs/testing/cases/3-4.ko.md`
- [4-1 · 요청별 전체 실행 흐름 기록](testing/cases/4-1.ko.md) — `docs/testing/cases/4-1.ko.md`
- [4-2 · LLM·도구·Memory·개선 결과와 오류 기록](testing/cases/4-2.ko.md) — `docs/testing/cases/4-2.ko.md`
- [4-3 · 시간·호출·재시도 주요 지표](testing/cases/4-3.ko.md) — `docs/testing/cases/4-3.ko.md`
- [4-4 · 작업별 Log·Trace 조회와 원인 확인](testing/cases/4-4.ko.md) — `docs/testing/cases/4-4.ko.md`
- [RF00 수용 테스트 상세](testing/r5/RF00.ko.md) — `docs/testing/r5/RF00.ko.md`
- [RF01 수용 테스트 상세](testing/r5/RF01.ko.md) — `docs/testing/r5/RF01.ko.md`
- [RF02 수용 테스트 상세](testing/r5/RF02.ko.md) — `docs/testing/r5/RF02.ko.md`
- [RF03 수용 테스트 상세](testing/r5/RF03.ko.md) — `docs/testing/r5/RF03.ko.md`
- [RF04 수용 테스트 상세](testing/r5/RF04.ko.md) — `docs/testing/r5/RF04.ko.md`
- [RF05 수용 테스트 상세](testing/r5/RF05.ko.md) — `docs/testing/r5/RF05.ko.md`
- [RF06 수용 테스트 상세](testing/r5/RF06.ko.md) — `docs/testing/r5/RF06.ko.md`
- [RF07 수용 테스트 상세](testing/r5/RF07.ko.md) — `docs/testing/r5/RF07.ko.md`
- [RF08 수용 테스트 상세](testing/r5/RF08.ko.md) — `docs/testing/r5/RF08.ko.md`
- [RF09 수용 테스트 상세](testing/r5/RF09.ko.md) — `docs/testing/r5/RF09.ko.md`
- [RF10 수용 테스트 상세](testing/r5/RF10.ko.md) — `docs/testing/r5/RF10.ko.md`
- [RF11 수용 테스트 상세](testing/r5/RF11.ko.md) — `docs/testing/r5/RF11.ko.md`
- [테스트 위치](../tests/README.md) — `tests/README.md`

## 개발 에이전트 지침 · 18개

- [개발 역할: architect](../.agents/roles/architect.md) — `.agents/roles/architect.md`
- [개발 역할: implementer](../.agents/roles/implementer.md) — `.agents/roles/implementer.md`
- [개발 역할: release-reviewer](../.agents/roles/release-reviewer.md) — `.agents/roles/release-reviewer.md`
- [독립 검토자](../.agents/roles/reviewer.md) — `.agents/roles/reviewer.md`
- [개발 역할: security-reviewer](../.agents/roles/security-reviewer.md) — `.agents/roles/security-reviewer.md`
- [평가 근거를 남기는 개발](../.agents/skills/cyrano-assessed-development/SKILL.md) — `.agents/skills/cyrano-assessed-development/SKILL.md`
- [cyrano-context-discipline](../.agents/skills/cyrano-context-discipline/SKILL.md) — `.agents/skills/cyrano-context-discipline/SKILL.md`
- [cyrano-contract-change](../.agents/skills/cyrano-contract-change/SKILL.md) — `.agents/skills/cyrano-contract-change/SKILL.md`
- [cyrano-dcode-probe](../.agents/skills/cyrano-dcode-probe/SKILL.md) — `.agents/skills/cyrano-dcode-probe/SKILL.md`
- [Cyrano 개발 workflow](../.agents/skills/cyrano-development/SKILL.md) — `.agents/skills/cyrano-development/SKILL.md`
- [cyrano-evidence-review](../.agents/skills/cyrano-evidence-review/SKILL.md) — `.agents/skills/cyrano-evidence-review/SKILL.md`
- [현재 문서 동기화](../.agents/skills/cyrano-note-docs/SKILL.md) — `.agents/skills/cyrano-note-docs/SKILL.md`
- [cyrano-path-b-change](../.agents/skills/cyrano-path-b-change/SKILL.md) — `.agents/skills/cyrano-path-b-change/SKILL.md`
- [cyrano-release-check](../.agents/skills/cyrano-release-check/SKILL.md) — `.agents/skills/cyrano-release-check/SKILL.md`
- [cyrano-work-cycle](../.agents/skills/cyrano-work-cycle/SKILL.md) — `.agents/skills/cyrano-work-cycle/SKILL.md`
- [Cyrano Agent 개발 지침](../AGENTS.md) — `AGENTS.md`
- [Cyrano 문서 작성 지침](AGENTS.md) — `docs/AGENTS.md`
- [Native source migration](../packages/AGENTS.md) — `packages/AGENTS.md`

## 의사결정 기록 · 1개

- [설계 의사결정의 기록 위치](../.agents/notes/README.md) — `.agents/notes/README.md`

## 현재 코드 API 참고 · 15개

- [cli: 현재 public source reference](subsystems/cli.md) — `docs/subsystems/cli.md`
- [compiler: 현재 public source reference](subsystems/compiler.md) — `docs/subsystems/compiler.md`
- [contracts: 현재 public source reference](subsystems/contracts.md) — `docs/subsystems/contracts.md`
- [dcode: 현재 public source reference](subsystems/dcode.md) — `docs/subsystems/dcode.md`
- [evaluation: 현재 public source reference](subsystems/evaluation.md) — `docs/subsystems/evaluation.md`
- [events: 현재 public source reference](subsystems/events.md) — `docs/subsystems/events.md`
- [세션 전이 guard 구현 명세](subsystems/governance-guards.ko.md) — `docs/subsystems/governance-guards.ko.md`
- [승인·세션·운영 데이터 전환 명세](subsystems/governance-storage.ko.md) — `docs/subsystems/governance-storage.ko.md`
- [improvement: 현재 public source reference](subsystems/improvement.md) — `docs/subsystems/improvement.md`
- [interview: 현재 public source reference](subsystems/interview.md) — `docs/subsystems/interview.md`
- [kernel: 현재 public source reference](subsystems/kernel.md) — `docs/subsystems/kernel.md`
- [lifecycle: 현재 public source reference](subsystems/lifecycle.md) — `docs/subsystems/lifecycle.md`
- [memory: 현재 public source reference](subsystems/memory.md) — `docs/subsystems/memory.md`
- [sqlite: 현재 public source reference](subsystems/sqlite.md) — `docs/subsystems/sqlite.md`
- [workflow: 현재 public source reference](subsystems/workflow.md) — `docs/subsystems/workflow.md`

## 제품 역할·skill · 55개

- [CYRANO product plugin](../plugins/cyrano/README.md) — `plugins/cyrano/README.md`
- [역할: blind-handoff-reviewer](../plugins/cyrano/agents/blind-handoff-reviewer.md) — `plugins/cyrano/agents/blind-handoff-reviewer.md`
- [역할: candidate-author](../plugins/cyrano/agents/candidate-author.md) — `plugins/cyrano/agents/candidate-author.md`
- [역할: code-reviewer](../plugins/cyrano/agents/code-reviewer.md) — `plugins/cyrano/agents/code-reviewer.md`
- [CYRANO 공통 실행 규칙](../plugins/cyrano/agents/constitution.md) — `plugins/cyrano/agents/constitution.md`
- [역할: critic](../plugins/cyrano/agents/critic.md) — `plugins/cyrano/agents/critic.md`
- [역할: evidence-scout](../plugins/cyrano/agents/evidence-scout.md) — `plugins/cyrano/agents/evidence-scout.md`
- [역할: experiment-reviewer](../plugins/cyrano/agents/experiment-reviewer.md) — `plugins/cyrano/agents/experiment-reviewer.md`
- [역할: exploration-policy](../plugins/cyrano/agents/exploration-policy.md) — `plugins/cyrano/agents/exploration-policy.md`
- [역할: facilitator](../plugins/cyrano/agents/facilitator.md) — `plugins/cyrano/agents/facilitator.md`
- [역할: implementer](../plugins/cyrano/agents/implementer.md) — `plugins/cyrano/agents/implementer.md`
- [역할: learning-analyst](../plugins/cyrano/agents/learning-analyst.md) — `plugins/cyrano/agents/learning-analyst.md`
- [역할: plan-reviewer](../plugins/cyrano/agents/plan-reviewer.md) — `plugins/cyrano/agents/plan-reviewer.md`
- [역할: planner](../plugins/cyrano/agents/planner.md) — `plugins/cyrano/agents/planner.md`
- [Security Reviewer](../plugins/cyrano/agents/security-reviewer.md) — `plugins/cyrano/agents/security-reviewer.md`
- [역할: verifier](../plugins/cyrano/agents/verifier.md) — `plugins/cyrano/agents/verifier.md`
- [blind-handoff](../plugins/cyrano/skills/blind-handoff/SKILL.md) — `plugins/cyrano/skills/blind-handoff/SKILL.md`
- [blind-handoff: 상세 검토](../plugins/cyrano/skills/blind-handoff/references/checklist.md) — `plugins/cyrano/skills/blind-handoff/references/checklist.md`
- [cache-context](../plugins/cyrano/skills/cache-context/SKILL.md) — `plugins/cyrano/skills/cache-context/SKILL.md`
- [cache-context: 상세 검토](../plugins/cyrano/skills/cache-context/references/checklist.md) — `plugins/cyrano/skills/cache-context/references/checklist.md`
- [Universal Harness 통합 적용](../plugins/cyrano/skills/cache-context/references/universal-integration.md) — `plugins/cyrano/skills/cache-context/references/universal-integration.md`
- [candidate-authoring](../plugins/cyrano/skills/candidate-authoring/SKILL.md) — `plugins/cyrano/skills/candidate-authoring/SKILL.md`
- [candidate-authoring: 상세 검토](../plugins/cyrano/skills/candidate-authoring/references/checklist.md) — `plugins/cyrano/skills/candidate-authoring/references/checklist.md`
- [cyrano-code-intelligence](../plugins/cyrano/skills/cyrano-code-intelligence/SKILL.md) — `plugins/cyrano/skills/cyrano-code-intelligence/SKILL.md`
- [decision-interview](../plugins/cyrano/skills/decision-interview/SKILL.md) — `plugins/cyrano/skills/decision-interview/SKILL.md`
- [decision-interview: 상세 검토](../plugins/cyrano/skills/decision-interview/references/checklist.md) — `plugins/cyrano/skills/decision-interview/references/checklist.md`
- [Universal Harness 통합 적용](../plugins/cyrano/skills/decision-interview/references/universal-integration.md) — `plugins/cyrano/skills/decision-interview/references/universal-integration.md`
- [evidence-scout](../plugins/cyrano/skills/evidence-scout/SKILL.md) — `plugins/cyrano/skills/evidence-scout/SKILL.md`
- [evidence-scout: 상세 검토](../plugins/cyrano/skills/evidence-scout/references/checklist.md) — `plugins/cyrano/skills/evidence-scout/references/checklist.md`
- [exploration-policy](../plugins/cyrano/skills/exploration-policy/SKILL.md) — `plugins/cyrano/skills/exploration-policy/SKILL.md`
- [exploration-policy: 상세 검토](../plugins/cyrano/skills/exploration-policy/references/checklist.md) — `plugins/cyrano/skills/exploration-policy/references/checklist.md`
- [learning-analysis](../plugins/cyrano/skills/learning-analysis/SKILL.md) — `plugins/cyrano/skills/learning-analysis/SKILL.md`
- [learning-analysis: 상세 검토](../plugins/cyrano/skills/learning-analysis/references/checklist.md) — `plugins/cyrano/skills/learning-analysis/references/checklist.md`
- [Universal Harness 통합 적용](../plugins/cyrano/skills/learning-analysis/references/universal-integration.md) — `plugins/cyrano/skills/learning-analysis/references/universal-integration.md`
- [memory-curation](../plugins/cyrano/skills/memory-curation/SKILL.md) — `plugins/cyrano/skills/memory-curation/SKILL.md`
- [monitor-investigation](../plugins/cyrano/skills/monitor-investigation/SKILL.md) — `plugins/cyrano/skills/monitor-investigation/SKILL.md`
- [paired-evaluation-review](../plugins/cyrano/skills/paired-evaluation-review/SKILL.md) — `plugins/cyrano/skills/paired-evaluation-review/SKILL.md`
- [paired-evaluation-review: 상세 검토](../plugins/cyrano/skills/paired-evaluation-review/references/checklist.md) — `plugins/cyrano/skills/paired-evaluation-review/references/checklist.md`
- [계획과 독립 리뷰](../plugins/cyrano/skills/plan-and-review/SKILL.md) — `plugins/cyrano/skills/plan-and-review/SKILL.md`
- [계획·리뷰 체크리스트](../plugins/cyrano/skills/plan-and-review/references/checklist.md) — `plugins/cyrano/skills/plan-and-review/references/checklist.md`
- [Universal Harness 통합 적용](../plugins/cyrano/skills/plan-and-review/references/universal-integration.md) — `plugins/cyrano/skills/plan-and-review/references/universal-integration.md`
- [release-review](../plugins/cyrano/skills/release-review/SKILL.md) — `plugins/cyrano/skills/release-review/SKILL.md`
- [release-review: 상세 검토](../plugins/cyrano/skills/release-review/references/checklist.md) — `plugins/cyrano/skills/release-review/references/checklist.md`
- [Universal Harness 통합 적용](../plugins/cyrano/skills/release-review/references/universal-integration.md) — `plugins/cyrano/skills/release-review/references/universal-integration.md`
- [runtime-code-change](../plugins/cyrano/skills/runtime-code-change/SKILL.md) — `plugins/cyrano/skills/runtime-code-change/SKILL.md`
- [runtime-code-change: 상세 검토](../plugins/cyrano/skills/runtime-code-change/references/checklist.md) — `plugins/cyrano/skills/runtime-code-change/references/checklist.md`
- [safe-implementation](../plugins/cyrano/skills/safe-implementation/SKILL.md) — `plugins/cyrano/skills/safe-implementation/SKILL.md`
- [safe-implementation: 상세 검토](../plugins/cyrano/skills/safe-implementation/references/checklist.md) — `plugins/cyrano/skills/safe-implementation/references/checklist.md`
- [Universal Harness 통합 적용](../plugins/cyrano/skills/safe-implementation/references/universal-integration.md) — `plugins/cyrano/skills/safe-implementation/references/universal-integration.md`
- [scoped-memory](../plugins/cyrano/skills/scoped-memory/SKILL.md) — `plugins/cyrano/skills/scoped-memory/SKILL.md`
- [scoped-memory: 상세 검토](../plugins/cyrano/skills/scoped-memory/references/checklist.md) — `plugins/cyrano/skills/scoped-memory/references/checklist.md`
- [Universal Harness 통합 적용](../plugins/cyrano/skills/scoped-memory/references/universal-integration.md) — `plugins/cyrano/skills/scoped-memory/references/universal-integration.md`
- [verification-recipe](../plugins/cyrano/skills/verification-recipe/SKILL.md) — `plugins/cyrano/skills/verification-recipe/SKILL.md`
- [verification-recipe: 상세 검토](../plugins/cyrano/skills/verification-recipe/references/checklist.md) — `plugins/cyrano/skills/verification-recipe/references/checklist.md`
- [Universal Harness 통합 적용](../plugins/cyrano/skills/verification-recipe/references/universal-integration.md) — `plugins/cyrano/skills/verification-recipe/references/universal-integration.md`

## 참고문서·보존 원문 · 160개

- [원본 dcode 검토 근거 · R4](reference/R4_SOURCE_REVIEW.ko.md) — `docs/reference/R4_SOURCE_REVIEW.ko.md`
- [Coding Agent 기술 조사와 채택 판단](reference/R5_RESEARCH.ko.md) — `docs/reference/R5_RESEARCH.ko.md`
- [첨부 문서팩 사용·충돌 해결](reference/REFERENCE_PACKS.ko.md) — `docs/reference/REFERENCE_PACKS.ko.md`
- [조사 출처와 검증 경계](reference/SOURCES.ko.md) — `docs/reference/SOURCES.ko.md`
- [UDH DREAM Self-Improvement 상세 설계](../references/dream/DESIGN.ko.md) — `references/dream/DESIGN.ko.md`
- [FULL_DESIGN.ko](../references/dream/FULL_DESIGN.ko.html) — `references/dream/FULL_DESIGN.ko.html`
- [UDH DREAM Self-Improvement 상세 설계](../references/dream/FULL_DESIGN.ko.md) — `references/dream/FULL_DESIGN.ko.md`
- [구현 담당 에이전트 작업 지시](../references/dream/IMPLEMENTATION_HANDOFF.ko.md) — `references/dream/IMPLEMENTATION_HANDOFF.ko.md`
- [UDH DREAM 설계 패키지](../references/dream/README.ko.md) — `references/dream/README.ko.md`
- [출처와 조사 범위](../references/dream/SOURCES.md) — `references/dream/SOURCES.md`
- [계약 의미와 서버 측 불변조건](../references/dream/contracts/SEMANTICS.ko.md) — `references/dream/contracts/SEMANTICS.ko.md`
- [자기개선 워커 역할 계약](../references/dream/prompts/roles.ko.md) — `references/dream/prompts/roles.ko.md`
- [Decision Interview — 에이전트 기반 인터뷰 플러그인 설계](../references/interview/DESIGN.ko.md) — `references/interview/DESIGN.ko.md`
- [구현 요청서와 작업 순서](../references/interview/IMPLEMENTATION_PLAN.ko.md) — `references/interview/IMPLEMENTATION_PLAN.ko.md`
- [조사 근거](../references/interview/SOURCES.md) — `references/interview/SOURCES.md`
- [Decision Interview 설계 패키지](../references/interview/START_HERE.ko.md) — `references/interview/START_HERE.ko.md`
- [패키지 검증 범위](../references/interview/VALIDATION.md) — `references/interview/VALIDATION.md`
- [Blind Handoff Reviewer](../references/interview/prompts/blind-handoff-reviewer.md) — `references/interview/prompts/blind-handoff-reviewer.md`
- [Counterexample Critic](../references/interview/prompts/critic.md) — `references/interview/prompts/critic.md`
- [Evidence Scout](../references/interview/prompts/evidence-scout.md) — `references/interview/prompts/evidence-scout.md`
- [Facilitator / Analyst](../references/interview/prompts/facilitator.md) — `references/interview/prompts/facilitator.md`
- [AGENTS.md — dcode 기능 파악 가이드](../references/packs/dcode-analysis/AGENTS.md) — `references/packs/dcode-analysis/AGENTS.md`
- [CLAUDE.md](../references/packs/dcode-analysis/CLAUDE.md) — `references/packs/dcode-analysis/CLAUDE.md`
- [dcode (Deep Agents Code) 소스 분석](../references/packs/dcode-analysis/README.md) — `references/packs/dcode-analysis/README.md`
- [00 — dcode 전체 아키텍처 종합](../references/packs/dcode-analysis/analysis/00-overview.md) — `references/packs/dcode-analysis/analysis/00-overview.md`
- [01 — 진입점·부팅·클라이언트/서버 런타임·세션](../references/packs/dcode-analysis/analysis/01-boot-client-server.md) — `references/packs/dcode-analysis/analysis/01-boot-client-server.md`
- [02 — 에이전트 조립과 SDK 코어 (create_deep_agent, 미들웨어 스택, 백엔드, 컨텍스트 관리)](../references/packs/dcode-analysis/analysis/02-agent-assembly-sdk-core.md) — `references/packs/dcode-analysis/analysis/02-agent-assembly-sdk-core.md`
- [03 — 설정 계층·모델/프로바이더·자격증명·비용 추적](../references/packs/dcode-analysis/analysis/03-config-models-credentials.md) — `references/packs/dcode-analysis/analysis/03-config-models-credentials.md`
- [04 — 승인 모드·Human-in-the-loop·권한·위협 모델](../references/packs/dcode-analysis/analysis/04-approval-hitl-security.md) — `references/packs/dcode-analysis/analysis/04-approval-hitl-security.md`
- [05 — 서브에이전트(동기/비동기)·목표(Goal)와 루브릭(Rubric)](../references/packs/dcode-analysis/analysis/05-subagents-goals-rubrics.md) — `references/packs/dcode-analysis/analysis/05-subagents-goals-rubrics.md`
- [06 — 메모리(AGENTS.md)·스킬 시스템](../references/packs/dcode-analysis/analysis/06-memory-skills.md) — `references/packs/dcode-analysis/analysis/06-memory-skills.md`
- [07 — MCP 도구 · 훅 · Python 확장 · 플러그인](../references/packs/dcode-analysis/analysis/07-mcp-hooks-extensions-plugins.md) — `references/packs/dcode-analysis/analysis/07-mcp-hooks-extensions-plugins.md`
- [08 — 원격 샌드박스·명령 실행 백엔드](../references/packs/dcode-analysis/analysis/08-sandboxes-execution.md) — `references/packs/dcode-analysis/analysis/08-sandboxes-execution.md`
- [09 — 인터랙티브 TUI(Textual) · app.py · 슬래시 커맨드 · ACP 모드](../references/packs/dcode-analysis/analysis/09-tui-app-commands-acp.md) — `references/packs/dcode-analysis/analysis/09-tui-app-commands-acp.md`
- [Approval modes](../references/packs/dcode-analysis/docs_official/code/approval-modes.md) — `references/packs/dcode-analysis/docs_official/code/approval-modes.md`
- [changelog](../references/packs/dcode-analysis/docs_official/code/changelog.md) — `references/packs/dcode-analysis/docs_official/code/changelog.md`
- [Command reference](../references/packs/dcode-analysis/docs_official/code/cli-reference.md) — `references/packs/dcode-analysis/docs_official/code/cli-reference.md`
- [Config file](../references/packs/dcode-analysis/docs_official/code/config-file.md) — `references/packs/dcode-analysis/docs_official/code/config-file.md`
- [Configuration](../references/packs/dcode-analysis/docs_official/code/configuration.md) — `references/packs/dcode-analysis/docs_official/code/configuration.md`
- [Provider credentials](../references/packs/dcode-analysis/docs_official/code/credentials.md) — `references/packs/dcode-analysis/docs_official/code/credentials.md`
- [Python extensions](../references/packs/dcode-analysis/docs_official/code/extensions.md) — `references/packs/dcode-analysis/docs_official/code/extensions.md`
- [Goals and rubrics](../references/packs/dcode-analysis/docs_official/code/goals-and-rubrics.md) — `references/packs/dcode-analysis/docs_official/code/goals-and-rubrics.md`
- [Hooks](../references/packs/dcode-analysis/docs_official/code/hooks.md) — `references/packs/dcode-analysis/docs_official/code/hooks.md`
- [MCP tools](../references/packs/dcode-analysis/docs_official/code/mcp-tools.md) — `references/packs/dcode-analysis/docs_official/code/mcp-tools.md`
- [Memory and Skills](../references/packs/dcode-analysis/docs_official/code/memory-and-skills.md) — `references/packs/dcode-analysis/docs_official/code/memory-and-skills.md`
- [Deep Agents Code](../references/packs/dcode-analysis/docs_official/code/overview.md) — `references/packs/dcode-analysis/docs_official/code/overview.md`
- [Plugins and marketplaces](../references/packs/dcode-analysis/docs_official/code/plugins.md) — `references/packs/dcode-analysis/docs_official/code/plugins.md`
- [Model providers](../references/packs/dcode-analysis/docs_official/code/providers.md) — `references/packs/dcode-analysis/docs_official/code/providers.md`
- [Quickstart](../references/packs/dcode-analysis/docs_official/code/quickstart.md) — `references/packs/dcode-analysis/docs_official/code/quickstart.md`
- [Use remote sandboxes](../references/packs/dcode-analysis/docs_official/code/remote-sandboxes.md) — `references/packs/dcode-analysis/docs_official/code/remote-sandboxes.md`
- [Use subagents in Deep Agents Code](../references/packs/dcode-analysis/docs_official/code/subagents.md) — `references/packs/dcode-analysis/docs_official/code/subagents.md`
- [A2A endpoint in Agent Server](../references/packs/dcode-analysis/docs_official/sdk/a2a.md) — `references/packs/dcode-analysis/docs_official/sdk/a2a.md`
- [Agent Client Protocol (ACP)](../references/packs/dcode-analysis/docs_official/sdk/acp.md) — `references/packs/dcode-analysis/docs_official/sdk/acp.md`
- [Async subagents](../references/packs/dcode-analysis/docs_official/sdk/async-subagents.md) — `references/packs/dcode-analysis/docs_official/sdk/async-subagents.md`
- [Backends](../references/packs/dcode-analysis/docs_official/sdk/backends.md) — `references/packs/dcode-analysis/docs_official/sdk/backends.md`
- [changelog-js](../references/packs/dcode-analysis/docs_official/sdk/changelog-js.md) — `references/packs/dcode-analysis/docs_official/sdk/changelog-js.md`
- [changelog-py](../references/packs/dcode-analysis/docs_official/sdk/changelog-py.md) — `references/packs/dcode-analysis/docs_official/sdk/changelog-py.md`
- [Comparison with Claude Agent SDK](../references/packs/dcode-analysis/docs_official/sdk/comparison.md) — `references/packs/dcode-analysis/docs_official/sdk/comparison.md`
- [Build a content builder agent](../references/packs/dcode-analysis/docs_official/sdk/content-builder.md) — `references/packs/dcode-analysis/docs_official/sdk/content-builder.md`
- [Context engineering in Deep Agents](../references/packs/dcode-analysis/docs_official/sdk/context-engineering.md) — `references/packs/dcode-analysis/docs_official/sdk/context-engineering.md`
- [Customize Deep Agents](../references/packs/dcode-analysis/docs_official/sdk/customization.md) — `references/packs/dcode-analysis/docs_official/sdk/customization.md`
- [Build a data analysis agent](../references/packs/dcode-analysis/docs_official/sdk/data-analysis.md) — `references/packs/dcode-analysis/docs_official/sdk/data-analysis.md`
- [Build a deep research agent](../references/packs/dcode-analysis/docs_official/sdk/deep-research.md) — `references/packs/dcode-analysis/docs_official/sdk/deep-research.md`
- [Dynamic subagents](../references/packs/dcode-analysis/docs_official/sdk/dynamic-subagents.md) — `references/packs/dcode-analysis/docs_official/sdk/dynamic-subagents.md`
- [Event streaming](../references/packs/dcode-analysis/docs_official/sdk/event-streaming.md) — `references/packs/dcode-analysis/docs_official/sdk/event-streaming.md`
- [Fault tolerance](../references/packs/dcode-analysis/docs_official/sdk/fault-tolerance.md) — `references/packs/dcode-analysis/docs_official/sdk/fault-tolerance.md`
- [Going to production](../references/packs/dcode-analysis/docs_official/sdk/going-to-production.md) — `references/packs/dcode-analysis/docs_official/sdk/going-to-production.md`
- [Human-in-the-loop](../references/packs/dcode-analysis/docs_official/sdk/human-in-the-loop.md) — `references/packs/dcode-analysis/docs_official/sdk/human-in-the-loop.md`
- [Interpreters](../references/packs/dcode-analysis/docs_official/sdk/interpreters.md) — `references/packs/dcode-analysis/docs_official/sdk/interpreters.md`
- [Model Context Protocol (MCP)](../references/packs/dcode-analysis/docs_official/sdk/mcp.md) — `references/packs/dcode-analysis/docs_official/sdk/mcp.md`
- [Memory](../references/packs/dcode-analysis/docs_official/sdk/memory.md) — `references/packs/dcode-analysis/docs_official/sdk/memory.md`
- [Models](../references/packs/dcode-analysis/docs_official/sdk/models.md) — `references/packs/dcode-analysis/docs_official/sdk/models.md`
- [Multimodal inputs and outputs](../references/packs/dcode-analysis/docs_official/sdk/multimodal.md) — `references/packs/dcode-analysis/docs_official/sdk/multimodal.md`
- [OpenWiki](../references/packs/dcode-analysis/docs_official/sdk/openwiki.md) — `references/packs/dcode-analysis/docs_official/sdk/openwiki.md`
- [Deep Agents overview](../references/packs/dcode-analysis/docs_official/sdk/overview.md) — `references/packs/dcode-analysis/docs_official/sdk/overview.md`
- [Permissions](../references/packs/dcode-analysis/docs_official/sdk/permissions.md) — `references/packs/dcode-analysis/docs_official/sdk/permissions.md`
- [Profiles](../references/packs/dcode-analysis/docs_official/sdk/profiles.md) — `references/packs/dcode-analysis/docs_official/sdk/profiles.md`
- [Quickstart](../references/packs/dcode-analysis/docs_official/sdk/quickstart.md) — `references/packs/dcode-analysis/docs_official/sdk/quickstart.md`
- [Retrieval Augmented Generation (RAG) with Deep Agents](../references/packs/dcode-analysis/docs_official/sdk/rag.md) — `references/packs/dcode-analysis/docs_official/sdk/rag.md`
- [Retrieval](../references/packs/dcode-analysis/docs_official/sdk/retrieval.md) — `references/packs/dcode-analysis/docs_official/sdk/retrieval.md`
- [Grading rubrics](../references/packs/dcode-analysis/docs_official/sdk/rubric.md) — `references/packs/dcode-analysis/docs_official/sdk/rubric.md`
- [Sandbox](../references/packs/dcode-analysis/docs_official/sdk/sandbox.md) — `references/packs/dcode-analysis/docs_official/sdk/sandbox.md`
- [Sandboxes](../references/packs/dcode-analysis/docs_official/sdk/sandboxes.md) — `references/packs/dcode-analysis/docs_official/sdk/sandboxes.md`
- [Skills](../references/packs/dcode-analysis/docs_official/sdk/skills.md) — `references/packs/dcode-analysis/docs_official/sdk/skills.md`
- [Streaming](../references/packs/dcode-analysis/docs_official/sdk/streaming.md) — `references/packs/dcode-analysis/docs_official/sdk/streaming.md`
- [Subagent streaming](../references/packs/dcode-analysis/docs_official/sdk/subagent-streaming.md) — `references/packs/dcode-analysis/docs_official/sdk/subagent-streaming.md`
- [Subagents](../references/packs/dcode-analysis/docs_official/sdk/subagents.md) — `references/packs/dcode-analysis/docs_official/sdk/subagents.md`
- [Todo list](../references/packs/dcode-analysis/docs_official/sdk/todo-list.md) — `references/packs/dcode-analysis/docs_official/sdk/todo-list.md`
- [Tools](../references/packs/dcode-analysis/docs_official/sdk/tools.md) — `references/packs/dcode-analysis/docs_official/sdk/tools.md`
- [UDH Python Engineering Quality Harness 상세설계 Kit](../references/packs/python-engineering/START_HERE.ko.md) — `references/packs/python-engineering/START_HERE.ko.md`
- [UDH_PYTHON_ENGINEERING_FULL_DESIGN.ko](../references/packs/python-engineering/UDH_PYTHON_ENGINEERING_FULL_DESIGN.ko.html) — `references/packs/python-engineering/UDH_PYTHON_ENGINEERING_FULL_DESIGN.ko.html`
- [UDH Python Engineering Quality Harness 상세설계](../references/packs/python-engineering/UDH_PYTHON_ENGINEERING_FULL_DESIGN.ko.md) — `references/packs/python-engineering/UDH_PYTHON_ENGINEERING_FULL_DESIGN.ko.md`
- [ADR-PY-001 — UDH의 Python 품질 정책 정합화](../references/packs/python-engineering/docs/decisions/ADR-PY-001.ko.md) — `references/packs/python-engineering/docs/decisions/ADR-PY-001.ko.md`
- [1. 범위, 적용 순서, 확정 결정](../references/packs/python-engineering/docs/design/01_SCOPE_AND_DECISIONS.ko.md) — `references/packs/python-engineering/docs/design/01_SCOPE_AND_DECISIONS.ko.md`
- [2. 아키텍처와 파일별 책임](../references/packs/python-engineering/docs/design/02_ARCHITECTURE_AND_OWNERSHIP.ko.md) — `references/packs/python-engineering/docs/design/02_ARCHITECTURE_AND_OWNERSHIP.ko.md`
- [3. Python 품질 정책](../references/packs/python-engineering/docs/design/03_PYTHON_POLICY.ko.md) — `references/packs/python-engineering/docs/design/03_PYTHON_POLICY.ko.md`
- [4. AGENTS, Skill, 역할, 컨텍스트](../references/packs/python-engineering/docs/design/04_AGENT_SKILL_AND_CONTEXT.ko.md) — `references/packs/python-engineering/docs/design/04_AGENT_SKILL_AND_CONTEXT.ko.md`
- [5. 작업 계획과 상태 전이](../references/packs/python-engineering/docs/design/05_PLAN_AND_STATE_MACHINE.ko.md) — `references/packs/python-engineering/docs/design/05_PLAN_AND_STATE_MACHINE.ko.md`
- [6. 스냅샷, 정책 보호, 실행 경계](../references/packs/python-engineering/docs/design/06_SNAPSHOT_AND_TRUST.ko.md) — `references/packs/python-engineering/docs/design/06_SNAPSHOT_AND_TRUST.ko.md`
- [7. QualityRunner와 도구 어댑터](../references/packs/python-engineering/docs/design/07_RUNNER_AND_TOOL_ADAPTERS.ko.md) — `references/packs/python-engineering/docs/design/07_RUNNER_AND_TOOL_ADAPTERS.ko.md`
- [8. 데이터 계약과 최종 완료 판정](../references/packs/python-engineering/docs/design/08_DATA_CONTRACTS_AND_COMPLETION.ko.md) — `references/packs/python-engineering/docs/design/08_DATA_CONTRACTS_AND_COMPLETION.ko.md`
- [9. Legacy baseline과 예외](../references/packs/python-engineering/docs/design/09_LEGACY_AND_EXCEPTIONS.ko.md) — `references/packs/python-engineering/docs/design/09_LEGACY_AND_EXCEPTIONS.ko.md`
- [10. 실제 dcode 연결](../references/packs/python-engineering/docs/design/10_DCODE_INTEGRATION.ko.md) — `references/packs/python-engineering/docs/design/10_DCODE_INTEGRATION.ko.md`
- [11. CI, 보안, 운영](../references/packs/python-engineering/docs/design/11_CI_SECURITY_AND_OPERATIONS.ko.md) — `references/packs/python-engineering/docs/design/11_CI_SECURITY_AND_OPERATIONS.ko.md`
- [12. 관측과 제한적 자기개선](../references/packs/python-engineering/docs/design/12_OBSERVABILITY_AND_SELF_IMPROVEMENT.ko.md) — `references/packs/python-engineering/docs/design/12_OBSERVABILITY_AND_SELF_IMPROVEMENT.ko.md`
- [13. 인수 테스트 명세](../references/packs/python-engineering/docs/design/13_ACCEPTANCE_TEST_SPEC.ko.md) — `references/packs/python-engineering/docs/design/13_ACCEPTANCE_TEST_SPEC.ko.md`
- [14. 출처, 검증 범위, 인계 주의사항](../references/packs/python-engineering/docs/design/14_SOURCES_AND_VALIDATION.ko.md) — `references/packs/python-engineering/docs/design/14_SOURCES_AND_VALIDATION.ko.md`
- [15. 구현 API, 저장 DDL, 오류 계약](../references/packs/python-engineering/docs/design/15_API_STORAGE_ERROR_CONTRACTS.ko.md) — `references/packs/python-engineering/docs/design/15_API_STORAGE_ERROR_CONTRACTS.ko.md`
- [Python Quality Harness 구현 계획](../references/packs/python-engineering/docs/development/PY_IMPLEMENTATION_PLAN.ko.md) — `references/packs/python-engineering/docs/development/PY_IMPLEMENTATION_PLAN.ko.md`
- [도입 및 실행 Runbook](../references/packs/python-engineering/docs/execution/PY_RUNBOOK.ko.md) — `references/packs/python-engineering/docs/execution/PY_RUNBOOK.ko.md`
- [하위 구현 모델 전달 요청문](../references/packs/python-engineering/handoff/IMPLEMENTATION_REQUEST.ko.md) — `references/packs/python-engineering/handoff/IMPLEMENTATION_REQUEST.ko.md`
- [Python Code Reviewer](../references/packs/python-engineering/templates/agents/python-code-reviewer/AGENTS.md) — `references/packs/python-engineering/templates/agents/python-code-reviewer/AGENTS.md`
- [Python Plan Reviewer](../references/packs/python-engineering/templates/agents/python-plan-reviewer/AGENTS.md) — `references/packs/python-engineering/templates/agents/python-plan-reviewer/AGENTS.md`
- [AGENTS.python-section](../references/packs/python-engineering/templates/project/AGENTS.python-section.md) — `references/packs/python-engineering/templates/project/AGENTS.python-section.md`
- [Python Engineering](../references/packs/python-engineering/templates/skills/python-engineering/SKILL.md) — `references/packs/python-engineering/templates/skills/python-engineering/SKILL.md`
- [Completion evidence](../references/packs/python-engineering/templates/skills/python-engineering/references/completion.md) — `references/packs/python-engineering/templates/skills/python-engineering/references/completion.md`
- [Legacy repositories](../references/packs/python-engineering/templates/skills/python-engineering/references/legacy.md) — `references/packs/python-engineering/templates/skills/python-engineering/references/legacy.md`
- [Policy interpretation](../references/packs/python-engineering/templates/skills/python-engineering/references/policy.md) — `references/packs/python-engineering/templates/skills/python-engineering/references/policy.md`
- [UDH 통합 상세 설계서](../references/universal-harness/FULL_DESIGN.ko.md) — `references/universal-harness/FULL_DESIGN.ko.md`
- [구현 에이전트에게 전달할 작업 지시](../references/universal-harness/IMPLEMENTER_HANDOFF.ko.md) — `references/universal-harness/IMPLEMENTER_HANDOFF.ko.md`
- [UDH 설계 패키지 시작점](../references/universal-harness/START_HERE.ko.md) — `references/universal-harness/START_HERE.ko.md`
- [UDH_FULL_DESIGN.ko](../references/universal-harness/UDH_FULL_DESIGN.ko.html) — `references/universal-harness/UDH_FULL_DESIGN.ko.html`
- [검증 결과와 적용 범위](../references/universal-harness/VALIDATION.ko.md) — `references/universal-harness/VALIDATION.ko.md`
- [UDH: dcode 기반 범용 개발 Harness 상세 설계](../references/universal-harness/docs/01_ARCHITECTURE_AND_WORKFLOW.ko.md) — `references/universal-harness/docs/01_ARCHITECTURE_AND_WORKFLOW.ko.md`
- [런타임·권한·컨텍스트·메모리·Self-Improving 상세 계약](../references/universal-harness/docs/02_RUNTIME_MEMORY_AND_LEARNING.ko.md) — `references/universal-harness/docs/02_RUNTIME_MEMORY_AND_LEARNING.ko.md`
- [전체 개발 과정 모니터링·Python 품질·운영·출시 판정](../references/universal-harness/docs/03_OBSERVABILITY_QUALITY_AND_OPERATIONS.ko.md) — `references/universal-harness/docs/03_OBSERVABILITY_QUALITY_AND_OPERATIONS.ko.md`
- [모듈·API·저장소 계약과 구현 순서](../references/universal-harness/docs/04_MODULE_API_AND_IMPLEMENTATION.ko.md) — `references/universal-harness/docs/04_MODULE_API_AND_IMPLEMENTATION.ko.md`
- [데이터 계약·알고리즘·어댑터 동작·검증 상세](../references/universal-harness/docs/05_CONTRACT_DETAILS_AND_TESTING.ko.md) — `references/universal-harness/docs/05_CONTRACT_DETAILS_AND_TESTING.ko.md`
- [출처·첨부 설계 보존·요구사항 추적](../references/universal-harness/docs/06_SOURCES_AND_TRACEABILITY.ko.md) — `references/universal-harness/docs/06_SOURCES_AND_TRACEABILITY.ko.md`
- [Universal development principles](../references/universal-harness/prompts/AGENTS.template.md) — `references/universal-harness/prompts/AGENTS.template.md`
- [공통 worker 계약](../references/universal-harness/prompts/COMMON_WORKER.ko.md) — `references/universal-harness/prompts/COMMON_WORKER.ko.md`
- [독립 인수인계 검토자 / `blind_handoff_reviewer`](../references/universal-harness/prompts/blind_handoff_reviewer.ko.md) — `references/universal-harness/prompts/blind_handoff_reviewer.ko.md`
- [명세 반례 검토자 / `counterexample_critic`](../references/universal-harness/prompts/counterexample_critic.ko.md) — `references/universal-harness/prompts/counterexample_critic.ko.md`
- [독립 평가 판정자 / `evaluator`](../references/universal-harness/prompts/evaluator.ko.md) — `references/universal-harness/prompts/evaluator.ko.md`
- [근거 조사자 / `evidence_scout`](../references/universal-harness/prompts/evidence_scout.ko.md) — `references/universal-harness/prompts/evidence_scout.ko.md`
- [사용자 진행자 / `facilitator`](../references/universal-harness/prompts/facilitator.ko.md) — `references/universal-harness/prompts/facilitator.ko.md`
- [독립 최종 코드 검토자 / `final_reviewer`](../references/universal-harness/prompts/final_reviewer.ko.md) — `references/universal-harness/prompts/final_reviewer.ko.md`
- [승인 범위 구현자 / `implementer`](../references/universal-harness/prompts/implementer.ko.md) — `references/universal-harness/prompts/implementer.ko.md`
- [범용 개선 분석자 / `learning_analyst`](../references/universal-harness/prompts/learning_analyst.ko.md) — `references/universal-harness/prompts/learning_analyst.ko.md`
- [독립 계획 검토자 / `plan_reviewer`](../references/universal-harness/prompts/plan_reviewer.ko.md) — `references/universal-harness/prompts/plan_reviewer.ko.md`
- [구체 개발 계획자 / `planner`](../references/universal-harness/prompts/planner.ko.md) — `references/universal-harness/prompts/planner.ko.md`
- [독립 보안 검토자 / `security_reviewer`](../references/universal-harness/prompts/security_reviewer.ko.md) — `references/universal-harness/prompts/security_reviewer.ko.md`
- [udh-evaluate](../references/universal-harness/prompts/skills/udh-evaluate/SKILL.md) — `references/universal-harness/prompts/skills/udh-evaluate/SKILL.md`
- [udh-implement](../references/universal-harness/prompts/skills/udh-implement/SKILL.md) — `references/universal-harness/prompts/skills/udh-implement/SKILL.md`
- [udh-improve](../references/universal-harness/prompts/skills/udh-improve/SKILL.md) — `references/universal-harness/prompts/skills/udh-improve/SKILL.md`
- [udh-interview](../references/universal-harness/prompts/skills/udh-interview/SKILL.md) — `references/universal-harness/prompts/skills/udh-interview/SKILL.md`
- [udh-investigate](../references/universal-harness/prompts/skills/udh-investigate/SKILL.md) — `references/universal-harness/prompts/skills/udh-investigate/SKILL.md`
- [udh-plan](../references/universal-harness/prompts/skills/udh-plan/SKILL.md) — `references/universal-harness/prompts/skills/udh-plan/SKILL.md`
- [udh-review](../references/universal-harness/prompts/skills/udh-review/SKILL.md) — `references/universal-harness/prompts/skills/udh-review/SKILL.md`
- [udh-verify](../references/universal-harness/prompts/skills/udh-verify/SKILL.md) — `references/universal-harness/prompts/skills/udh-verify/SKILL.md`
- [실행 증거 검증자 / `verifier`](../references/universal-harness/prompts/verifier.ko.md) — `references/universal-harness/prompts/verifier.ko.md`
- [Decision Interview — 에이전트 기반 인터뷰 플러그인 설계](../references/universal-harness/source_interview/DESIGN.ko.md) — `references/universal-harness/source_interview/DESIGN.ko.md`
- [구현 요청서와 작업 순서](../references/universal-harness/source_interview/IMPLEMENTATION_PLAN.ko.md) — `references/universal-harness/source_interview/IMPLEMENTATION_PLAN.ko.md`
- [조사 근거](../references/universal-harness/source_interview/SOURCES.md) — `references/universal-harness/source_interview/SOURCES.md`
- [Decision Interview 설계 패키지](../references/universal-harness/source_interview/START_HERE.ko.md) — `references/universal-harness/source_interview/START_HERE.ko.md`
- [패키지 검증 범위](../references/universal-harness/source_interview/VALIDATION.md) — `references/universal-harness/source_interview/VALIDATION.md`
- [Blind Handoff Reviewer](../references/universal-harness/source_interview/prompts/blind-handoff-reviewer.md) — `references/universal-harness/source_interview/prompts/blind-handoff-reviewer.md`
- [Counterexample Critic](../references/universal-harness/source_interview/prompts/critic.md) — `references/universal-harness/source_interview/prompts/critic.md`
- [Evidence Scout](../references/universal-harness/source_interview/prompts/evidence-scout.md) — `references/universal-harness/source_interview/prompts/evidence-scout.md`
- [Facilitator / Analyst](../references/universal-harness/source_interview/prompts/facilitator.md) — `references/universal-harness/source_interview/prompts/facilitator.md`

## 작성 템플릿 · 3개

- [개발 WorkPlan](../templates/WORK_PLAN.ko.md) — `templates/WORK_PLAN.ko.md`
- [Native 연결 patch 청사진 — 아직 적용되지 않음](../templates/native-monitor/README.ko.md) — `templates/native-monitor/README.ko.md`
- [preview.synthetic](../templates/native-monitor/preview.synthetic.html) — `templates/native-monitor/preview.synthetic.html`

## 프로젝트 안내·계약 설명 · 21개

- [CYRANO 개발 지침](../.claude/CLAUDE.md) — `.claude/CLAUDE.md`
- [CYRANO 개발 지침](../CLAUDE.md) — `CLAUDE.md`
- [Cyrano Agent · AI 개발 수행 지시](../IMPLEMENTATION_REQUEST.ko.md) — `IMPLEMENTATION_REQUEST.ko.md`
- [출처와 배포 범위](../NOTICE.md) — `NOTICE.md`
- [CYRANO R3](../README.ko.md) — `README.ko.md`
- [CYRANO R3 · dcode source-native development kit](../README.md) — `README.md`
- [Cyrano Agent · 프로젝트 시작](../START_HERE.ko.md) — `START_HERE.ko.md`
- [R4 상세 계약의 적용 범위](../contracts/r4/README.ko.md) — `contracts/r4/README.ko.md`
- [R5 계약 · canonical 상태와 화면 projection 분리](../contracts/r5/README.ko.md) — `contracts/r5/README.ko.md`
- [Cyrano Agent · 작은 길잡이](NAVIGATION.ko.md) — `docs/NAVIGATION.ko.md`
- [현재 소스 구조](architecture.md) — `docs/architecture.md`
- [새 skill 추가](cookbook/add-skill.ko.md) — `docs/cookbook/add-skill.ko.md`
- [계약 변경](cookbook/change-contract.ko.md) — `docs/cookbook/change-contract.ko.md`
- [Work Package 구현](cookbook/implement-work-package.ko.md) — `docs/cookbook/implement-work-package.ko.md`
- [개발 실행](development.md) — `docs/development.md`
- [첨부 Universal Harness 상세 분석·반영 결과](reviews/2026-09-16-universal-harness-analysis.ko.md) — `docs/reviews/2026-09-16-universal-harness-analysis.ko.md`
- [조사 출처와 채택 범위](sources.md) — `docs/sources.md`
- [테스트 문서 위치](testing.md) — `docs/testing.md`
- [Native source modules](../packages/README.md) — `packages/README.md`
- [dcode runtime 검증 경계](../runtime/README.md) — `runtime/README.md`
- [프로젝트 단위 도구 설치](../tools/README.md) — `tools/README.md`

## 생성된 통합 읽기용 문서 · 5개

- [Cyrano Agent · 문서 유형별 전체 목차](INDEX.ko.md) — `docs/INDEX.ko.md`
- [DEVELOPER_GUIDE.ko](generated/DEVELOPER_GUIDE.ko.html) — `docs/generated/DEVELOPER_GUIDE.ko.html`
- [Cyrano Agent · 개발 수행 가이드](generated/DEVELOPER_GUIDE.ko.md) — `docs/generated/DEVELOPER_GUIDE.ko.md`
- [FULL_DESIGN.ko](generated/FULL_DESIGN.ko.html) — `docs/generated/FULL_DESIGN.ko.html`
- [Cyrano Agent · dcode 기반 전체 상세 설계](generated/FULL_DESIGN.ko.md) — `docs/generated/FULL_DESIGN.ko.md`

## 실행 증거 문서 · 1개

- [현재 검사 결과](../evidence/README.md) — `evidence/README.md`

## 제품 코드와 테스트의 현재 참고

- [deepagents_code/cyrano/AGENTS.md](../../deepagents_code/cyrano/AGENTS.md)
- [deepagents_code/cyrano/cli/README.md](../../deepagents_code/cyrano/cli/README.md)
- [deepagents_code/cyrano/context/README.md](../../deepagents_code/cyrano/context/README.md)
- [deepagents_code/cyrano/contracts/README.md](../../deepagents_code/cyrano/contracts/README.md)
- [deepagents_code/cyrano/dcode/README.md](../../deepagents_code/cyrano/dcode/README.md)
- [deepagents_code/cyrano/evaluation/README.md](../../deepagents_code/cyrano/evaluation/README.md)
- [deepagents_code/cyrano/events/README.md](../../deepagents_code/cyrano/events/README.md)
- [deepagents_code/cyrano/improvement/README.md](../../deepagents_code/cyrano/improvement/README.md)
- [deepagents_code/cyrano/intelligence/README.md](../../deepagents_code/cyrano/intelligence/README.md)
- [deepagents_code/cyrano/interview/README.md](../../deepagents_code/cyrano/interview/README.md)
- [deepagents_code/cyrano/kernel/README.md](../../deepagents_code/cyrano/kernel/README.md)
- [deepagents_code/cyrano/memory/README.md](../../deepagents_code/cyrano/memory/README.md)
- [deepagents_code/cyrano/monitor/README.md](../../deepagents_code/cyrano/monitor/README.md)
- [deepagents_code/cyrano/plugins/README.md](../../deepagents_code/cyrano/plugins/README.md)
- [deepagents_code/cyrano/sqlite/README.md](../../deepagents_code/cyrano/sqlite/README.md)
- [deepagents_code/cyrano/workflow/README.md](../../deepagents_code/cyrano/workflow/README.md)
- [tests/unit_tests/cyrano/AGENTS.md](../../tests/unit_tests/cyrano/AGENTS.md)
- [tests/cyrano_product/README.md](../../tests/cyrano_product/README.md)
- [.agents/skills/cyrano-development/SKILL.md](../../.agents/skills/cyrano-development/SKILL.md)
- [CYRANO_START_HERE.ko.md](../../CYRANO_START_HERE.ko.md)

## 기계 계약·증거

Schema/SQL: `contracts/`; WP DAG: `.agents/work/plan.json`; TS DAG: `docs/development/test-work-plan.json`; RC DAG: `docs/development/r4-work-plan.json`; RF DAG: `docs/development/r5-work-plan.json`; 실제 검사: `evidence/`.
