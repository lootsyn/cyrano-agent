# 개발·테스트 실행계획 — 하위 구현 모델용

## 시작 조건

이 파일은 24개 기존 WP를 폐기하지 않는다. native 배치와 최신 평가15항목을 각 WP의 인수 조건으로 추가한다. `test-work-plan.json`의 TS00–TS11은 테스트 개발 순서이고 `execute_requires_wp`는 해당 제품 테스트를 실제 실행하기 위한 선행 기능이다. test를 먼저 작성하는 것과 제품 기능이 이미 있다는 것을 혼동하지 않는다. 설명만 있는 future helper를 import하거나 없는 test를 skip하여 PASS로 만들지 않는다.

모든 작업은 현재 source snapshot 확인→변경 범위·완료 조건→구체 계획→독립 AI 계획 리뷰→finding 수정·재리뷰→사람 승인/유효 개발 permit→허용된 수정→테스트→독립 코드 리뷰→보고 순서를 따른다. 아직 broker가 구현되지 않은 bootstrap에서는 외부 사람이 승인하고 sandbox/OS로 범위를 제한한다. 이를 CYRANO 자체 강제 완료라고 보고하지 않는다. 실제 강제 기능 완성 후에는 모든 coding path에서 승인 없이는 mutation이 발생할 수 없음을 테스트한다.

## Wave 0 — 저장소·정책·데이터 계약

TS00와 WP00: fresh monorepo checkout의 HEAD와 pyproject project.name, sibling dependencies를 검증한다. dry-run overlay 후 변경 경로·source map을 리뷰한다. native Ruff/ty scope와 optional mypy/Black adapter 정책을 ADR로 승인한다. 실제 버전·lock·python patch·OS·도구 --version·wheel/import 경로를 `evidence/runtime-lock.json`에 기록한다. legacy standalone uv.lock을 사용하지 않는다.

TS01와 WP01/02: `AssessmentSession`, `CaseAttempt`, `ArtifactReceipt`, `AtomDecision`, `AssessmentReport`를 공용 계약에 추가한다. 이름·필수 field·enum·extra field·strict bool/int/float·시간·digest·scope validation, foreign IDs, stale report, signed subject projection을 구현한다. 이벤트/상태/outbox/receipt를 같은 transaction으로 처리하는 crash/CAS 테스트를 먼저 쓴다.

완료 증거: schema positive/negative, canonical digest vectors, no-read-before-ACL, stale/revoked/mismatched receipt 거부. malformed 입력을 빈 dict나 PASS로 fallback하지 않는다.

## Wave 1 — Python QualityRunner

TS02/TS03와 WP06: source inventory(.py/.pyi/critical public/private symbols)→immutable snapshot→rendered policy→pinned toolchain→argv factory→runner→parser→baseline→registered report→completion reducer 순서로 구현한다.

`discover_python_inventory(snapshot, policy) -> PythonInventory`: paths와 exclusions, changed files, major functions를 반환한다. empty scope·숨겨진 파일·symlink·비UTF8/Unicode 충돌은 명시 blocker다. `.gitignore`가 검사 scope를 줄일 권한은 없다.

`run_check(CheckSpec, SnapshotHandle, Toolchain, Cancellation) -> ToolReceipt`: shell=False, 절대 도구 경로, whitelist env, stdout/stderr 동시 drain, 각 stream cap10MiB, timeout 후 process group 종료·5초 grace·kill·남은 child cleanup. 시간은 monotonic, 생존 child나 missing output은 ERROR다.

`parse_tool_result(receipt, parser_version) -> CheckResult`: 실제 exit와 JSON/raw diagnostic의 의미가 맞는지 검사한다. Ruff format exit semantics는 고정 버전 fixture를 확보한다. Ruff check exit0+빈 valid diagnostics만 성공, unknown version/JSON 오류는 ERROR다. 외부 Black adapter는 exit1=violation,123=tool error를 검증한다. ty/mypy/Pyright는 각 parser schema fixture를 별도 소유한다.

`compare_baseline(before, after, permit) -> BaselineComparison`: 동일tool/policy/파일 bytes의 exact diagnostic multiset만 미수정파일에서 차감한다. 같은 개수의 새로운 오류, 수정파일의 과거 진단, pytest 실패 baseline은 거부한다.

`register_quality_report(auth, draft) -> RegisteredReport`: candidate의 로컬 report JSON을 믿지 않고 trusted runner channel을 요구한다. `request_completion(auth, report_id, expected_revision)`은 현재source·plan·review·policy·permit·revocation을 CAS로 다시 검사한다.

TS03는 semantic review fixture를 만든다. 틀린 Args/Returns, 의미 없는 docstring, stale 보안 주석, private rename을 넣는다. LLM reviewer는 근거 심볼·설명·제안 수정·confidence·unknown을 반환하고 auto doc coverage와 별도 판정한다. 1-3을 docstring 존재 개수만으로 합격시키지 않는다.

## Wave 2 — 인터뷰·계획·강제 경계

TS04/TS05와 WP03/08/09/10: 기존 R01–R22와 R3 2-x 사례를 연결한다. `compile_requirements`, `compile_plan`, `review_plan`, `resolve_finding`, `authorize_plan`, `dispatch_work`의 입력 revision을 하나의 approved subject로 결속한다. UI에서 승인 버튼을 눌렀다는 사실과 모델이 approved JSON을 출력한 것을 구분한다.

실제 AI plan reviewer 호출은 작성자 context와 분리한다. critical flaw가 포함된 계획에 review finding이 생성되고 수정된 plan V2에 반영된 후 새로운 review가 있어야 한다. 같은 모델을 사용할 수 있지만 별도 attempt/context·입출력과 실패 상태를 기록한다. 독립 context만으로 reviewer가 항상 맞는다는 주장은 금지한다.

권한 tests는 허가 없는 edit뿐 아니라 execute/MCP/child/YOLO/headless/ACP/resume/symlink/hardlink에 대해 파일이 실제로 변하지 않았음을 확인한다. 동작을 테스트하려고 production filesystem 권한을 풀지 않는다. mode가 미지원이면 launch deny 사례로 별도 표시하고 지원 matrix를 축소하되 요구 미충족을 공개한다.

## Wave 3 — Memory 실제 활용

TS06와 WP11/12: 새 process A/B fixture, persistent store, retrieval index, ACL-before-rank, freshness, deletion, projection pin을 구현한다. plan/code의 applied predicate는 케이스별 oracle가 소유한다. 회고 텍스트에 memory ID를 썼다고 applied=true를 만들지 않는다. noise·conflict·stale·malicious memory test를 정상 흐름과 함께 둔다.

`collect_memory_use(run_id) -> MemoryUseEvidence`는 각 queried/selected/injected/referenced/applied 단계의 artifact와 plan/code/test delta를 연결한다. 현재 view가 `release_digest`와 다르면 run context를 재바인딩 또는 차단하고 조용히 최신 memory로 갈아끼우지 않는다.

## Wave 4 — 자기개선 전후 검증

TS07/TS08와 WP15/16/17/18/19/20/21: episode의 expected/actual/phase를 보존해 원인 가설을 만들고 LearningWorkPlan을 리뷰한다. system prompt 허용 블록, skill, memory, code proposal 네 표면을 각각 시험한다. system prompt 안전/권한 core는 보호한다.

`classify_candidate(base, patch, dependencies)`는 모델의 scheduling_only 선언이 아니라 실제 input impact로 A/B를 분류한다. `run_paired_trials`는 predeclared family/split/budget/seed 가능한 조건을 고정한다. `evaluate_effect`는 improvement·noninferiority·inconclusive·hard fail을 분리한다. `promote`는 parent CAS와 current signed evaluation을 요구한다.

실제 다음 업무에서 새release가 사용되는지 검증하고 old running task pin을 확인한다. promotion 실패·효과 불명·비밀 유출·canary 회귀는 점수 상승으로 상쇄하지 않는다. package code 변경은 독립 CI/wheel/install/runtime test를 거치며 실행 중 Python 파일을 덮어쓰지 않는다.

## Wave 5 — 관측·조회·출시 판정

TS09/TS10과 WP13/14: native provider adapter·tool wrapper·memory service·improvement service·broker event를 실제로 연결한다. summarizer/classifier/grader/child는 separate coverage row를 만들고 native cost accounting와 중복을 피한다. FakeClock와 deterministic provider sequence로 retries=attempts-1을 해당 layer에서 검사한다.

조회 fixture는 세 원인(승인누락, pytest실패, provider timeout)과 unknown worker loss를 제공한다. UI/CLI에서 각각 실패 span과 raw evidence, remedial owner를 식별한다. telemetry gap·redaction·ACL·pagination·SSE 재연결도 검사한다. causal parent가 없는 것을 timestamp sorting으로 감추지 않는다.

TS11와 WP22/23: source-native upstream regression과 CYRANO suite를 모두 실행하고 signed results를 aggregate한다. upstream official tests가 못 돌았으면 개발 준비 PASS와 별개 blocker다. 실제 CI job required-check 설정·skip/cancel·merge 차단 여부는 운영 권한으로 확인해야 한다. 로컬 YAML 파일 존재는 branch protection 설정 증거가 아니다.

## 완료 보고 형식

각 TS/WP report에는 source/plan/policy/runtime/suite digest, 변경파일, exact argv·cwd·env recipe, 시작/종료·exit, 실제 수집/실행/skip/xfailed/deselected node IDs, test별 verdict·raw refs, review/finding 상태, blocked 이유, 알려진 부작용·cleanup, 다음 선행관계 영향을 남긴다. 수정한 후에는 해당 postimage 기준으로 tests·review를 다시 한다. 통과한 다른 snapshot 증거를 인용하지 않는다.

계획→리뷰→실행의 이 프로세스를 실제 제품에서 강제할 수 있어야 2번 평가 항목을 획득한다. 이 문서를 읽고 수동으로 지켰다는 bootstrap 기록은 개발 이력으로 유용하지만 enforcement 제품 평가를 대신하지 않는다.
