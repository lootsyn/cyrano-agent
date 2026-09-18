# 적응형 Memory·Skill 개선 상세 설계

문서 유형: 목표 상세 설계. [Memory 수명주기](MEMORY_LIFECYCLE.ko.md)와 [개선 수명주기](SELF_IMPROVEMENT_LIFECYCLE.ko.md)를 확장한다. 기존 승인·scope·paired eval을 약화하지 않는다. 소유 RF04–RF06, WP11/WP16–WP20. 연구는 [R5 참고 분석](../reference/R5_RESEARCH.ko.md) [S03]–[S09]이다.

## 1. 장기 기억을 세 가지 표현으로 분리

`CoreMemoryProjection`은 명시적 사용자 선호·승인된 핵심 프로젝트 규칙만 작은 stable 블록에 담는다. session/epoch 시작 시 release digest로 고정한다. new candidate가 생겨도 active prompt를 매 turn 덮어쓰지 않는다. freshness가 깨졌거나 사용자 정정·보안 revoke가 발생하면 stale 안내를 동적 tail에 넣고 필요한 epoch 재바인딩을 수행한다. cache 유지를 위해 거짓 사실을 계속 authoritative로 주입하면 안 된다.

`EpisodeRecord`는 task-family/source/runtime 조건, 실패·성공·교정·검증 근거, 사용한 memory와 skill, 비용·오류를 가진 관측이다. 요약은 원본 event/artifact refs를 잃지 않는 파생 view이며 개인정보 보존과 삭제를 따른다. episode 검색은 질문 결과의 hint이며 성공 recipe 권위가 아니다.

`PlaybookEntry`는 하나의 절차/주의점/검증 recipe다. entry_id, revision, scope, applies_when, does_not_apply_when, content, evidence_ids, counterexample_ids, related_entries, validation_status, sensitivity, dependency_digests, created_from_candidate, supersedes를 가진다. topic heading만 바꾸어 전체 skill을 교체하지 않는다. protected core instructions는 playbook 영역 밖이다.

## 2. Recall 결정과 두 단계 검색

계획 단계의 recall request는 phase, WorkUnit 목표, touched paths, unknowns, evidence budget을 포함한다. ACL과 active/fresh 필터를 먼저 적용한다. primary lexical retrieval은 dependency/tag/path/FTS를 사용한다. optional embedding은 동일한 필터의 corpus에서만 검색한다. 특정 provider rank 점수를 서로 같은 확률로 해석하지 않는다.

관련성 기준을 넘은 후보만 utility 우선순위의 영향을 받을 수 있다. policy 예시 `rank = normalized_relevance + clip(utility_adjustment, -0.1, 0.1)`는 초기 실험 설정이지 최적 공식이 아니다. utility는 entry_revision×task_family×evaluation_condition에 귀속하고 factual confidence·approval·권한에 영향을 주지 않는다. task 성공 여부를 그 task에 노출된 모든 memory에 보상으로 일괄 배분하지 않는다.

허용된 정답은 `no_recall_needed`와 `insufficient_relevant_memory`도 포함한다. 필수 안전 규칙은 recall 최적화로 빼지 않는다. 아무 관련 memory가 없는데 3-2 점수를 받으려고 엉뚱한 기억을 주입하면 실패다. 검증은 관련성이 있는 숨은 과제를 새 세션에 주어 실제 적용을 확인하고, 관련 없는 과제에서는 정확도 유지와 불필요 주입 감소를 확인한다.

## 3. 노출·사용·효과 ledger

`RecallExposure`: view_id, run_id, phase, entry_revision, rank_features_ref, selected, injected, referenced, application_check_id, observed_outcome_ref, experimental_assignment. 모델의 '도움됐다'는 별도 self_report다. ApplicationChecker는 계획의 제약 반영, 코드 변경, 검증 recipe 실행 중 사전 지정된 검사를 사용한다. automatic detector가 확신하지 못하면 unknown으로 두며, 독립 reviewer는 evidence-backed 판정을 남길 수 있다.

`UtilityObservation`은 통제 평가에서 on/off 또는 baseline/candidate 비교가 가능할 때만 causal로 표기한다. 일반 업무 feedback은 correlational이다. 초깃값은 중립, 최소 독립 family 수 전까지 ranking 영향 0, 최신 조건 변화 시 decay 또는 reset. utility snapshot은 release로 고정하고 run 중 갱신을 직접 반영하지 않는다. 실험 정책은 모델 이름에 따라 분기하지 않고 condition별 결과를 보고만 한다.

## 4. Entry delta와 consolidation

ACE를 참고해 `add`, `refine`, `link`, `deprecate`의 typed delta를 생성한다. base_release_digest와 expected_revision을 필수로 한다. add에는 조건·근거·반례 검증 계획이 필요하고 refine은 이전 의미의 보존/변경 범위를 표시한다. deprecate는 삭제가 아니라 새 revision의 inactive 표시다. 실제 개인정보 삭제는 별도 retention/deletion workflow다. link는 `supports`, `contradicts`, `supersedes`, `example_of` 중 허용된 종류만 사용한다. scope가 다른 entry로 권한을 확장하는 링크를 만들지 않는다.

정적 검증 순서: 입력 schema→release/revision CAS→권한/scope→근거 유효성→protected surface 검사→의미 변경 분류→중복/상충→크기/적용 조건→evaluation manifest 생성. 문자열 정규식 injection 검사만으로 안전성을 확정하지 않는다. 코드·명령이 포함된 skill resource는 executable 후보로 올려 별도 빌드/승인 경로를 거친다.

consolidation trigger는 terminal episode, 반복 교정, memory capacity 압력, 명시적 refine다. 매 tool error마다 LLM을 재귀 호출하지 않는다. 같은 episode/release/policy에는 outbox key 하나, 작업 예산·max attempts·deadline·pause·취소·dead-letter가 있다. UI 알림 suppress는 worker disable과 다르다. 포그라운드가 자원을 요구하면 queue를 defer하지만 프로세스 종료 시 잃지 않는다. '학습 실행됨', '후보 있음', '평가 완료', '승격', '다음 task 적용'을 다른 이벤트로 표시한다.

## 5. 작은 core 유지와 무손실 관리

core 크기는 token budget이 검증된 tokenizer를 쓰며, character budget은 명시적으로 char limit이라고 표시한다. 압축 후보가 필수 규칙·예외·금지·근거 링크를 잃으면 reject한다. 더 작은 summary가 무조건 개선이 아니다. core 밖 상세 entry는 query+progressive skill로 찾는다. full raw session을 stable system block에 붙이지 않는다.

상충한 기억은 다수결로 진위를 확정하지 않는다. fresh evidence/사용자 명시 수정/현재 source가 우선이다. 불확실 기록은 hypothesis로 보여 주며 자동 질문을 남발하지 않는다. 재확인 비용과 위험을 plan에 넣는다. 삭제 대상 entry에 대한 link·embedding·QMD corpus·학습 후보·백업 복구에도 tombstone epoch를 적용해 재등장을 막는다. backup을 복원해도 최신 삭제 ledger를 replay하기 전 active 검색을 열지 않는다.

## 6. 실제 비교 평가

평가 arm: A0=기존 R4 memory, A1=bounded core+episode recall, A2=A1+entry delta, A3=A2+utility/abstain. 비교 예산·과제·승인·tool inventory·환경을 사전 고정한다. 요인별 ablation을 건너뛰고 네 기능을 한 번에 바꿔 각 기능 효과라고 주장하지 않는다. 효용 실험은 개발 세트→잠긴 holdout→새 task future window를 구분하고 repo family/time leakage를 검사한다.

주요 지표: 실제 task acceptance, memory application precision, relevance/abstention 오류, 재발 실패율, 비밀/권한 위반, source-stale 오류, 비용·latency·cache usage coverage. 최소 20 independent families×반복3은 초기 계획 예시이며 표본 수만으로 검정력 보장하지 않는다. family 단위 paired CI와 correctness non-inferiority margin을 사전 등록한다. 통계적으로 결론이 없으면 inconclusive, 안전 위반이면 hard reject다.

새 release 승격 뒤 다른 프로세스·새 task에 binding하고 실제 행동과 registry hash가 일치해야 3-4를 검증한다. 운영 canary는 동의된 신규 작업만 대상으로 하며 코드·메모리의 mutation은 별도 승인된다. rollback은 harness와 작업 source를 나누고 영향 session 목록을 남긴다.

## 7. 구현 인터페이스

| 함수 | 전제·후조건 | 오류 |
|---|---|---|
| `build_episode(terminal_event, source_manifest)` | trusted terminal/outbox same tx, raw refs retained | incomplete_trace, unknown_outcome |
| `propose_core_projection(release, budget)` | policy·facts role 분리, stable draft 반환 | critical_fact_loss, budget_overflow |
| `decide_recall(work_unit, policy)` | 필수 규칙 제외 불가, reason-coded choice | policy_unavailable |
| `rank_memory(view, utility_snapshot)` | 같은 scope·freshness, ties deterministic | utility_condition_mismatch |
| `validate_delta(base, proposed)` | 새 candidate만 반환, active 불변 | stale_revision, protected_change |
| `record_application(exposure, artifacts)` | detector evidence, unknown 유지 | missing_proof |
| `build_eval_arms(candidate, dataset)` | hidden answers 미노출, 전후 입력 고정 | split_leakage |
| `bind_release(new_run)` | approved immutable snapshot | revoked_release |

## 1. 분류는 조회·수명 정책이지 새 데이터베이스 열한 개가 아니다

| 첨부 분류 | 기존 Cyrano에 매핑 | 권위·수명 |
|---|---|---|
| Session Memory | checkpoint/context epoch | 현재 세션, 최신 계획·원장 우선 |
| Working Memory | task work state | 작업별, 미해결 의무 보존 |
| Project Memory | scoped semantic | workspace/source 유효성 검사 |
| Semantic Memory | semantic facts | 근거·유효기간·상충 상태 필요 |
| Episodic Memory | episodes/evidence | 실제 실행, 해석과 분리 |
| Procedural Memory | approved recipe | version/release에 결속 |
| Skill Memory | skill artifact | registry·테스트·승격 필요 |
| Failure Memory | episode failure facet | 원인 미확정은 hypothesis |
| Preference Memory | explicit human preference | 최근 사용자 결정 우선 |
| Architecture Decision | decision/evidence facet | 원문·대안·변경 이력 |
| Review Feedback | finding/disposition facet | 정성 피드백, fact 자동 승격 금지 |

기존 memory.kind enum을 즉시 바꾸지 않는다. facet과 query view로 매핑 가능한지 WP11에서 결정하고, durable 형식을 바꿀 필요가 있을 때만 별도 migration을 검토한다.

## 2. 고정 핵심과 event-triggered recall

core memory는 session/release 시작에 고정한다. 나머지는 `plan.started`, `tool.failed`, `review.finding`, `context.pressure`, `task.resumed` 등의 의미 있는 이벤트에서 후보를 찾는다. TTL마다 무조건 LLM을 깨우지 않는다. 최소 interval·event coalescing·queue priority·예산을 둔다.

순서: scope/ACL → active/not-deleted → dependency freshness → query retrieval → evidence validity → relevance → utility 보조 → 중복·상충 → context budget. top-k를 뽑고 나서 권한을 필터하면 다른 scope의 자료 때문에 필요한 자료가 누락될 수 있으므로 금지한다.

`RecallHint`는 memory id/revision과 사실 한 문장·trigger ref·expiry만 가진다. 부모가 최신 후보 set과 대조한다. [OMO gate](../reference/SOURCES.ko.md#ns09)의 짧은 nudge를 참고하되 정규식만으로 injection을 차단했다고 주장하지 않는다. 명령을 포함한 외부 자료는 낮은 신뢰의 인용 데이터이며 policy가 되지 않는다.

## 3. Memory application의 증거

`queried`, `selected`, `injected`, `referenced`, `applied`, `effect_measured`를 별도로 기록한다. `applied`는 plan diff의 요구·작업 연결, code diff의 수정 범위, 실행된 verification에서 어떤 기억이 영향을 주었는지 observer/검토자가 확인한 상태다. LLM의 자기보고는 self_report로 별도 보관한다.

같은 session에서 다시 떠올린 기억은 persistence 시험이 아니다. 프로세스 A 종료 뒤 새 프로세스 B에서 persisted revision을 조회하고, 다른 workspace에선 조회되지 않으며, 이를 실제 계획에 적용하는 시험이 필요하다. resume에서 과거 요약을 읽은 결과만으로 3-1/3-2를 통과시키지 않는다.

## 4. Utility는 신뢰가 아니다

[MemRL](../reference/SOURCES.ko.md#ns63)의 관련성 뒤 효용 평가를 참고하여 실험할 수 있다. 효과 값은 성공 확률·진실 확률·권한이 아니다. 오래된 사실이 과거에 도움이 됐다는 이유로 주입하지 않는다. 선택하지 않은 기억의 결과는 관측되지 않았으므로 0점 실패로 학습하지 않는다.

record에는 exposed/applied/outcome attribution, task family, baseline, sample count, uncertainty가 필요하다. 같은 프로젝트 변형을 독립 표본처럼 세지 않는다. on/off 무작위 통제나 paired 사례로 실제 효과를 확인한다. 데이터가 적으면 conservative/unknown이며 자동 전역 승격하지 않는다.

## 5. Lesson → skill 후보

사건의 expected_outcome, actual_outcome, phase, environment, user_change를 구분한다. 의도한 TDD red, 정상 취소, 올바른 권한 거부는 무조건 실패 학습이 아니다. 반복 사건은 원인 가설과 대안 설명으로 묶는다. 단일 심각 보안 사건은 반복을 기다리지 않고 revoke할 수 있다.

Lesson은 근거 ref를 가진 후보이며 바로 행동 지침이 아니다. 반복 lesson으로 skill을 만들 때 `add / refine / deprecate / merge` patch를 기존 id/revision에 적용한다. [ACE](../reference/SOURCES.ko.md#ns62)의 부분 수정 접근을 참고하되 모델이 core policy를 쓰게 하지 않는다.

## 6. Skill 유형과 lifecycle

Knowledge, Procedure, Workflow, Tool, Policy, Domain, Evaluation이라는 facet을 둔다. Policy skill은 정책 설명이지 권한 원장이 아니다. Evaluation skill은 사례 제안이지 hidden test·판정 기준 편집 권한이 아니다. Tool skill에 실행 스크립트가 있으면 텍스트만 바뀐 skill보다 높은 코드 변경 검토를 받는다.

필수 manifest: identity/version, owner/scope, applicability/exclusions, inputs/outputs, required tools/capabilities, resources hashes, dependencies, prohibited actions, evaluation set, migration/rollback, source/license. discovery에는 metadata만, 본문·resources는 필요할 때만 노출한다. 순환 dependency와 duplicate id는 거부한다.

상태는 `candidate → validated → evaluated → reviewed → approved → released → stale/deprecated/revoked`다. merge는 두 id의 근거와 반례를 보존한 새 후보이며, 근거가 약해졌다고 자동 삭제하지 않는다. decay는 재검증 우선순위이지 진실을 시간만으로 확정하는 알고리즘이 아니다. 사람의 삭제·scope 축소는 모든 projection보다 우선한다.

## 7. lane A/B 및 다음 작업 적용

A는 실행 의미를 보존하는 탐색 정책이며 replay가 지원하는 범위에서 선별한다. 새로운 행동 결과가 없으면 out_of_support이며 실패로 보정하지 않는다. B는 memory/skill/prompt/도구/코드/검증·workflow 의미 변경이다. 실제 baseline/candidate 재실행과 regression이 필수다.

승격은 artifact+policy+evaluation digest에 서명된 승인 후 active release CAS로 이뤄진다. 동시에 같은 parent를 전제로 한 두 후보는 두 번째가 재평가해야 한다. 이미 실행 중인 작업은 일반적으로 시작 release 유지; security revoke는 즉시 pause/새 context binding. 새 작업의 실제 input manifest와 결과가 새 release를 사용했는지 확인해야 3-4 완료다.

## 8. 잠재적인 자기강화 오류

사용자 수정 피드백은 현재 요구의 반영이지 모든 작업에 대한 보편 규칙이 아니다. reviewer 취향을 correctness oracle로 바꾸지 않는다. 후보 생성 에이전트가 test 데이터를 보고 반례를 삭제하거나, 검증을 생략하는 skill로 비용을 줄이면 hard fail이다. 모델에 따라 규칙을 분기하지 않고 동일 후보를 실행 조건별로 검증한다.
