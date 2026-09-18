# UDH: dcode 기반 범용 개발 Harness 상세 설계

문서 버전: 1.0.0-design • 기준일: 2026-09-15 (Asia/Seoul)
상태: **구현 명세**. 제품 구현, dcode 실연동, 실제 모델 실행 및 성능 검증이 완료되었다는 뜻이 아니다.

## 0. 이 문서의 계약

UDH(Universal Development Harness)는 이 문서에서 새로 정의한 구성 요소의 이름이다. `udh` 명령, `udh.*` 이벤트, `udh_harness` 패키지, 여기서 정의한 YAML/JSON 필드는 **개발할 인터페이스**이지 dcode가 이미 제공하는 기능이 아니다. dcode의 기존 기능은 [S01]–[S12]와 구분하여 표시한다.

MUST는 필수, MUST NOT은 금지, SHOULD는 사유를 기록해야 예외를 둘 수 있는 기본값이다. 예산·용량·성능 목표의 숫자는 초기 운영 정책이며 실측 최적값이 아니다. 구현 단계가 여러 개여도 최종 기능을 축소하지 않는다. 부분 구현은 해당 단계의 완료일 뿐 전체 요구사항 충족이 아니다.

### 0.1 요구사항 해석

제외하는 것은 **모델 이름·계열에 따라 자체 프롬프트, 능력 점수, 라우팅 정책을 만드는 특화 계층**이다. 제거하지 않는 것은 인터뷰, 계획·다중 리뷰, 작업 프로필, 서브에이전트, 컨텍스트 최적화, 캐시 측정, 적극적인 기억 활용, 자동 개선 후보 생성·평가, 승인·권한 강제, 전체 작업 관측과 복구이다.

대상 프로젝트에는 설치를 위해 `.deepagents/`, `.agents/`, 설정 파일, SDK 의존성을 생성하지 않는다. dcode core도 수정·fork·monkey patch하지 않는다. UDH 자체 Python 패키지, 사용자 프로필, 외부 상태 저장소, 격리 실행 환경은 별도로 개발한다. 이후 사용자가 개발을 승인한 범위의 소스 변경은 허용되는 업무이며, **설치 비침습성**과 **승인된 개발 변경**을 혼동하지 않는다.

### 0.2 요구사항 ID

| ID | 요구사항 | 반드시 남겨야 할 증거 |
|---|---|---|
| BASE-01 | dcode 사용, core 무수정 | 배포 패키지 해시·버전, 어댑터 검사 |
| BASE-02 | 대상 저장소 설치 오염 없음 | 설치 전후 tracked/untracked 파일 manifest 비교 |
| GEN-01 | 모델 비특화 | 모델별 자체 분기 없음, 교체 회귀 검사 |
| CACHE-01 | 캐시 친화적 컨텍스트 | 안정 블록 digest, 변경 이유, 실제 usage 구분 |
| PROFILE-01 | 충분한 작업·위험도 프로필 | 프로필 스키마, 권한 교집합, 단계별 검토 |
| INT-01 | 첨부 Decision Interview 통합 | 원본 R01–R22 및 확장 회귀 검사 |
| PLAN-01 | 구현 전 상세 계획·리뷰·승인 | 요구↔작업↔검증 추적표와 승인 receipt |
| MEM-01 | 적극적·범위화된 Memory | 조회·주입·사용·효과를 구분한 이벤트 |
| LEARN-01 | Middleware 기반 Self-Improving | 관측→후보→평가→승인→배포→롤백 이력 |
| OBS-01 | 개발 전 과정 모니터링 | 전 단계 timeline, 호출 트리, 누락 감지, 보고서 |
| PY-01 | Python PEP8 및 일반 품질 기준 | formatter/lint/type/test/검토 증거 |
| AUTH-01 | 승인·권한·비밀 분리 | 위조·만료·재사용·우회 실패 검사 |
| REL-01 | 중단·동시성·재개·버전 일관성 | crash/replay/CAS/idempotency/lease 검사 |
| EVAL-01 | 기능·효과·회귀 평가 | 실행된 검사와 미실행 명세의 분리 |

추가 평가 항목의 `[10]`은 항목당 최대 10점, 총 40점의 **증거 기반 평가표**로 해석한다. 이 설계 문서가 있다는 사실만으로 40점을 부여하지 않는다. 배점과 판정식은 품질·평가 장에 정의한다.

## 1. 확인된 dcode 범위와 구현 경계

### 1.1 조사 사실

공개 `libs/code/pyproject.toml`의 조회 내용은 `deepagents-code` 0.1.69, `deepagents==0.7.14`, Python `>=3.12,<4.0`를 표시한다. 이는 조회된 main 문서의 내용이고 사용자 설치 버전이나 배포 파일의 검증 결과가 아니다. 과거 대화의 버전 수치를 고정값으로 사용하지 않는다. 첫 구현 작업에서 실제 설치 조합을 고정해야 한다. [S09]

공식 Python 확장은 `DEEPAGENTS_CODE_EXPERIMENTAL=1`을 요구한다. 등록 표면은 middleware, tool, backend route, shutdown callback이다. 사용자 영역 파일 또는 버전 있는 plugin으로 배포할 수 있다. **커스텀 slash command 등록은 이 API에 없다.** middleware·backend 변경은 서버 rebuild/restart를 고려해야 한다. [S01]

공식 hooks는 lifecycle shell 실행이다. handler의 일반 오류와 timeout을 곧바로 안전한 차단으로 볼 수 없고, 여러 handler가 동시에 실행될 수 있다. 따라서 UDH의 승인·원장·정책은 hook stdout이나 exit code 하나만으로 보호하지 않는다. [S02]

SDK의 memory/backend/skills 기능과 실제 dcode loader는 구분한다. virtual route를 추가한다고 built-in `AGENTS.md`가 그곳으로 이동하지 않으며 shell도 virtual file route를 자동으로 볼 수 없다. 이에 따라 UDH는 **memory 저장·선택·노출·쓰기 승인**을 별도 계약으로 구현한다. [S01][S03]

### 1.2 지원 상태 표

| 표면 | 판정 | UDH 사용 방법 |
|---|---|---|
| 사용자 Python extension | 문서상 제공, experimental | 얇은 `extension(d)`로 middleware/tools 등록 |
| 사용자 프로필 root | `DEEPAGENTS_HOME` 문서상 제공 | 외부 전용 root, 대상 repo 아래 지정 금지 |
| LangChain middleware | 문서상 제공 | 상태·모델·도구 경계에 관측/제약 추가 |
| hooks | 문서상 제공 | client lifecycle 보완, 비권위적 알림 |
| 내장 skills/subagents | 문서상 제공 | 범용 역할·절차, inheritance는 실제 테스트 |
| 신뢰된 외부 승인 발급 | UDH 개발 대상 | 별도 승인 UI/CLI와 Broker |
| 작업 상태기계·계획 강제 | UDH 개발 대상 | deterministic kernel |
| 모델별 benchmark/profile DB | 의도적 제외 | 없음 |
| 모든 tool 경로의 강제 통제 | 어댑터+격리 검증 필요 | 통과 못 하면 governed 실행 금지 |
| 모든 provider의 prompt-cache | 보편 보장 불가 | 지원하는 native integration만 활용, 나머지 unknown |
| 수정 없이 TUI 전체 교체 | 요구 범위 아님 | dcode TUI 유지, 외부 dashboard 병행 |

### 1.3 CompatibilityReport

`udh doctor`는 모델 지능 평가가 아니다. 다음 연결 계약을 검사한다: 설치 버전/해시, extension 로딩, 실험 플래그, root 해석, async middleware 호출, sync 테스트 호출, 모델/도구 이벤트 관측, 서브에이전트의 동일 정책 적용, 실제 도구 이름, virtual route, shutdown, headless 출력, context mutation 결과, 승인 우회 차단, sandbox 경계.

각 항목은 `verified / unsupported / failed / not_tested` 중 하나다. `not_tested`를 true로 만들지 않는다. `governed` 실행은 모든 필수 항목이 verified일 때만 허용한다. 미지원 버전을 조용히 fallback하거나 별도 SDK 에이전트로 갈아끼우지 않는다. 호환되는 dcode 릴리스로 운영자가 명시적으로 변경하거나 조사 전용 상태에서 차단 사유를 표시한다.

## 2. 전체 아키텍처

```text
사람 ───── dcode TUI (대화)                      사람 ─ 승인 UI/CLI
              │                                           │
         dcode server                               Approval Broker
              │                                           │
       UDH Python extension ── 제안/조회 ── Control Plane Kernel
              │                         ├─ Interview / Intent Ledger
       UDH Composite Middleware         ├─ Plan / Review / Authorization
              │                         ├─ Memory / Improvement / Evaluation
       Native Deep Agents harness       ├─ Event Store / Artifacts / Outbox
              │                         └─ Scheduler / Recovery / Dashboard
        임의의 호환 LLM                         │
              │                              Action Broker
     도구 호출 / 서브에이전트                    │
              └─────────────────────────── Sandbox Runner
                                                  │
                                    승인된 외부 작업 사본 / 테스트
                                                  │
                                    승인된 변경 패치 반영 게이트
                                                  │
                                            대상 프로젝트
```

모델은 제안자다. 승인·권한·완료 상태는 Kernel/Broker가 정한다. dcode를 버리고 자체 agent loop를 만드는 설계가 아니다. 모델 호출과 코딩 상호작용은 dcode/Deep Agents에 남겨두고, 업무 계약·권한·기억 수명주기·평가를 외부 control plane에 둔다.

### 2.1 세 영역

**Control plane:** 사용자 이벤트, 승인 발급, 정책, 상태 원장, 메모리 원본, 평가 판정, promotion pointer를 소유한다. 모델 도구에서 DB나 승인 키에 직접 접근할 수 없다.

**Agent plane:** dcode와 확장 모듈을 실행한다. 서명 검증용 공개키, 제한된 run token, 현재 작업의 최소 컨텍스트만 받는다. 일반 셸이 broker 관리 파일을 읽거나 수정할 수 없도록 격리한다.

**Execution plane:** 실제 명령·파일 변경·테스트를 수행한다. 작업별 ephemeral sandbox, 시간·메모리·네트워크·경로 제한을 적용한다. agent plane과도 권한을 구분한다.

소스 작업 사본의 유일한 writer는 Broker다. dcode native 파일·셸 및 테스트 runner에는 소스를 readonly로 제공하고, 임시 산출물은 별도 scratch에만 쓴다. 변경 tool은 Broker가 검증 후 수행하며 새 snapshot을 원자적으로 노출한다. 임의 실행 코드에 소스 디렉터리 전체를 writable mount한 뒤 사후 diff만 검사하는 구성은 새 파일 생성·승인 범위의 강제 보장을 충족하지 않는다. 테스트 실행을 위해 소스 쓰기가 불가피하면 그 파일과 부작용을 명시 승인한 별도 recipe가 필요하며 원본 저장소는 여전히 격리한다.

같은 OS 사용자 권한의 Python 프로세스 두 개로 나눈 것만으로 비밀·승인 경계가 생기지 않는다. `governed`는 다른 OS principal 또는 VM/container 경계를 필수로 요구한다. 로컬 단일 사용자 환경의 비격리 구동은 `advisory`로 표시하며 승인 위조 방지·우회 차단 보장을 주장하지 않는다.

### 2.2 배포 등급

| 등급 | 용도 | 보장/제한 |
|---|---|---|
| advisory | 개발·관측 연결 확인 | 기록/지침은 가능, 강제 보안 보장 없음 |
| governed | 전체 요구사항의 목표 운영 | broker+격리+원장+필수 어댑터 검증 |

등급은 기능 축소용 플래그가 아니다. 전체 요구사항 출시 판정은 governed에서만 수행한다. governed를 선택했는데 연결이 실패하면 advisory로 자동 전환하지 않는다.

## 3. 외부 파일·환경 구조

```text
~/.local/share/udh/
  control/                     # Agent/테스트 프로세스에 mount하지 않음
    state.sqlite3
    blobs/                     # digest 기반 immutable artifact
    memory/                    # 정규화된 기억·승격 release
    policies/                  # 사람 승인된 policy revision
    approvals/                 # 검증/철회/표시 이력
    releases/                  # content-addressed harness releases
    runbooks/
  runtimes/<runtime-id>/
    deepagents-home/            # 전용 DEEPAGENTS_HOME, 비밀 없는 런타임 투영
      config.toml
      extensions/udh_entry.py
      agent/AGENTS.md           # 실제 loader 경로 doctor로 확인
      agent/skills/             # 동일하게 loader와 일치 검증
    workspace/                 # 대상 저장소 외부 작업 사본
    scratch/
  exports/<session-id>/
  quarantine/

~/src/udh-harness/              # UDH 자체 개발 저장소, 대상 제품 저장소와 분리
  pyproject.toml
  uv.lock                      # 실제 dependency resolution 후 생성
  src/udh_harness/
  tests/
  config/
```

경로는 UDH 소유 디렉터리의 예시다. 특정 dcode 버전이 `agent/skills` 이외 경로를 탐색하면 adapter가 verified path에 투영한다. 같은 skill을 여러 검색 경로에 중복 설치하지 않는다. loader 경로를 추정으로 강제하지 않는다.

### 3.1 WorkspaceIdentity와 스냅샷

`workspace_id`는 등록된 저장소의 임의 UUID다. 같은 이름의 폴더를 같은 프로젝트로 취급하지 않는다. 저장소 위치, 정규화 경로, repository identity, 작업 사본 ID는 control plane에 보관하며 telemetry의 공개 label로 내보내지 않는다.

Snapshot manifest에는 관련 tracked·허용된 untracked 파일의 상대 경로, type, byte hash, mode, 크기, Git HEAD(있다면), dirty 여부, 캡처 범위를 포함한다. `.env`, private key, credential, 원본 운영 데이터는 기본 제외다. HEAD만 같다고 파일 내용이 같다고 판단하지 않는다.

설치·조사 단계는 원본 저장소 파일을 수정하지 않는다. `git worktree add`도 원본 Git metadata를 바꾸므로 엄격한 비침습 설치 검사의 우회로 쓰지 않는다. 기본은 외부 snapshot copy다. 개발 실행은 외부 working copy에서 진행하고 최종 patch를 원본 preimage와 비교한 후 별도로 반영한다. 원본에서 직접 개발하려면 사용자가 그 실행 위치와 범위를 명시적으로 승인해야 한다.

### 3.2 초기 환경 고정

Python은 UDH 자체에 3.12 이상을 사용하되, 대상 프로젝트의 interpreter를 바꾸지 않는다. dcode와 extension은 동일 런타임에서 import 가능해야 한다. 별도 개발 venv에만 패키지를 설치하고 dcode 실행 venv에는 설치하지 않는 실수를 doctor에서 잡는다.

설치 산출물은 `runtime-lock.json`: Python 실제 버전, dcode/SDK/LangChain/extension distribution 버전·해시, 공개 extension 시그니처, tool inventory digest, dependency lock digest, OS/sandbox image digest이다. 이 문서에는 실행하지 않은 dependency resolution 결과나 가짜 `uv.lock`을 넣지 않는다.

## 4. 핵심 도메인과 단일 진실 원천

첨부 `source_interview/`의 모델과 권위 규칙을 계승한다. 원본 v1 스키마는 보존하며, 개발 단계용 객체를 추가한다.

| 객체 | 내용 | 누가 확정하는가 |
|---|---|---|
| UserEvent | 사용자 원문·표시 대상·출처 | trusted host channel |
| IntentItem / Decision | 원하는 결과·범위·선택·위임 | 실제 사용자 또는 검증된 위임 |
| Evidence | 관측 위치·발췌·snapshot·신선도 | 수집기가 기록, 진실 여부 별도 검토 |
| Obligation / Scenario | 적용 의무·관찰 가능한 합격 조건 | 계약 검토 및 권한 검증 |
| ContractBundle | 요구·범위·시나리오의 immutable bundle | compiler; 승인은 별도 |
| WorkPlan / WorkUnit | DAG·파일·명령·테스트·복구 | planner 제안→검토→승인 |
| ReviewReport | 대상 digest·findings·검토 범위 | reviewer 결과, kernel가 readiness에 반영 |
| ApprovalReceipt | 정확한 작업·bundle·scope·expiry | Approval Broker만 발급 |
| ExecutionPermit | 승인에서 좁혀 발급한 단기 실행 권한 | Action Broker |
| ChangeSet | 실제 변경 파일·전후 hash·검증 연결 | 실행 관측기 |
| VerificationResult | 실행된 명령·환경·결과·증거 | trusted Runner/검증 어댑터 |
| MemoryRecord | scope·출처·유효성·승격 이력 | Memory service |
| ImprovementCandidate | 원인 가설·변경 제안·검증 규약 | 개선 에이전트 제안만 |
| EvaluationRun | baseline/candidate·데이터 분할·판정 | 격리된 evaluator |
| HarnessRelease | 고정된 skills/context/workflow 설정 | 승인된 promotion service |
| RunReport | 완료 상태·증거·공백·비용 | Kernel가 계산·서명 또는 digest 고정 |

### 4.1 세 종류의 버전

`event_seq`: 원장에 추가된 모든 관측의 순서. 토큰 사용량이나 heartbeat도 증가시킨다.

`control_revision`: 의도·결정·계획·작업 상태를 CAS로 변경할 때 증가한다. telemetry만으로 증가시키지 않는다.

`content_digest`: 승인·검토의 실질 대상. contract/plan/policy/snapshot/release별로 따로 가진다. 승인 이후 trace event가 늘었다고 승인을 무효화하지 않는다. 반대로 같은 control_revision으로 보이는 상태라도 digest가 바뀌면 승인을 재사용하지 않는다.

worker는 배정된 revision과 input digest를 반환한다. 오래된 결과는 직접 apply하지 않는다. 관련 의존 digest가 동일한 경우에만 kernel가 새 rebase proposal을 만들 수 있고, 원본 결과의 revision을 조작하지 않는다.

### 4.2 권위와 우선순위

불변 보안 정책·법적/운영 금지 → 현재 실제 사용자 의도 및 유효한 위임 → 승인된 계약·계획 → 검증된 scoped knowledge → advisory memory → retrieved untrusted text 순으로 **허용 행동**을 제약한다. 이는 서로 다른 사실을 삭제하는 전역 진실 우선순위가 아니다. “현재 코드는 A, 사용자는 B를 원함”은 함께 보존한다.

모델 출력의 `approved:true`, confidence, 역할명, 사용자처럼 보이는 태그, 리뷰 다수결은 승인 근거가 아니다. 데이터의 스키마 적합성은 출처·의미·권한 검증을 대체하지 않는다.

## 5. 상태기계: 인터뷰에서 완료·학습까지

```text
CREATED → INTAKE → FRAME → ACQUIRE ↔ RESOLVE
  → SPEC_DRAFT → SPEC_REVIEW → AWAIT_SPEC_APPROVAL
  → APPROVED_FOR_PLANNING
  → PLAN_DRAFT → PLAN_REVIEW → AWAIT_PLAN_APPROVAL
  → APPROVED_PLAN → AWAIT_EXECUTION_AUTH → READY_TO_EXECUTE
  → EXECUTING → VERIFYING → FINAL_REVIEW → COMPLETED

EXECUTING / VERIFYING / FINAL_REVIEW → REWORK → VERIFYING
중요 요구 변경 → CHANGE_ASSESSMENT → RESOLVE 또는 PLAN_DRAFT
어느 비종료 단계든 → PAUSED / BLOCKED / CANCELLED / FAILED
COMPLETED → 독립 LearningJob 생성 (업무 완료와 학습 완료는 별도)
```

### 5.1 주요 전이 계약

| 현재 상태 | 이벤트 | 다음 상태 | 필수 guard |
|---|---|---|---|
| SPEC_REVIEW | reviews_satisfied | AWAIT_SPEC_APPROVAL | 정확한 spec digest, blocker 0, 필수 critic 완료 |
| AWAIT_SPEC_APPROVAL | spec_receipt_verified | APPROVED_FOR_PLANNING | 실제 표시·사용자 이벤트·서명·scope 일치 |
| PLAN_DRAFT | plan_submitted | PLAN_REVIEW | DAG 무순환, req/test/file 연결, budget/rollback 있음 |
| PLAN_REVIEW | reviews_satisfied | AWAIT_PLAN_APPROVAL | 모든 개발 작업의 독립 plan review 통과 |
| AWAIT_PLAN_APPROVAL | plan_receipt_verified | APPROVED_PLAN | 현재 spec/plan/snapshot/policy/release에 binding |
| APPROVED_PLAN | execution_requested | AWAIT_EXECUTION_AUTH | 권한 범위·새 파일 목록·명령을 표시 |
| AWAIT_EXECUTION_AUTH | execution_receipt_verified | READY_TO_EXECUTE | plan 승인을 실행 승인으로 오인하지 않음 |
| READY_TO_EXECUTE | lease_acquired | EXECUTING | adapter governed 통과, sandbox, 예산·원장 정상 |
| EXECUTING | work_units_finished | VERIFYING | 실제 change manifest와 작업 결과 있음 |
| VERIFYING | required_checks_passed | FINAL_REVIEW | 최신 postimage에 대한 필수 검사, 미확인 0 |
| FINAL_REVIEW | final_review_passed | COMPLETED 또는 AWAIT_APPLY_APPROVAL | patch_only는 완료; apply_to_source는 별도 원본 반영 승인 필요 |
| ANY_ACTIVE | material_change | CHANGE_ASSESSMENT | 영향 의존관계 계산, 실행 permit 중단 |
| ANY_ACTIVE | user_cancel | CANCELLING → CANCELLED | 신규 dispatch 즉시 금지, 실행 중 부작용을 확인한 뒤 취소 완료 |

`COMPLETED`는 kernel 계산 상태다. 모델이 “완료했습니다”라고 출력해도 전이가 일어나지 않는다. dcode TUI의 자연어 문구를 항상 제어할 수 있다고 가정하지 않으며, dashboard/최종 보고서에서 권위 있는 상태와 agent 주장을 구분한다.

### 5.2 정상 변경과 외부 드리프트

납품 방식은 `delivery_mode=patch_only|apply_to_source`로 spec와 plan에 고정한다. 기본 제안은 patch_only이며 사용자 의도를 임의로 바꾸지 않는다. apply_to_source는 FINAL_REVIEW 이후 AWAIT_APPLY_APPROVAL→APPLYING→현재 원본 반영 검증→COMPLETED다. 부분 적용·결과 불명은 RECONCILING으로 이동하고 거짓 완료를 금지한다. 정확한 전체 전이와 guard는 `contracts/state-machine.catalog.json`을 따른다.


허가된 작업 자체가 파일을 바꾸는 것은 예상된 snapshot evolution이다. WorkUnit마다 `expected_preimage → observed_postimage` 체인을 기록해 이어간다. 이 변화 때문에 매 파일 수정마다 전체 계획 재승인을 요구하지 않는다. 외부 사용자/프로세스의 예기치 않은 변경, 승인 범위를 넘는 파일, 제품 의미 변경은 pause·재계획·필요 승인으로 되돌린다.

### 5.3 일시정지와 재개

재개는 기존 승인 유효성·policy/release·snapshot·lease 상태·실행 중 명령의 결과를 먼저 reconcile한다. TTL 만료나 변경된 파일은 재검증한다. 예산 소진, 필수 reviewer timeout, context limit, 외부 서비스 장애는 성공으로 종료하지 않는다. 일시정지 사유와 남은 의무를 `ReadinessReport`에 남긴다.

## 6. Decision Interview의 고도화 통합

### 6.1 원본에서 보존하는 핵심

단일 외부 진행자, 원문/해석 분리, 사실/의도/가설 분리, 결정별 authority, 의무별 readiness, 반례, blind handoff review, revision+digest, 의존 무효화, 신뢰된 승인, 적법한 보류, 예산 소진 시 pause, R01–R22 모두 MUST다. 원본의 `APPROVED_FOR_PLANNING`을 `EXECUTION_APPROVED`로 이름만 바꾸지 않는다.

### 6.2 인터뷰 입력 계약

입력은 사용자 원문, 허용 source scope, workspace snapshot, 사용자에게 이미 확인한 결정, 관련 memory view, policy/risk profile이다. memory의 과거 취향은 현재 명시 요청보다 강하지 않다. 이전 프로젝트의 합의를 현재 프로젝트의 사용자 승인으로 가져오지 않는다.

Agent가 다음 행동을 제안하면 kernel가 `ASK_USER / INSPECT / RESEARCH / SANDBOX_PROBE / DELEGATED_DECISION / DEFER / REVIEW / PREPARE_SPEC` 중 허용되는 행동으로 검증한다. sandbox probe는 인터뷰용 별도 승인으로 실행하며 구현 작업 권한을 열지 않는다.

### 6.3 질문 선택 알고리즘

1. 미해결 의무에서 승인·보안·데이터 손실·외부 공개·되돌리기 어려운 결정을 먼저 추출한다.
2. 해당 결정이 원문, 최신 근거, 현재 합의에 이미 해결되어 있는지 검사한다.
3. 코드나 문서로 확인할 사실이면 먼저 적법한 읽기/조사를 선택한다.
4. 질문 후보에는 decision IDs, 선택별 관측 결과, 왜 지금 필요한지, 사용자의 답변 가능성, 기존 질문 중복 여부를 요구한다.
5. 동일 의미 후보는 결정 ID와 질문 목적에 따라 병합하되, 원문에 없는 의도를 합성하지 않는다.
6. 한 사용자 질문에 한 독립 결정을 다룬다. 복수 항목을 받았다면 여러 제안으로 분해하고 중요한 해석만 확인한다.
7. 사용자가 모르면 예시·조사·제한적 위임·보류 중 가능한 경로를 선택한다.
8. 시간/질문 soft limit은 다음 행동 재평가 신호이며 강제 종료 조건이 아니다. hard budget 초과는 pause다.

진단용 ambiguity/coverage는 유지할 수 있지만 모델의 0.9 점수로 승인 또는 readiness를 결정하지 않는다. 커버리지 분모는 적용 의무의 등록 목록이다. 분모 삭제에는 사유·권한·의존관계 검사가 필요하다.

### 6.4 독립 검토

Spec Critic은 경계·오류·취소·동시성·권한 중 적용 가능한 구체적 반례를 제시한다. Blind Handoff Reviewer는 후보 spec와 허용 snapshot만 보고 구현 해석 및 추가 가정을 낸다. 원 대화, 다른 reviewer의 점수, 숨겨진 테스트는 제공하지 않는다.

모든 개발 작업에는 spec critic과 독립 plan reviewer를 배치한다. high/critical 작업에는 spec blind handoff, plan risk reviewer, 최종 독립 code reviewer를 추가로 필수화한다. 동일 모델의 역할 분리는 정보 격리를 뜻하며 통계적 독립성이나 정답 보증은 아니다.

### 6.5 인터뷰 산출물

`contract.json`, `SPEC.md`, `ACCEPTANCE.md`, `DECISIONS.md`, `OPEN_QUESTIONS.md`, `EVIDENCE_INDEX.json`, `approval.json`을 외부 run export 디렉터리에 작성한다. 내용은 원본 설계와 호환하며 UDH에서는 traceability IDs, semantic version, scope digest, evidence freshness, 후속 plan interface를 추가한다.

SPEC 승인 뒤 변경 요청은 변경된 의도·결정·시나리오에서 시작해 관련 plan task, verification, review, execution permit까지 전이적으로 무효화한다. 영향 없는 결정은 다시 질문하지 않는다.

## 7. 개발 시작 전 계획 구체화·리뷰 Workflow

### 7.1 계획은 TODO 목록보다 강한 계약이다

각 WorkUnit에는 다음이 필수다: `id`, 목적, 요구사항 IDs, 선행 작업, 입력 artifact와 digest, 변경할 파일/생성 파일, 읽기/쓰기 범위, 전제조건, 구체적 구현 절차, 공개 interface 변화, 실패/예외 처리, 검증 명령 및 기대 결과, rollback/recovery, 위험도, 예산, 완료 조건.

“인증 구현”, “테스트 추가”, “필요한 파일 수정” 같은 이름만 있는 작업은 PLAN_INVALID다. 아직 정확한 대상 파일을 모르면 먼저 읽기 전용 discovery work item으로 분리한다. discovery 결과가 나온 뒤 concrete write-set을 만들고 실행 승인을 받는다.

### 7.2 Plan 생성 순서

현재 구현과 테스트 조사 → 승인된 요구·제약 재확인 → 영향 범위/호환성/실패 모드 분석 → 인터페이스 계약 → DAG 분해 → 검증 계획 → 권한/예산/복구 계획 → 독립 리뷰 → 수정 → 정확한 plan bundle 승인 → 실행 승인 순서다.

Planner가 결정할 수 있는 내부 기술 선택은 사전에 위임된 범위로 제한한다. 제품 의미가 바뀌는 결정은 인터뷰로 되돌린다. Python/TypeScript 등 언어별 quality profile은 프로젝트 근거로 정하고 모델 종류로 선택하지 않는다.

### 7.3 리뷰 내용

Plan Reviewer는 다음을 확인한다: 각 중요 요구에 작업과 합격 시나리오가 있는가; DAG가 실제 선행 조건을 표현하는가; 파일/명령 범위가 명확한가; 기존 동작 보존 검사가 있는가; 신규/변경 API의 타입·오류·동시성 계약이 있는가; 실패 시 안전한 중단·복구가 가능한가; 테스트 실행에 필요한 데이터·네트워크·비밀이 과도하지 않은가; 구현자가 추가로 정해야 할 중요 사항이 남아 있는가.

Review finding은 severity, affected IDs, 구체적 근거 또는 가상 반례, 해결 조건을 가진다. 단순한 스타일 선호나 기능 추가 제안은 blocker가 아니다. blocker의 폐기는 작성 에이전트 단독 판단으로 하지 않고 동일 검토자 재검토 또는 승인된 정책에 따른 adjudicator를 사용한다.

### 7.4 필수 traceability

`Requirement → Decision → Scenario → WorkUnit → ChangedFile → VerificationResult → ReviewReport` 연결을 생성한다. 모든 테스트가 모든 요구를 증명할 필요는 없지만 중요 요구는 적어도 하나의 관측 가능한 검사나 명시적 인간 검토 절차와 연결되어야 한다.

검증 실행 전에는 상태가 `specified`다. 실행 후 실제 runner 결과가 들어오면 `passed/failed/error/skipped`로 구분한다. `skipped`와 테스트 수 0은 pass가 아니다. 요구사항이 비기능적이면 검증 방법·환경·담당자·합격 범위를 명시한다.

### 7.5 실행 중 재계획

사소한 내부 순서 변경은 DAG/권한이 허용하고 결과·비용·검증 의미가 같을 때 기록 후 진행할 수 있다. 추가 파일 생성, API 변경, 승인 budget 초과, acceptance 변경, 보안 범위 변화는 새 plan revision과 재리뷰가 필요하다. 기존 plan approval은 새 digest에 자동 이월되지 않는다.

최종 리뷰가 수정 요청을 내면 제한된 rework plan을 만들고 기존 permit의 포함 범위인지 검사한다. 범위 안의 버그 수정과 검증 재실행은 기존 권한으로 가능하지만, 변경된 postimage에 대해 관련 검사는 반드시 재실행한다.

## 8. 작업 기반 Harness Profiles와 서브에이전트

### 8.1 프로필 구성 축

모델 프로필이 아니라 `phase × task_kind × risk × permission_scope × budget`를 조합한다. `TaskProfile`에는 요구 리뷰, memory categories, tool permissions, context allocation, parallelism, verification recipe가 있다. provider/model 이름으로 분기하는 필드는 금지한다.

| 단계 프로필 | 핵심 기능 | 수정 권한 |
|---|---|---|
| interview | framing, evidence, clarification, critic, blind handoff | 원본 소스 금지 |
| investigate | search, call-flow, failure hypothesis, bounded probe | probe 별도 승인 |
| plan | task DAG, interface, tests, rollback, review | 계획 산출물만 |
| implement | 작업 임대, scoped edits, test loop | 승인된 작업 사본만 |
| verify | lint/type/test/acceptance/performance 확인 | 승인된 sandbox 임시 출력만 |
| review | 독립 diff/contract/evidence 검토 | 수정 금지 |
| improve | pattern/causal hypothesis, candidate, eval proposal | candidate 영역만 |
| evaluate | 통제 비교, holdout, regression | 격리된 평가 사본만 |

일반 bugfix·feature·refactor·migration·documentation·security review에 같은 phase engine을 사용하되 필요한 의무가 다르다. refactor에는 동작 보존, migration에는 이전/이후 호환성과 rollback, bugfix에는 재현과 회귀 검사, 문서 변경에도 사실성 및 참조 유효성을 요구한다.

### 8.2 프로필 합성 규칙

hard policy는 항상 상위다. 최종 권한은 상위 policy, session scope, 승인 scope, role scope, WorkUnit scope의 **교집합**이다. deny는 allow보다 우선한다. budget은 허용 상한 중 최소값이다. 필수 리뷰/검증은 합집합이다. cache 이득을 이유로 도구 권한을 넓히지 않는다.

profile이 tool-set을 바꾸면 새로운 profile epoch/digest를 기록한다. 같은 phase 안에서는 owned tool 이름과 schema의 순서를 안정적으로 유지한다. provider native profile은 dcode/SDK에 맡기되 그것이 도구 이름이나 기본 동작을 바꾸어도 UDH 권한 검사를 우회하지 못해야 한다.

### 8.3 서브에이전트 역할

Facilitator, EvidenceScout, SpecCritic, BlindHandoffReviewer, Planner, PlanReviewer, Implementer, Verifier, CodeReviewer, LearningAnalyst, EvaluationJudge와 선택적 SecurityReviewer를 제공한다. 숫자가 많다는 이유로 모두 매 turn 실행하지 않는다. 단계·위험도·필수 검토 계약에 따라 선택한다.

모든 worker는 `role`, assigned task ID, parent run ID, policy digest, input digest, bounded context, deadline, max calls, allowed output type을 받는다. 한 번에 하나의 외부 진행자만 사용자에게 질문한다. worker가 다른 worker를 임의로 spawn하지 못하며 kernel scheduler가 budget과 scope를 확인한다.

### 8.4 동시성

read-only 조사/독립 리뷰는 병렬 허용한다. 같은 파일에 대한 쓰기는 exclusive lease로 직렬화한다. 별도 작업 사본의 병렬 구현도 integration 단계에서 충돌·계약·전체 테스트를 재검증한다. 메인 모델의 context에서 모든 파일·로그를 합치지 않고 결과 artifact와 핵심 근거를 반환한다.

기본값: 동시 worker 3, worker spawn depth 0, work-unit 동시 writer는 충돌 없는 범위에 한정. 이는 기능 제거가 아니라 운영 상한이며 policy로 조절할 수 있다. 동일 모델/다른 모델 어느 경우에도 같은 규칙을 적용한다.

native `task` 경로에서 UDH 정책·추적이 상속되는지 반드시 검사한다. 보장이 없으면 그 경로를 차단하고 kernel가 별도 dcode worker 세션을 시작하는 검증된 adapter를 사용한다. 이 fallback은 dcode를 SDK 에이전트로 대체하지 않으며, 원래 경로 실패를 숨기지 않는다.
