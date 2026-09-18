# CYRANO 전체 시스템과 소유권

문서 유형: 상세 설계 · 상태: 계획(제품 미구현)


## Problem

사용자는 인터뷰부터 코드 검증까지 수행하는 dcode에 적극적 기억과 자기개선 기능을 결합하려 한다. 회고문을 저장하는 것만으로는 이후 행동 변화와 개선 효과를 보장할 수 없다. 반대로 모델이 활성 프롬프트·권한·평가기·자기 Python 코드를 즉시 수정하면 평가 오염, 승인 우회, 재현 불가능한 실행을 만든다. DeepSeek Harness의 모듈·문서·에이전트 구조를 채택하되 기존 Deep Agents Code 실행 엔진과 사용자의 모델 비특화 요구를 유지해야 한다.

## Proposal

### 통합 R2 책임과 상태

기존13 workspace와 dcode 실행을 유지한다. source 단일 패키지를 추가하지 않는다. 현 세션29상태는 후보 lifecycle과 다른 aggregate다. 목표강화 DTO는 contract registry의 v2, 기존feature DTO는 v1을 명시 선택한다. 설치하는 고객 저장소에는 agent/config/dependency를 자동 생성하지 않는다.

자세한 해석·충돌 해결은 [Universal Harness 통합 설계](2026-09-16-universal-harness-integration.ko.md)를 따른다. 원본첨부에 있는 더 느슨한예시로 이규칙을낮추지 않는다.

CYRANO(Universal Development Harness)를 **dcode를 대체하지 않는 외부 제어 계층과 plugin**으로 구현한다. 이번 저장소는 이 제품을 개발하는 저장소이며, 압축 해제 직후 네트워크 없이 동작하는 결정적 기반 코드·테스트와 전체 구현 명세를 포함한다. 실행 모델 호출, 운영 sandbox, 신뢰된 승인 UI, 실제 효과 검증은 작업계획에 따라 추가 구현한다. 기반 테스트 통과를 전체 제품 출시로 표시하지 않는다.

### 1. 범위와 불변 조건

| ID | 필수 요구 | 금지되는 대체 해석 |
|---|---|---|
| BASE-01 | 코딩 실행은 실제 dcode | 별도 SDK agent loop를 조용히 대체 사용 |
| BASE-02 | 설치 시 원본 보존·승인된 최소 native 연결 변경 허용 | 무승인 원본 덮어쓰기·monkey patch·침묵하는 loop 대체 |
| BASE-03 | 고객 저장소 비침습 설치 | harness 설치 때문에 고객 repo에 설정·SDK dependency 생성 |
| GEN-01 | 모델 비특화 | 모델 이름별 프롬프트·능력 점수·탐색 규칙 분기 |
| INT-01 | 원본 R01–R22 인터뷰 보존 | 질문 수·명확성 평균 점수만으로 준비 완료 |
| PLAN-01 | 구현 전 계획·독립 리뷰·허가 | 에이전트가 작성한 계획을 자기 승인 |
| MEM-01 | scope·근거·freshness 기반 적극 기억 | vector 검색 hit를 적용·효과로 간주 |
| LEARN-A | 탐색 정책 개선 및 실제 검증 | 기록에 없는 전이 추측·replay만으로 배포 |
| LEARN-B | 지식·절차·코드 개선 | markdown 회고만 저장하거나 활성 코드 즉시 수정 |
| CACHE-01 | 안정 context와 실제 usage 관측 | digest 동일·latency 감소만으로 cache hit 주장 |
| OBS-01 | 관측 가능한 개발 전 수명주기 | 비공개 내부 추론이나 타 IDE 전체를 관측한다고 주장 |
| AUTH-01 | 신뢰된 사용자 권한과 실행 격리 | 파일의 approved:true 또는 같은 OS 사용자 프로세스 분리 |
| REL-01 | CAS·outbox·lease·복구·release 고정 | 외부 API exactly-once를 허위 보장 |
| PY-01 | PEP8 기반 스타일·타입·문서·테스트 | formatter 한 개의 성공을 전체 품질로 간주 |
| PREP-01 | 독립 실행 가능한 개발 준비 ZIP | 제품 운영 검증 완료와 개발 준비 완료 혼동 |

설정·명령·타입 이름 중 `cyrano_*`, `cyrano …`, 이 저장소의 JSON은 신규 CYRANO 인터페이스다. dcode가 이미 제공하는 것으로 설명하지 않는다. `register_middleware`, `register_tool`, `register_backend_route`, `on_shutdown`만 확인된 확장 표면이며 실제 설치 조합은 WP00에서 확인한다 [S04].

### 2. 세 계층과 실제 데이터 흐름

```text
[사용자 대화] dcode TUI ── 신뢰된 입력 어댑터 ──┐
[승인 사용자] 별도 CYRANO 승인 UI/CLI ───────────────┤
                                                 ▼
Control Plane (별도 principal)
  Interview / Intent / Plan / Review / Approval
  Memory / Candidate / Evaluation / Release / Event Store
  Action Broker / Artifact Store / Outbox / Recovery
             │ 서명된 최소 run 권한 + 불변 입력 manifest
             ▼
Agent Plane
  공식 dcode + CYRANO extension + 역할별 안정 context
  허가된 도구 요청 / 관측 / 제안만 수행
             │ 요청; DB·승인키·sealed tests 직접 접근 불가
             ▼
Execution Plane
  작업별 격리 sandbox / 읽기 전용 source snapshot
  Broker가 승인된 패치만 반영 / 쓰기 가능한 scratch
             │ 검증된 산출물 + 별도 원본 반영 승인
             ▼
사용자 대상 프로젝트
```

Control Plane의 command handler는 상태·권한 소유자다. Agent Plane의 middleware는 신뢰된 서비스에 질의하고 관측을 보완하지만 보안 경계 전체가 아니다. Execution Plane의 runner는 실제 도구 실행 결과를 서명된 실행 receipt와 연결한다. 승인 UI는 모델 tool에서 호출할 수 없는 경로에 둔다. Dashboard read stream과 승인 mutation endpoint를 분리한다.

같은 OS 계정으로 띄운 두 Python 프로세스는 임의 파일 접근을 막지 못한다. 그러한 환경은 `advisory_diagnostics`이며 governed로 승격할 수 없다. governed는 서로 다른 principal 또는 검증된 container/VM 경계, 최소 mount, 독립 credential, 필수 호환성 검사를 모두 요구한다.

### 3. 실행 단위와 식별자

`Workspace`는 프로젝트의 논리 ID다. remote URL만으로 workspace를 합치지 않는다. `SourceSnapshot`은 tracked·허가된 untracked 파일 내용, 실행 환경, 주요 config digest를 기록한다. 같은 Git HEAD여도 dirty tree가 다르면 다른 snapshot이다. `.env`, credential, private key는 기본 제외하고 제외 manifest만 남긴다.

`Session`은 사용자와의 작업 수명주기, `Run`은 고정된 runtime·release·권한에 묶인 실행, `WorkUnit`은 검증 가능한 계획 작업, `DiscoveryEpisode`는 동일 요구·시작 snapshot을 공유하는 탐색, `Attempt`는 특정 branch에서 구현 및 검증까지 수행한 하나의 시도다. 모델 호출·tool 호출은 Attempt의 자식이다. 모델 요청 한 번을 무조건 별도 학습 사례로 세지 않는다.

모든 ID는 opaque하며 결과나 품질이 드러나는 이름을 사용하지 않는다. canonical artifact digest는 `sha256:<64hex>`와 schema version으로 구분한다. raw source·실제 prompt bytes는 별도 raw digest를 사용한다. 생성 JSON의 정규화가 원본 파일의 실제 바이트를 대신하지 않는다.

### 4. 저장소 구조와 배포 구조의 차이

```text
cyrano-deepagent-code/                 # 이 제품 자체를 개발
  ../deepagents_code/cyrano/cli/                        # 실제 offline 명령, 장래 단일 제품 launcher
  packages/<group>/<package>/      # Python workspace, 기능별 소유자
  plugins/cyrano/                     # dcode 배포 plugin, skills와 역할 원본
  configs/                         # CYRANO 구성, dcode native config와 다름
  contracts/{v1,api,sql}/           # 데이터·wire·persistence 명세
  .agents/{skills,roles,notes,work}/ # 이 저장소를 개발할 에이전트 설정
  docs/{subsystems,cookbook,runbooks,generated}/
  scripts/                         # 검사·문서 생성; product 실행을 우회하지 않음
  tests/                           # 실행 가능한 기반 테스트 + 미실행 수용 명세
  runtime/                         # 설치 probe 입력·검증해야 할 runtime lock
  references/{interview,dream}/     # 첨부 원문, 변경하지 않는 참고 입력
  evidence/                        # 실제 검사 결과; 평가 fixture와 분리
```

운영 시 고객 저장소 밖에 `$CYRANO_HOME/control/`, `artifacts/`, `releases/`, `runtimes/`, `workspaces/`, `quarantine/`를 만든다. dcode profile root와 plugin cache도 별도 검증 경로다. 이 프로젝트의 `.agents`를 고객 저장소에 복사하지 않는다. `git worktree`는 원본 `.git`를 수정할 수 있으므로 기본 source snapshot은 외부 content copy이며 worktree 사용은 명시 허가가 있을 때만 허용한다.

### 5. 서비스 정의 / 구현체 / 소비자

DeepSeek Harness의 capability 구조를 Python Protocol과 명시적 구성으로 적용한다 [S01–S03]. 각 기능은 인터페이스만 선언한 빈 모듈로 끝나지 않는다. 제공자가 상태·오류·수명주기를 소유하고, 소비자가 이를 호출하는 실제 경로와 테스트를 가진다.

| Capability | 정의와 소유 package | 제공자 | 소비자 | 핵심 불변 조건 |
|---|---|---|---|---|
| Contract | core/contracts | JSON parser + semantic validator | 모든 외부 입력 | unknown 필드·잘못된 enum 거부 |
| Control | core/kernel | command handlers | UI·extension bridge | revision·권한 검사 후 단일 transaction |
| Events | storage/sqlite | SQLite adapter | kernel·recovery·dashboard | append + outbox atomic |
| Context | context/compiler | deterministic compiler | dcode middleware | stable prefix에 변동 상태 없음 |
| Memory | memory/service | scope storage·selector | interview·planner·verifier | query 전 ACL·freshness |
| Interview | interview/kernel | obligation/state engine | facilitator bridge | 점수로 critical blocker 상쇄 불가 |
| Plan | workflow/planner | DAG + review engine | dispatcher | 승인된 입력·경로·검증 범위 |
| Improvement | improvement/engine | A replay / B proposal workers | scheduler·release | 독립 평가·권한 없는 active mutation 금지 |
| Evaluation | evaluation/runner | isolated paired runner·judge | release gate | 기준·hidden tests는 candidate가 변경 못 함 |
| Lifecycle | plugin/lifecycle | trusted component registry | CYRANO launcher | 역순 정리, 부분 setup 롤백 |
| Observability | observability/events | redacted event exporter | dashboard·metrics | unknown과 zero 구분 |
| Dcode | runtime/dcode | version-pinned adapter | work dispatcher | 실제 dcode 호출, 미지원 fail closed |

현재 lock에는 13개 로컬 distribution과 virtual root가 있다. 새 capability를 만들 때 기존 소유자에 메서드를 추가할지 독립 package를 만들지 먼저 결정한다. 이름만 다른 빈 service package를 양산하지 않는다. 테스트·배포 수명주기가 독립적인 경우에만 분리한다.

### 6. 의존성 방향과 import 규칙

contracts는 표준 라이브러리 외 런타임 의존성을 갖지 않는다. 각 domain은 contracts와 공개 port에 의존한다. SQLite·dcode 같은 adapter는 domain port를 구현하고 domain이 adapter를 import하지 않는다. ../deepagents_code/cyrano/cli composition root만 제공자들을 결합한다. 초기 foundation package dependencies와 목표 단계의 추가 의존성은 package manifest와 WP에서 같이 갱신한다. 다른 package의 `_private` 모듈이나 `src` 경로를 import하지 않는다.

개발용 `scripts/bootstrap.py`는 로컬 src 탐색을 위한 보조 도구다. 배포 wheel은 정식 distribution dependency로 import되어야 하며 runtime에서 sys.path monkey-patch를 사용하지 않는다. WP22의 clean-wheel smoke가 source-tree 우연한 import 성공을 잡는다.

### 7. 구성과 extension lifecycle

configuration은 표준 JSON으로 저장한다. `!!js`, Python 표현식, 임의 import 문자열 실행을 지원하지 않는다. `resolve(config, capabilities) -> ResolvedSpec`가 defaults와 권한 교집합을 확정한 뒤, `run(spec)`는 숨은 fallback 없이 실행한다. component ID 중복·알 수 없는 field·의존성 cycle·필수 service 없음은 시작 실패다.

구성층은 배포 기본값 → 운영자 정책 → workspace 허용 정책 → task 요청 순이다. 권한은 뒤층이 앞층의 제한을 넓힐 수 없고 교집합으로 계산한다. provider endpoint와 역할 선택은 서로 다른 필드이며 역할은 작업 종류로 결정한다. 모델 이름은 역할 선택 조건이 아니다.

plugin 활성화는 의존성 위상순, 종료는 역순이다. setup 중 등록한 서비스와 disposer는 그 plugin 소유다. setup 실패 시 해당 effects를 되돌리고 실제 실패를 기록한다. shutdown 오류가 나도 남은 disposer를 호출하고 오류를 묶어 보고한다. 승인키·판정기·audit 정책은 일반 비신뢰 plugin이 교체할 수 있는 확장점으로 제공하지 않는다.

### 8. 모델에 보이는 입력과 기록의 정합성

모든 CYRANO 주입 블록에는 source artifact ID·release·epoch·scope·주입 이유가 있어야 한다. 가능한 경우 모델에 보낸 실제 내용을 로컬 승인 저장소에서 재구성한다. 그러나 비밀 제거·보존 만료·provider 내부 변환 때문에 완전 재구성이 불가능한 경우 `reconstructability=redacted|expired|unobserved`로 표시한다. model-visible implies logged 원칙을 개인정보 무제한 보관의 명분으로 쓰지 않는다.

공개 행동·짧은 근거·입출력·도구 실행을 기록한다. 모델 비공개 chain-of-thought를 요구하거나 그 수집에 의존하지 않는다. dcode의 내부 요약 호출·child graph·provider retry 등 관측 누락은 coverage report의 실제 검사 결과로 남긴다.

## Alternatives considered

**DeepSeek Harness 전체 런타임 이식:** Cordis·Node 제품을 통째로 도입하면 dcode 기반 요구를 바꾸고 두 실행 엔진의 상태를 유지해야 한다. 대신 package·문서·수명주기 원칙을 채택한다.

**거대한 root AGENTS.md 하나:** 항상 많은 토큰을 사용하고 작은 상태 변경으로 공통 context가 흔들린다. standing orders, 역할, on-demand skill, 작업 입력을 분리한다.

**회고를 곧바로 active memory에 기록:** 낮은 품질의 단발 사건이 전역 동작을 바꾸고 평가 전후 조건을 섞는다. observation/candidate/active release를 분리한다.

**관측부터 승인까지 하나의 shell hook:** 모든 모델·서브에이전트 경로와 권한을 보호하지 못한다. hooks는 보완 관측이며 커널·broker·격리가 강제한다.

## Acceptance criteria

설치 전후 고객 repo manifest가 같아야 한다. dcode 실제 진입점·extension health·child 도구·권한 우회 테스트가 모두 verified여야 governed launch가 가능하다. workspace별 package dependency 검사는 cycle·private import를 거부한다. 모든 상태 변경 command는 명세의 revision·scope·idempotency·권한 검사를 통과해야 한다. BASE/GEN/INT/PLAN/MEM/LEARN/CACHE/OBS/AUTH/REL/PY 추적표에서 필수 작업의 실행 증거가 연결되어야 전체 출시로 표시한다.

## Risks

upstream dcode experimental 확장 변경, 네이티브 context 로딩 순서, 제한된 host 승인 출처, sandbox별 차이가 가장 큰 호환성 위험이다. WP00/03/06이 해결하지 못한 경계는 기능을 몰래 약화하지 않고 명시적으로 차단한다. 명세에 사용한 예산·표본·byte 기본값은 초기 정책이지 실측 최적값이 아니다.

## Native CLI 모니터링의 현재 설계 연결

사용자 운영 모니터링의 기본은 [dcode 내부 Monitor](../NATIVE_MONITOR_TUI.ko.md)다. 기존 dashboard 용어는 이 native 화면의 읽기 view를 포함하는 개념이며 외부 웹 UI 필수 요구가 아니다. 실행은 RF07–RF09에서 native 명령·인증 query·Textual·실제 호출 coverage를 함께 검증한다.

## 1. 이번 반영의 정확한 경계

현재 사용자 지시가 첨부 요청서의 새 디렉터리 예시보다 우선한다. `deepagents_code/cyrano/`는 우리가 개발할 제품 코드, `cyrano/`는 기존 개발 자료의 위치다. 본 팩은 그중 `cyrano/docs/`의 기존 분류 아래에 고유 이름의 문서만 더한다. dcode 원본, Python 패키지, lock, installer, runtime 설정, `.agents/`와 기존 목차를 변경하지 않는다.

검토 가능한 실제 기준은 R5 ZIP의 946개 payload 파일이다. 대화에는 R6 설명이 있지만 해당 ZIP bytes를 확보하지 못했다. R6의 상태기계·case 수·서명 계약을 재현해 교체하지 않는다. WP00은 사용자의 실제 checkout에서 R6 소유 문서와 최신 코드를 결속하고 충돌표를 만든다. R5로 downgrade하지 않는다.

## 2. 유지하는 한 가지 실행 구조

```text
사용자 / 기존 dcode TUI / 기존 ACP ingress
             │
      기존 dcode agent loop
             │
      Cyrano 통합 middleware ────── 모델 protocol 정규화 검사
             │                              │
       기존 Control plane                기존 provider adapter
       ├─ Interview / 의도·근거·결정
       ├─ Plan / 독립 Review / Human decision
       ├─ Workflow / Task ledger / lease / mailbox
       ├─ Memory / Skills / Improvement A·B
       ├─ Verification / Evidence / Release
       └─ Events / Recovery / CLI read projection
             │
      Action Broker / 검증된 Sandbox
             │
      승인된 worktree·candidate snapshot
             │
      별도 검증·승인된 원본 반영
```

모델 호출과 coding interaction은 dcode에 남긴다. generated DAG도 기존 workflow의 작업 단위를 만드는 입력 형식일 뿐 두 번째 agent runtime이 아니다. MCP는 도구 연결, ACP는 client/coding-agent 연결, A2A는 원격 agent 간 task 연결로 분리한다. 모든 외부 worker는 같은 작업·권한·증거 계약의 소비자다.

## 3. 책임의 소유자

| 책임 | 기존 소유 영역 | skill/모델에 허용 | 코드로 강제 |
|---|---|---|---|
| 요구·완료 조건 | interview + kernel | 질문·명세·대안 제안 | revision·blocker·사용자 결정 보존 |
| 계획·review | workflow | 작업 분해·반례·finding 작성 | 요구 추적·DAG·finding 상태·승인 결속 |
| 정규화 | dcode + contracts | 없음 | typed stream·call/result mapping·capability 검증 |
| context | context | 관련성 제안·요약 초안 | 필수 의무 보존·예산·고정 epoch·scope |
| 기억 | memory | 읽기 요청·추가/수정 후보 | ACL·freshness·후보/활성 분리·삭제 |
| skill | plugins + memory | 절차 작성·개선 후보 | manifest·권한·version·eval·release |
| 병렬 작업 | workflow + kernel | 독립 작업 제안 | lease·resource conflict·budget·승인 |
| 편집·원본 반영 | kernel + dcode Broker | patch 제안 | snapshot·경로·권한·원자적 효과 원장 |
| 평가 | evaluation | 정성 리뷰 보조 | sealed 데이터·실행기 판정·회귀·불확실성 |
| 화면 | monitor + events | 사용자 요청 시 설명 | 실제 원장 조회·집계·redaction·권한 |

## 4. 성능을 위해 권한을 약화시키지 않는 실행 단계

먼저 text/구조 검색으로 좁히고 필요할 때 symbol·LSP·AST·그래프를 호출한다. 도구 전체를 항상 system prompt에 노출하지 않는다. 그런데 도구 schema를 매 호출마다 바꾸면 cache와 관측이 흔들리므로 phase/tool epoch에서 고정한다. 필요한 도구가 없으면 새 epoch를 명시적으로 열거나 미지원으로 종료한다.

Memory advisor는 hint만 제안한다. approved memory release와 policy는 서로 다르다. generated workflow는 compile-time 검증을 통과해도 execution permit을 자동으로 얻지 않는다. replay score가 좋아도 lane B의 실제 실행 평가를 생략하지 않는다. read-only 조회 기능의 성공으로 제품의 강제 보안을 주장하지 않는다.

## 5. 불필요한 복잡성을 줄이는 결론

새 모델 SDK·독립 vector DB·별도 task DB·다른 TUI·Rust runtime·상시 remote orchestration 서비스는 기본 의존성으로 추가하지 않는다. 기존 자료의 Graphify/QMD/Serena/SCIP/Knip 판단은 유지한다. 이 팩은 도구를 설치하지 않으며 도구 활성화 권한도 바꾸지 않는다.

우선순위는 protocol 손실 방지 → context/권한·상태 결속 → 안전한 편집·durable work → 실제 개선 효과 순이다. speculative engine을 먼저 만드는 대신 WP20의 단순 baseline과 비교하여 효용 없는 층은 비활성 상태로 유지한다.
