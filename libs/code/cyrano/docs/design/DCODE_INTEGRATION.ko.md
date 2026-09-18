# Cyrano Agent · dcode 기반 코드와 복사 경계

문서 유형: 상세 설계. 상태: 개발 준비. 이 파일은 base/제품 코드/문서 위치의 단일 원본이다. **Cyrano Agent는 dcode를 기반으로 우리가 개발할 제품명**이다. dcode를 외부 서비스처럼 대체 호출하는 별도 agent loop를 만들지 않는다.

## 1. 정확한 디렉터리 의미

| 경로(원본 monorepo 기준) | 소유자 | 현재 ZIP의 처리 |
|---|---|---|
| `libs/code/deepagents_code/agent.py`, `main.py`, `server/`, `tui/` 등 | upstream dcode | 복사 payload에 넣지 않는다. 실제 native 연결 때 소유 WP에서 최소 patch |
| `libs/code/deepagents_code/cyrano/` | 우리가 개발할 Cyrano 제품 Python 코드 | 새 디렉터리. upstream base 코드가 아님 |
| `libs/code/cyrano/` | Cyrano 설계·개발 지원 파일 | 참고 자료·설계·계획·스크립트·개발용 설정. 제품 wheel에 자동 포함된다고 가정하지 않음 |
| `libs/code/tests/unit_tests/cyrano/` | Cyrano 순수 기반 테스트 | 새 디렉터리. 실제 dcode parent import 검사와 별도 |
| `libs/code/tests/cyrano_product/` | Cyrano 제품 수용 테스트 | 구현할 native 통합·격리·실제 평가 테스트 |
| `libs/code/.agents/skills/cyrano-development/` | Cyrano 개발 에이전트 읽기 절차 | 짧은 탐색 skill. 실제 IDE/agent loader 인식은 별도 확인 |
| `libs/deepagents`, `libs/acp`, `libs/partners/*` | upstream 로컬 의존성 | 전체 monorepo에 존재해야 한다. `libs/code`만 복제하지 않음 |

**복사 단위:** 배포 ZIP의 `copy_to_dcode/` 안에 있는 내용(폴더 자체가 아님)을 원본 `<deepagents>/libs/code/`에 합친다. 예를 들어 `copy_to_dcode/deepagents_code/cyrano/`가 `<deepagents>/libs/code/deepagents_code/cyrano/`가 된다. `libs/code/libs/code`나 `deepagents_code/deepagents_code`를 만들지 않는다.

현재 원본 확인 커밋은 `7f9e8ed3a555933902045792da9bb184950ee7b2`다. 날짜가 같아도 다른 SHA면 자동 호환으로 보지 않는다. 기준은 공개 main 조회 결과와 native `DEVELOPMENT.md`, `pyproject.toml`, package `__init__.py`이다. 출처는 [검토 근거](../reference/R4_SOURCE_REVIEW.ko.md).

## 2. 복사 가능 ≠ 제품 활성화 완료

현재 payload는 경로가 충돌하지 않는 개발 소스 추가분이다. 자체 순수 모듈과 준비 검사 도구는 존재한다. 복사만으로 `agent.py`가 Cyrano를 호출하지는 않는다. 새 import namespace는 native `deepagents_code/__init__.py` 아래에 놓이며, **원본 parent 초기화와 실제 의존성을 우회하지 않는 import 테스트가 WP00/RC00 완료 조건**이다. standalone namespace test PASS는 해당 증거가 아니다.

원본 dcode의 설치·실행은 native `uv sync --locked --group test`와 `uv run --no-sync dcode` 경로를 사용한다. `--locked`에서 실패하면 조용히 lock을 재생성하지 말고 원인을 기록·검토한다. 설치 가능한 버전과 credentials/OS가 확보되어야 실제 모델 실행이 가능하다.

## 3. native 통합 책임

| 변경 대상 | 소유 WP | 최소 연결 내용 | 완료 증거 |
|---|---|---|---|
| 설치/버전/실제 package import | WP00, RC00 | Python·uv·lock·build·source 경로 확인 | origin 파일·native smoke 결과 |
| `agent.py`의 middleware/도구/서브에이전트 구성 | WP06 | 단일 Cyrano assembly adapter; 중복 관측·중복 승인 방지 | 실제 graph 호출·main/child mode 테스트 |
| native Memory·Skills 읽기/쓰기 경로 | WP05/WP11/WP12, RC31 | 승인된 read-only projection과 query view; 제안 쓰기만 허용 | 세션 재시작·native `/remember` 우회 거부 |
| native model invocation·cost observer | WP13, RC41 | logical request/physical attempt/context export 연결 | main/child/summary/retry 실측 coverage |
| TUI·headless·ACP·resume 진입점 | WP06/WP13, RC40/RC43 | 같은 request/run authority 연결, 조회는 읽기 권한 별도 | 각 진입 모드 evidence, 미지원은 blocked |
| 종료·cancel·server 재시작 | WP06/WP13/WP21 | durable terminal settlement; unknown outcome·recovery | crash injection과 중복 outbox 검사 |
| native build 설정 | WP19/WP22, RC00 | 제품에 필요한 JSON/prompt/skill resources를 package resources로 투영 | wheel unzip + fresh venv import + resource read |

복사 과정에서 base 파일을 수정하지 않는 원칙과, **우리 제품 개발 중 승인된 native integration patch를 허용**하는 원칙은 다르다. 이전 설계의 'core 무수정'은 설치 시 무단 변경 금지로 범위를 제한한다. native integration을 절대 금지하는 뜻으로 해석하지 않는다. 다만 모델 이름별 분기, 핵심 loop 재작성, SDK 대체 agent로의 조용한 전환, upstream 전체 재포맷은 하지 않는다.

## 4. packaged code와 개발 자료의 분리

`cyrano/contracts`, `configs`, `plugins`는 현재 개발 원본이다. 제품이 runtime에 필요로 하는 부분만 WP19의 결정적 resource compiler로 `deepagents_code/cyrano/resources/`에 투영한다. 그 디렉터리는 이번 ZIP에서 가짜 완성 파일로 채우지 않는다. base wheel이 `*.json` 등을 실제 포함하는지는 빌드로 확인해야 한다. runtime에서 `Path(__file__).parents[...] / cyrano/docs`로 개발 checkout을 가정하지 않는다.

제품 distribution 이름/공개 CLI의 최종 변경은 별도 출시 작업이다. 이번 준비 상태의 native launcher 이름은 `dcode`, public import parent는 `deepagents_code`를 유지한다. 제품 표시명은 Cyrano Agent, 내부 기능 namespace는 `cyrano`다. 서비스·policy·approval 등의 active 식별자는 새 namespace를 사용한다.

## 5. 이전 이름과 기존 설치

이전 이름은 본 프로젝트의 확정 명칭이 아니었다. R4 active 코드·설정·작업 문서는 Cyrano로 바꾼다. 원문 참고팩 및 과거 증거의 이름은 바이트 보존을 위해 바꾸지 않으며 현재 지침으로 로딩하지 않는다.

이름이 다른 이전 추가분이 있는 checkout에는 Cyrano를 중복 활성화하지 않는다. 기본은 **새 worktree 또는 새 clone**이다. 기존 코드·데이터·승인 receipt를 임의 삭제/재서명/재사용하지 않는다. 현재 계약은 contracts/contract-registry.json에 명시한다. 참고 원문 보존과 실제 운영 데이터의 호환성 검증은 별개다. 운영 데이터가 있다면 별도 승인된 migration/backup/복구 검증 전 실행을 차단한다.

## 6. 직접 복사와 검사

사람이 탐색기로 붙여넣을 수 있도록 payload는 dcode code-root 상대 경로다. 다만 기존 파일이 있을 수 있으므로 먼저 root `prepare_dcode.py`의 dry-run을 실행한다. 복사 후 `--verify-installed`는 파일의 byte/hash 및 원본 보호 파일을 확인한다. 해당 도구는 버전·경로·복사 검사를 제공하며 모델 실행이나 운영 권한 강제를 제공하지 않는다.

네트워크 제한으로 이번 환경에서는 전체 upstream clone/uv 설치/제품 실행을 하지 못했다. 저장소의 실제 공개 파일은 connector로 읽었다. 현재 전달 evidence는 payload·준비 코드·synthetic installer 검사와 native source 정적 검토에 한정한다. developer guide가 실제 checkout에서의 검증 단계를 명시한다.

## R5 구현 연결

native `/cyrano` 명령·화면 연결과 package asset 배포 계약은 [R5 소유 상세 설계](NATIVE_MONITOR_TUI.ko.md)에서 구체화한다. 기존 scope·승인·실제 검증은 유지하며 skill 설정만으로 해당 기능을 구현하지 않는다.

## 1. 목표와 비목표

서로 다른 제공자에서 같은 도구·작업 계약을 표현할 수 있게 한다. 모델 이름으로 역할 프롬프트·지능 점수·분기 정책을 하드코딩하지 않는다. 정상적인 provider adapter가 이미 수행하는 변환을 두 번 하지 않는다. 새 `ModelAdapter` 전체를 만들기 전에 native provider의 request/response 관측점을 확인한다. [Pi의 메시지 변환 소스](../reference/SOURCES.ko.md#ns13)는 도구 ID·signature·missing result 문제를 보여 주지만 그대로 복제할 명세가 아니다.

## 2. CapabilityEnvelope와 판정

각 feature는 `unknown / declared / verified_supported / verified_unsupported` 중 하나다. context limit, output limit, image input, structured-tool arguments, parallel tool use, cancellation, cache metrics, reasoning replay를 개별 항목으로 둔다. `declared`가 곧 `verified_supported`는 아니다. 범용 관측 가능한 프로토콜 feature와 특정 모델의 benchmark 지능 점수를 혼합하지 않는다.

키는 provider API 종류·endpoint identity·provider model id·adapter version·probe suite digest다. OpenRouter의 model id가 같아도 실제 route가 다르면 별도 조건이다. route를 알 수 없으면 `route_observed=false`; 특정 upstream 전용 동작은 사용하지 않는다. endpoint가 변경되면 기존 probe 결과를 재사용하지 않는다. secret은 key에 넣지 않고 credential scope identity만 가진다.

`resolve_capability(request, runtime)`는 feature 필요 여부를 계산한다. 불필요한 image feature가 미지원인 것과 사용자가 첨부한 필수 image를 읽을 수 없는 것은 다르다. 후자는 `CAPABILITY_UNAVAILABLE`로 pause/검증된 변환 동의 경로를 사용한다. 몰래 이미지를 빼고 완료하지 않는다.

## 3. 스트림 조립 상태기계

```text
empty → receiving → complete → schema_validated → authorized → executing → settled
                     └→ rejected
receiving → interrupted / malformed
executing → succeeded / failed / cancelled / unknown_effect
```

`complete`는 provider가 정의한 종료 표시와 모든 필수 fragment가 수신된 상태다. JSON parse 가능성만으로 실행하지 않는다. 한 번 parse된 prefix가 뒤의 fragment로 의미를 바꿀 수 있기 때문이다. 최대 argument bytes와 fragment 수는 request의 사전 예산에 넣는다. 초과는 `TOOL_ARGUMENT_LIMIT`이며 잘라서 실행하지 않는다.

UTF-8 multibyte 분할과 문자열 escape를 stream decoder가 처리한다. 응답의 tool id가 충돌하면 첫 값을 유지하고 나머지를 임의 병합하지 않고 `CALL_ID_COLLISION`이다. provider id→Cyrano call id 대응은 request별로 결정적이며 결과까지 연결한다. 같은 이름으로 여러 번 호출한 도구는 순서와 독립 call id를 유지한다.

## 4. 합성 메시지와 실제 효과

대화의 call에 result가 없는 경우 허용된 protocol 보정으로 `observation_missing` 설명을 넣을 수 있다. 이것은 도구 실행 `failed`/`succeeded` 이벤트가 아니다. synthetic flag와 원시 관측 공백을 기록하고 실제 효과는 `unknown`으로 둔다. write 도구는 reconciliation 없이는 다시 실행하지 않는다.

정규화는 원문을 변경해 저장하지 않는다. 원래 provider record와 변환 map의 artifact digest를 결속하고 재구성 가능 범위를 표시한다. redaction 때문에 원문을 보관하지 않은 경우 `full_reconstruction=false`로 표시한다. 외부 private chain-of-thought를 수집하거나 사용자에게 노출하도록 요구하지 않는다.

## 5. reasoning·message·model 전환

opaque signed reasoning은 동일 provider/API/model 조건에서만 허용된 replay 처리에 사용한다. 다른 모델로 넘어갈 때 공개 텍스트로 해독·전환하지 않는다. 공개 최종 답·도구 결과·승인된 요약을 이용해 새 epoch를 연다. provider가 요구하는 signature를 임의 삭제한 뒤 같은 효과라고 주장하지 않는다.

역할 호환성 변환은 lossless, lossy-approved, unsupported 중 하나로 반환한다. system/developer 지침을 user message로 옮기는 것은 권위와 취급이 달라질 수 있어 기본 금지다. 변환하려면 어떤 기능이 달라지는지 별도 consent와 probe가 필요하다.

## 6. retry·cancel·fallback

retry 담당은 한 계층으로 지정한다. provider SDK 내부 retry를 숨긴 상태에서 Cyrano가 다시 retry하면 실제 호출·비용·side effect를 중복할 수 있다. 자동 retry는 byte-level transport/pre-dispatch 실패 또는 검증된 read-only idempotent 도구에 한정한다. HTTP 오류 이름만으로 원격 효과가 없었다고 단정하지 않는다.

동시 cancel이 발생해도 나중에 받은 usage·request id는 billing ledger에 반영한다. 결과를 작업에 적용하는 권한은 generation/fencing token으로 차단한다. 같은 원리로 fallback 모델의 성공은 원래 모델의 결과로 기록하지 않는다. 설정 없는 무음 model fallback은 금지한다.

## 7. 구현 API와 완료 조건

`ProtocolNormalizer.validate_request`, `consume_fragment`, `finalize`, `project_history`, `reconcile_missing_observation`은 순수 변환과 I/O를 분리한다. 각 변환은 `NormalizationRecord`를 돌려준다. native observer가 실제 provider invoke를 감싸는 통합 테스트가 통과하기 전에는 이 pure 코드의 통과를 runtime 호환성으로 표시하지 않는다.

최소 완료 증거는 동일 대화의 signed blocks·다중 call·취소·중단·unknown usage fixture, 정상 경로의 native provider 입력 비교, 원본/변환 digest, 실제 호출 수 ledger, 차단 시 무효과 증거다. 현재 모델 계열 수나 성공률을 추정하지 않는다.

## 1. 구분

MCP는 Agent↔Tool/Resource/Prompt, ACP는 Client/Editor↔Coding Agent, A2A는 Agent↔Agent 작업 전달을 다룬다. 어느 protocol도 해당 peer를 자동 신뢰하거나 local policy를 생략하라는 뜻이 아니다. 공식 규격의 날짜/버전·구현 adapter·conformance suite를 함께 pin한다. [NS58–NS60](../reference/SOURCES.ko.md#ns58)

## 2. 외부 worker 사용 시점

기존 dcode가 기본 worker다. 다른 agent는 별도 필요와 실제 호환성 검증이 있는 경우에만 `ExternalWorkerPort`로 연결한다. 기본 설치에 경쟁하는 daemon과 자격증명을 추가하지 않는다. `unknown / configured / installed / verified / authorized / active`를 구분하고 어느 단계 실패도 active로 건너뛰지 않는다.

필요 capability는 읽기·candidate 수정·검증 명령·취소·결과 artifact·trace·permission callback이다. 단순 채팅 답변만 받는 peer는 code execution worker로 간주하지 않는다. 원격 worker가 사용하는 모델 변경은 실험 조건에 기록한다.

## 3. Capability negotiation과 scope

handshake는 endpoint/executable identity, protocol version, schema digest, workspace map, allowed operations, egress, credential refs, budget, deadline을 결속한다. server description·Agent Card·tool annotation은 untrusted declaration이다. 운영자가 허가한 capability의 교집합만 사용한다.

ACP의 absolute path는 remote URI 또는 허가된 사본의 매핑을 통해 처리한다. 외부 agent가 받은 경로를 host 전체 파일 경로로 해석하지 않는다. filesystem·terminal callback은 Broker를 경유하며 client capability를 이유로 raw shell을 노출하지 않는다. A2A artifact URL은 임의 fetch하지 않고 scheme/host/size/type/redirect 정책을 검사한다.

## 4. 작업 수명

`submit → accepted → running → input_required / completed / failed / cancelled / unknown`을 protocol adapter가 내부 상태로 매핑한다. peer의 completed는 artifact 전달 완료일 뿐 acceptance 통과가 아니다. `input_required`에서 새 질문이 생기면 기존 HumanDecision 연결로 보낸다. remote worker가 사용자를 대신해 응답하지 않는다.

cancel 전송은 정지 확인이 아니다. 특히 notification은 응답을 요구하지 않을 수 있다. 취소 후 artifact/usage가 오면 비용·audit에는 기록하되 generation fence로 코드 반영을 막는다. 재연결에 resume가 없으면 새 작업 생성으로 몰래 대체하지 않고 사용자에게 상태를 보여준다.

## 5. 검증과 원본 반영

외부 patch를 허가된 candidate에 적용하고 source digest·diff scope·license/dependency·보안·hidden acceptance를 local trusted runner가 검사한다. peer의 ‘모든 테스트 통과’ 문자열을 verdict로 쓰지 않는다. 외부 trace를 내부 privileged event producer로 위조할 수 없게 provenance를 나눈다.

MCP schema drift를 감지하면 해당 snapshot으로 시작한 작업의 호출을 중단하고 새 도구 inventory를 review한다. 공격성 설명·리소스·prompt는 낮은 신뢰 자료로 표시한다. output artifact에서 escape·archive bomb·symlink·제어문자를 검사한다.

## 6. 기한·비용·fallback

submit timeout 때 원격 작업이 생성되지 않았다고 단정하지 않는다. protocol이 idempotency를 제공하지 않으면 external request id로 조회하거나 unknown으로 남긴다. 자동 전역 retry는 금지한다. fallback은 동일한 권한·artifact 계약을 검증한 worker만 명시적으로 선택하며 원래 요청과 실행 identity를 분리한다.

## 검토 기준과 현재 작업 소스의 구분

패키지의 native source 기준은 `runtime/runtime-lock.template.json`과 복사 manifest가 지정한 소스다. 2026-09-17 연구에서 관측한 다른 upstream revision은 조사 정보이며 자동 적용하지 않는다. 실제 `uv sync`, parent import, wheel, CLI/TUI smoke를 통과하기 전에는 최신 버전 호환을 주장하지 않는다.

현재 문서·계약·테스트가 개발 기준이다. 과거 응답에서만 언급되고 실제 파일이 확인되지 않은 산출물의 테스트 수나 byte 동일성을 승계하지 않는다. 추가 파일을 찾아야 하는 선행 작업 없이 이 프로젝트에서 바로 개발을 시작한다.

제품 코드 위치는 `libs/code/deepagents_code/cyrano/`, 개발 자료는 `libs/code/cyrano/`, AI 개발 작업 cwd는 `libs/code/`다. native 핵심 변경은 계획에 소유자·정확한 파일·회귀 검사를 포함한 뒤 수행한다. 설치가 자동으로 원본 파일을 덮어쓰는 것과 검토된 개발 변경은 다르다.
