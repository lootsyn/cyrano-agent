# 평가 3-3·3-4 · 자기개선 제안·실제 평가·다음 작업 반영

문서 유형: 목표 상세 설계. 상태: planned. 기존 경로 A/B의 기능을 축소하지 않는다. 3-3은 근거 기반 개선안 생성, 3-4는 전후·회귀 검증을 통과한 변경이 다음 작업에 실제 사용된 사실을 요구한다. 소유 WP14–WP21, RC33–RC36.

## 1. 개선 loop를 운영 loop에서 분리

업무 run은 시작 시점 `HarnessRelease`와 `MemoryRelease`를 고정한다. `after_model`에서 재귀적인 reflection/LLM 호출을 하지 않는다. terminal event와 동일 transaction으로 `(run_id, terminal_event_id, learning_policy_digest)` unique outbox job을 생성한다. 별도 worker가 짧은 lease/fencing token·max attempts·deadline·token/금액 예산으로 작업한다. learning job 실패는 이미 검증 완료된 업무 결과를 뒤집지 않지만 학습을 완료로 표시하지 않는다.

agent는 author·critic·generator 역할만 수행한다. 평가기와 승인 broker는 별도 principal, immutable sealed dataset과 verdict를 소유한다. 독립 reviewer는 같은 모델 사용 가능하지만 작성자 conversation/hidden chain-of-thought를 그대로 읽어 스스로 통과시키는 세션이 아니다. 역할 분리 자체를 정확성 보장으로 표현하지 않고 실제 검증을 추가한다.

## 2. 후보 계약과 함수

`Candidate`는 ID, parent release, source episodes/evidence, hypothesis, alternative_causes, scope, surface, exact artifact patch, patch digest, prerequisites, risk, expected_effect, counterexamples, evaluation_manifest, preregistered thresholds, budget, rollback target, approval requirement, creator identity, revision을 갖는다.

| 파일 | 함수·반환 | 책임 |
|---|---|---|
| `improvement/episodes.py` | `settle_episode(run_id) -> Episode` | outcome classification, redaction, source completeness |
| `improvement/analysis.py` | `analyze(episode_refs) -> HypothesisSet` | evidence-backed causal hypotheses와 반례; model 출력 strict validation |
| `improvement/workplan.py` | `compile_learning_plan(hypothesis) -> LearningWorkPlan` | 실험 변경범위·data split·비용·리뷰·실패 처리 |
| `improvement/candidates.py` | `propose_candidate(plan, patch) -> Candidate` | 불변 patch와 parent/plan 결속 |
| `improvement/impact.py` | `classify_diff(candidate, dependency_graph) -> ImpactReport` | generator 주장과 독립적으로 실행 의미 분석 |
| `evaluation/paired.py` | `evaluate_pair(baseline, candidate, manifest) -> EvaluationReport` | 동등 조건 paired 실제 replay가 아닌 실행, 비용·outcome 추적 |
| `evaluation/gates.py` | `decide_promotion(report, policy) -> PromotionVerdict` | hard fail 우선; pass/inconclusive/reject; LLM 임의 판정 금지 |
| `kernel/releases.py` | `promote(candidate_id, expected_parent, approval) -> HarnessRelease` | scope·proof·approval 검증, release pointer CAS |
| `kernel/rollout.py` | `bind_release(run, cohort_policy) -> ReleaseBinding` | 승인된 rollout에서만 새 run에 배포 |
| `kernel/recovery.py` | `revoke_or_rollback(release, cause) -> RollbackReceipt` | dispatch 중지·영향 run·관련 memory/코드 상태 구분 |

## 3. 표면별 실제 변경과 평가

| surface | candidate에 저장할 patch | 평가와 반례 | 배포 단위 |
|---|---|---|---|
| `system_prompt` | 승인된 절차 block의 변경. 보안 root·user intent·approval 지침 변경은 protected | 고정 tasks에서 correctness/false-ready/intent/지침 누락 비교 | prompt component digest + context epoch |
| `skill` | SKILL.md·resources·metadata graph. script가 바뀌면 code 변경 추가 분류 | activation/no-activation·관련/비관련 tasks·필수 check 유지 | immutable skill artifact |
| `working_memory` | 현재 task note의 후보 revision. 전역 scope 자동 승격 금지 | 같은 episode 새 branch 실제 실행; 현재 승인 의무 불변 | task-scoped new revision |
| `semantic_memory` | 명시 근거·dependency·scope의 사실 후보 | 사실 재검증, 충돌·stale·다른 workspace 반례 | memory release |
| `procedure_memory` | 실패 원인·적용 조건·검증 recipe | on/off 실제 비교; 잘못된 적용·과도한 일반화 반례 | memory+skill bundle |
| `interview`, `plan`, `review` | 질문/순서/분해/리뷰 procedure patch | 질문 수보다 false-ready·coverage·defect detection·false-block 우선 | workflow config/skill |
| `context_config` | recall/compaction/offload/budget 변경 | 의무 보존·actual context·정확도+캐시 측정 | context component |
| `verification_recipe` | 준비/명령/대상/환경 patch | 결함 검출/오탐/flake; 실패 test 삭제·oracle 약화 금지 | signed recipe |
| `extension_code_proposal` | Cyrano source diff+dependency/build plan | CI·native import·build·fresh install·migration·rollback+live pair | 새 package/runtime |
| `search_policy` | 허용 feature와 bounded IR | 과거와 입력 의미 같을 때만 A replay; out_of_support 실제 실행 | policy artifact |

mixed change는 가장 강한 경로(B/protected)로 간다. tool schema, prompt, memory, dependency, model/endpoint, environment가 바뀌면 `scheduling_only`를 주지 않는다. 분류 불명은 transition_changing으로 처리한다. 경로 A는 기록에 없는 결과를 추측하지 않으며 미래 branch 결과를 정책 입력에서 분리한다.

## 4. 학습계획의 허가

learning plan 승인과 promotion 승인은 다르다. 전자는 주어진 dataset·scope·예산의 sandbox 실험을 허용하고 후자는 특정 검증된 artifact를 실제 후속 작업에 배포하도록 허용한다. 사람의 사전 위임이 있는 경우에도 surface/scope/risk/budget/expiry를 좁게 고정한다. 정책, 승인 trust root, evaluator, holdout, audit 보존, 보안 임계치는 일반 자동 승격 대상이 아니다.

patch나 parent digest, data manifest, threshold를 바꾸면 기존 plan review/평가/promotion approval을 무효화한다. 후발 후보가 오래된 parent 기준에서 이겼더라도 현재 release 위로 자동 병합하지 않는다. rebase 후 영향에 맞는 재평가가 필요하다.

## 5. 평가 데이터·실행·판정

split 단위는 repository/task family와 시간이다. 같은 issue의 변형, clone, 인접 commit, 같은 인터뷰 대화는 같은 family다. sealed 평가 정답은 learning worker에 노출하지 않는다. 반복적으로 sealed feedback으로 후보를 조정하면 평가 세트를 소진/교체하며 최초 계획의 최대 조회 횟수를 넘길 수 없다.

각 pair는 같은 task/spec/source snapshot/runtime/model endpoint/budget/allowed tools/memory release에서 실행하고 candidate surface만 바꾼다. provider nondeterminism 때문에 seed를 고정해도 동일 출력이 보장된다고 쓰지 않는다. 실행 순서를 randomize하고 independent family별 paired difference를 통계 단위로 사용한다. cancellation·실패·환경 오류·사용자 변경을 분리하며 유리한 표본만 삭제하지 않는다. 제외 사유는 pre-register한다.

품질 개선형은 quality difference의 사전 정의 최소 개선과 비용/latency ceiling을 모두 통과한다. 효율 개선형은 correctness non-inferiority의 CI가 사전 margin을 만족하면서 비용 또는 지연이 유의미하게 개선되어야 한다. 표본 최소 수는 검정력 계획으로 정하며 20 family×3 반복 예시가 보장을 의미하지 않는다. hard violation이 한 건이라도 있으면 평균 효율로 상쇄하지 않는다. 표본 부족·오차 범위·불완전 usage는 `inconclusive` 또는 `invalid`, success가 아니다.

`EvaluationReport`는 per-case outcome/raw artifacts, measured scope, runtime/source/policy/suite digest, order/seed when available, sample family IDs, confidence method, baseline/candidate metrics, cost of learning, excluded cases and reason, safety regressions, reviewer evidence를 보존한다. native LLM rubric self-evaluation만으로 완성 판정하지 않는다.

## 6. 다음 작업 반영의 증명

3-4 통과 증거는 다음 연결을 모두 포함한다.

`Candidate -> EvaluationReport -> IndependentReview -> PromotionApproval -> HarnessRelease -> new RunBinding -> ContextManifest/ToolInventory -> 실제 행동 -> regression result`.

새 release가 파일로 존재한다는 사실은 적용 증거가 아니다. process B/new thread에서 새 binding이 실제 chosen artifact digest와 같고, 기존 run A는 보안 revoke가 아닌 일반 승격에서 이전 binding을 유지하는지 검사한다. context/skill 실제 로딩을 관측할 수 없으면 반영 결과는 `unverified`. 감사 지표는 release 생성 수와 다음 업무 적용 수를 구분한다.

## 7. canary·rollback·비용

기본 learning/live/canary/자동 승격은 꺼져 있다. 승인된 canary는 새 run에만 적용하며 control cohort와 task family의 불균형을 기록한다. 순차 중간 검정의 기준을 매일 유리하게 바꾸지 않는다. hard incident는 즉시 신규 dispatch 중지와 revoke; 품질 경고는 preregistered 기준으로 평가.

rollback은 immutable 이전 component pointer를 되돌리고 영향 run을 표시한다. 사용자 코드 변경이나 irreversible DB migration을 되돌렸다고 주장하지 않는다. code 후보는 expand/contract migration과 이전 런타임 read compatibility 또는 명시 restore path가 없으면 승격 차단한다.

`net_saving = 업무 기준안 예상 비용 - 후보 실제 업무 비용 - 분석/생성/replay/실제 eval/review/운영 추가 비용`을 provenance 포함해 보고한다. 실측 아닌 baseline 추정은 proxy로 표시한다. 후보 생성 1회가 연쇄 무한 개선을 시작하지 않게 depth/job budget/max candidates를 제한한다.

## 8. 상세 수용

RC33–RC36에 정상·회귀·거부·inconclusive·동시 승격·next-run binding·crash/recovery 시험을 둔다. 절차·system block·skill·working memory를 각각 하나 이상 실제 후보로 평가한다. task 성공을 위한 보호 지침 약화, hidden test 변조, 인증된 reviewer 사칭은 명시 hard fail. 관련 작업 파일과 실행 프로토콜은 [개발계획](../development/MEMORY_OBSERVABILITY_PLAN.ko.md), [실행계획](../execution/MEMORY_OBSERVABILITY_RUNBOOK.ko.md).

## R5 구현 연결

typed entry delta·durable consolidation·actual ablation 계약은 [R5 소유 상세 설계](ADAPTIVE_MEMORY_AND_SKILL_EVOLUTION.ko.md)에서 구체화한다. 기존 scope·승인·실제 검증은 유지하며 skill 설정만으로 해당 기능을 구현하지 않는다.

## 개발 과정 자체에 대한 개선 한계

개선 모델은 인터뷰 질문 선택·review checklist·역할별 context·bounded retry를 제안할 수 있으나 필수 인터뷰, 독립 검토, 목적별 승인, 적용 전 허가, oracle·audit·redaction을 자동 약화할 수 없다. 사용자의 '계속 진행'을 매 실험·외부 호출의 새로운 무제한 동의로 사용하지 않는다.

결과 누락·모델 거부·cancel·환경 timeout과 correctness fail을 구분한다. 정상적인 권한 거부와 TDD red는 잘못된 행동의 lesson이 아니다. 비교 실험의 동일 task-family·source·runtime·scope·비용 상한을 고정하고 task를 성공 표본으로만 다시 선택하지 않는다. task/model별 seed가 지원되지 않으면 seed 제어 불가를 명시한다.

배포 후보가 현재 prompt/skill과 같아도 사용 중인 role/tool/config가 달라졌으면 새로운 평가 조건이다. 최소 유의 개선, 비열등성 허용폭, 통계적 불확실성·표본 부족 규칙은 실험 전에 명시한다. 모든 안전 실패는 비용 절감과 합산하지 않는다. 운영자가 허용한 작은 scope로만 canary하고 다음 작업에서 실제 release 사용을 확인한다.
