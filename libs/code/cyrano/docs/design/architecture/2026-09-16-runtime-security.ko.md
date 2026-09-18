# dcode 연결·승인·격리·복구

문서 유형: 상세 설계 · 상태: 계획(제품 미구현)


## Problem

extension이 시작됐다는 로그, 모델의 승인 주장, 로컬 파일의 permission 설정만으로 governed 실행을 보장할 수 없다. dcode는 extension setup 실패 뒤 다른 extension을 계속 로딩할 수 있고 native tools·subagents·shell 경로가 별도로 존재한다. 설치와 실행을 별도 probe 없이 자동 허용하면 중요한 경계가 빠진다.

## Proposal

### 통합 R2 실행·승인

governed 신규 실행은 TrustedApprovalReceipt/ToolExecutionPermit@2를 사용한다. legacy Permit을 자동 전환하지 않는다. 승인 purpose, 화면digest, actor, policyepoch, scope, tool inventory, sandbox, preimage, budget, nonce를 검증한다. only_write는 agent가 읽을 수 없는 broker sink이며 OS강제가 불가능하면 unsupported다. bootstrap/adapter/governed/operational probe를 나누고 WP00만으로 fullgov를 인증하지 않는다.

자세한 해석·충돌 해결은 [Universal Harness 통합 설계](2026-09-16-universal-harness-integration.ko.md)를 따른다. 원본첨부에 있는 더 느슨한예시로 이규칙을낮추지 않는다.

### 1. 공식 확장 표면의 사용

배포 plugin은 version 있는 manifest와 async `extension(d)`를 사용한다. factory는 `register_middleware(instance)`, `register_tool(callable)`, 필요한 경우 `register_backend_route(prefix, storage)`, `on_shutdown(callback)`만 호출한다. callback의 sync/async 의미·도구 override 충돌·재시작 필요 여부는 설치된 버전에서 검증한다 [S04].

custom slash command, TUI thread state 직접 변경, 존재를 확인하지 않은 headless flag, virtual backend를 shell mount로 간주하는 코드는 작성하지 않는다. CYRANO의 사용자 command는 외부 CLI/API이며 native `/restart` 같은 실제 제공 명령과 구분한다.

현재 `plugins/cyrano/extension.py`는 명시적 advisory diagnostic만 제공한다. 기본 환경에서 미구현 governed runtime을 켜지 않고 오류를 낸다. 이것을 검증된 extension 제품으로 표시하지 않는다. WP06은 공식 registrar에 실제 port를 연결하고 launcher health attestation을 구현한다.

### 2. RuntimeCompatibilityReport

필수 항목은 installed artifact version/hash, dcode entrypoint, plugin load health, actual async middleware callbacks, native tool inventory, subagent inheritance, source write interception, shell route, approval source binding, sandbox mount/isolation, shutdown/cancellation, headless output parsing, context binding이다. 결과는 `verified`, `unsupported`, `failed`, `not_tested`다.

설치 버전이 문서의 관측 버전과 같아도 자동 verified가 아니다. `runtime-lock.template.json`의 null을 가짜 hash로 채우지 않는다. wheel/source metadata·resolved dependency graph·probe commands·exit status·receipt를 수집해 새로운 runtime-lock을 생성한다. 실행 테스트가 없는 capability는 그대로 not_tested다.

### 3. Governed launch 순서

1. launcher는 외부 CYRANO_HOME을 canonicalize하고 target repo 내부인지 거부한다.
2. root가 소유한 정책·release·runtime lock의 hash와 승인 상태를 검사한다.
3. 모든 필수 compatibility probe와 실제 actor principal 분리를 확인한다.
4. source snapshot을 생성하고 비밀 제외·허용 untracked manifest를 고정한다.
5. control service, broker, execution sandbox, dcode server를 명시 구성으로 시작한다.
6. extension health handshake와 tool inventory receipt를 받는다. dcode가 extension 오류를 무시하고 계속 떠도 launcher는 dispatch하지 않는다.
7. limited run token을 발급하고 현재 context epoch를 bind한다.
8. 확인된 상태 이후에만 사용자 업무를 dispatch한다. 하나라도 실패하면 종료·cleanup·진단을 남기며 advisory로 자동 전환하지 않는다.

### 4. 권한과 permit

command envelope는 authenticated principal, exact Scope, expected_revision, idempotency_key, purpose, payload digest를 가진다. transport payload가 principal 값을 바꿔도 인증에서 얻은 identity를 덮어쓰지 않는다. permit은 issuer, audience, action, resource scope, snapshot·bundle·policy digests, expiry, nonce, revocation revision, signature를 묶는다. 서명키는 Control Plane만 소유한다.

서명 검증은 메시지 인증일 뿐 명령 안전성 전체가 아니다. 실행 시 현재 revocation·resource snapshot·허용 경로·action class를 다시 검사한다. approval receipt를 다른 목적의 tool permit으로 재사용할 수 없다. nonce replay는 action별 소비 정책에 따라 차단하고 unknown outcome에서는 중복 실행 대신 reconciliation한다.

보안 프로토콜은 검증된 암호 라이브러리와 독립 review를 사용한다. hand-rolled RSA/HMAC parsing을 작성하지 않는다. 초기 local auth 구현이 단순해도 같은 OS 사용자 공격을 막는다고 주장하지 않는다.

### 5. Source writer와 test 실행

Agent와 임의 tool 코드에는 source snapshot을 readonly로 제공한다. 변경은 broker `apply_patch`가 approved WorkUnit 경로와 patch digest·baseline snapshot을 검사한 뒤 수행한다. 새로운 snapshot을 atomic publish한다. agent에 write 가능한 source 전체를 mount한 후 사후 diff만 확인하는 것은 범위 강제가 아니다.

pytest cache, bytecode, build output은 scratch/env에 둔다. 쓰기 필요한 generator recipe는 정확한 생성 경로·side effect를 사전에 허가받는다. 보호된 source 파일을 테스트가 덮어쓰게 하지 않는다. user original repo로 patch를 적용하려면 별도 apply approval·현재 dirty tree 검사·충돌 검증·실제 최종 테스트가 필요하다.

경로 검사는 symlink escape, `..`, Windows drive/UNC/case, hardlink·mount alias, archive extraction traversal, 비정상 파일 유형을 포함한다. shell command 문자열 필터만으로 방어하지 않는다. sandbox syscall/mount/network 정책이 임의 프로세스의 실행 가능 범위를 제한한다. Docker socket, host credential, privileged flag는 제공하지 않는다.

### 6. Tool interception과 native 경로

실제 dcode의 읽기·쓰기·shell·subagent·backend route·custom tools 전체를 inventory로 고정한다. extension tool은 built-in approval map에 자동 포함되지 않으므로 sensitive operation은 broker를 통과한다. 이름 충돌을 이용한 built-in 교체는 allowlist와 compatibility test 없이는 거부한다.

virtual `/cyrano-memory/`는 model file tool 경로이며 shell에서 자동 보이지 않는다. model memory tool은 조회·후보 제안만 허용하고 active memory write를 허용하지 않는다. native remember 동작이 active projection에 쓰려 하면 candidate 제출로 연결하거나 deny한다. 실제 차단 불가능한 버전에서는 governed memory mutation을 지원한다고 주장하지 않는다.

### 7. Transaction과 outbox

모든 domain mutation은 validation → authentication/authorization → expected_revision → transition preconditions → event append + state projection + idempotent response + outbox를 단일 DB transaction으로 commit한다. idempotency key는 principal/scope/command namespace 안에서 유일하다. 같은 key와 같은 canonical request는 같은 response, 다른 payload는 IDEMPOTENCY_CONFLICT다.

outbox는 at-least-once delivery다. claim은 lease와 증가하는 fence를 발급한다. 오래된 worker는 새 fence에 대해 result를 commit할 수 없다. worker가 외부 API를 호출한 뒤 crash하면 unknown outcome이다. provider request ID·idempotency 지원·로그로 확인할 수 없으면 자동 재실행 대신 review 대기한다.

SQLite foundation은 CAS/outbox/lease 원리를 구현하지만 tenant auth·full production schema·파일 암호화·replication은 별도 작업이다. SQLite WAL을 네트워크 파일시스템에 무조건 배치하지 않으며 다중 host 요구가 생기면 transaction 의미를 유지하는 DB adapter를 설계한다.

### 8. 종료·복구

cancel은 사용자 의도를 먼저 기록하고 새 dispatch를 막는다. 실행 중 작업에는 cancellation을 전달하되 이미 수행된 외부 side effect가 취소되었다고 가정하지 않는다. 결과 미확인 작업은 unknown 상태로 남긴다. child process group 종료, timeout escalation, disposer reverse-order, partial setup cleanup을 검사한다.

startup recovery는 pending outbox·lease expiry·running attempts·active release pointer·incomplete artifact publish를 reconcile한다. temp directory가 있으나 manifest가 봉인되지 않았으면 active release로 로딩하지 않는다. 기존 schema가 future version이면 무시하고 읽지 말고 unsupported로 중단한다.

### 9. Remote exports·개인정보

local control metadata가 기본 진실 원천이다. 외부 LangSmith/OpenTelemetry exporter는 선택적이며 raw source·prompt 전송은 기본 off다. secret redaction은 저장·전송 전 적용한다. redaction 실패는 quarantine metadata를 남기고 body를 전송하지 않는다. trace 삭제는 외부 서비스 삭제 의무까지 별도 추적한다.

로그에는 private chain-of-thought, API key, 승인키, bearer token을 기록하지 않는다. source context를 마스킹했으면 완전 재현 가능하다고 주장하지 않는다. metrics labels에 task ID·model prompt 전체를 무제한 넣지 않고 상세 trace에 연결한다.

## Alternatives considered

**모든 권한을 middleware bool로 보호:** 임의 shell·subagent 경로가 우회할 수 있다. 실제 OS 경계와 broker 실행 검사를 결합한다.

**hook nonzero exit는 모두 차단:** 네이티브 semantics가 다르다. hook은 관측 보완이며 승인 enforcement를 맡기지 않는다.

**실패한 governed 자동 advisory fallback:** 사용자에게 보안 수준 변화가 숨겨진다. 별도의 명시적 선택만 허용한다.

## Acceptance criteria

AUTH/REL/RUNTIME 수용 테스트에서 fake approval, stale receipt, wrong audience, replay nonce, source dirty mismatch, cross-workspace, symlink escape, native shell bypass, child agent bypass, disabled extension, setup failure, lease fence, crash 후 unknown outcome이 올바르게 차단/보고돼야 한다. same-principal advisory 환경에서는 governed 보장 자체를 거부해야 한다.

## Risks

지원 OS·sandbox 구현별 제한이 다르다. macOS/Windows 개발 모드와 Linux governed 환경을 같은 보장으로 표시하지 않는다. production launch 허용은 UI checkbox가 아니라 실제 probe evidence에 묶는다.
