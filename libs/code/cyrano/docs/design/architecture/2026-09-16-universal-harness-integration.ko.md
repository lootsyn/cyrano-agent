# Universal Harness 통합 상세 설계

문서 유형: 상세 설계 · 상태: 계획(제품 미구현)

## Problem

추가 입력 `dcode-universal-harness-design-kit.zip`은 인터뷰부터 원본 반영·학습·관측·복구까지의 통제 계약을 제공한다. 기존 스켈레톤은 DREAM 경로 A/B, 캐시 친화적 역할·skill, 13개 Python 기능 모듈와 24개 작업을 이미 갖고 있다. 문서를 나란히 복사하면 서로 다른 승인, 상태, 품질, 작업 번호가 동시에 권위가 되는 문제가 생긴다.

이번 수정은 기존 제품 범위를 줄이지 않고 원본 요구를 현 구조에 결속하는 설계·실행계획 통합이다. `references/universal-harness/`의 110개 파일은 그대로 보존한다. 그 안의 Python/config/SQL/plugin은 자동 실행·활성화하지 않는다. 입력 hash와 파일별 처리는 `references/universal-harness-import.json`, `contracts/integration/source-file-dispositions.json`이 소유한다.

## Proposal

### 1. 적용 순서와 권위

기존 소유 package와 현재 입력의 요구사항을 연결한다. 현 요구의 기계 계약은 `contracts/contract-registry.json`이 지목하는 **명시 버전/타입**이고, 적용 논리는 이 문서의 INT-01–24 및 해당 담당 상세 설계다. `references/`와 `evidence/history/`는 과거 기록으로서 현재 실행 권한이나 현재 통과 증거가 아니다. 계약과 본문이 다시 충돌하면 어느 한쪽을 추측으로 선택하지 말고 소유 WP에서 schema·문서·fixture를 함께 수정한다.

원본 0–32장 전체는 `contracts/integration/section-map.json`에, 15개 schema는 `source-contract-map.json`에, WP00–21은 `work-package-map.json`에, 124개 수용 사례는 `acceptance-map.json`에 연결한다. 현재 전체 사례 수는 tests/acceptance/catalog.json을 따른다. 명세 개수는 실행된 제품 시험 수가 아니다.

### 2. 충돌 해결 결정

| 결정 | 확인한 차이 | 통합 규칙 | 구현 소유 |
|---|---|---|---|
| INT-01 · 패키지 구조 | 첨부는 단일 cyrano_harness 패키지, 현재는 dcode namespace 아래 13개 기능 모듈이다. | 기존 deepagents_code/cyrano 모듈과 plugins/cyrano 설정을 유지하고 담당 docs/design에서 설계를 관리한다. 원본의 클래스 책임만 기존 소유 package로 이동하며 두 개의 agent loop를 만들지 않는다. | WP01, WP04, WP06 |
| INT-02 · 권위와 구현 상태 | 첨부의 문서·schema 존재와 실행 보장을 혼동할 수 있다. | references는 보존 자료다. 현재 코드, 목표 계약, 실제 실행 증거를 구분한다. 새 v2는 검증 가능한 명세이며 제품 서비스 구현 완료가 아니다. | WP00, WP22 |
| INT-03 · 계약 버전 | PlanBundle·Permit·EventEnvelope@1은 강화된 승인·변경·납품 계약을 다 담지 못한다. | v1 원문을 동결하고 governed 경로는 v2 타입을 선택한다. 명시적인 parser/semantic validation 없이 필드명 변경·default 주입·권한 승격을 하지 않는다. | WP01, WP02 |
| INT-04 · 서명 호환 | 원본 HMAC v1, 첨부 Ed25519 v2, 기존 CYRANO digest 규칙이 다르다. | 구조가 비슷해도 서명 subject는 다르다. 기존 receipt는 기록으로만 보존하고 현 계약의 정확한 화면·subject·scope를 다시 승인받는다. 새 권한으로 자동 전환하지 않는다. | WP01, WP03 |
| INT-05 · 두 상태기계 | 기존 transitions.py는 개선 후보 상태, 첨부 29개 상태는 개발 세션 상태다. | 후보 상태를 교체하지 않는다. session_state/session_guards를 별도 구현하고 세션 terminal event가 learning outbox를 연결한다. 완료한 코드와 실패한 학습은 별도 결과다. | WP07, WP16 |
| INT-06 · 계획과 납품 | 기존 WorkUnit의 write_paths만으로 생성·삭제·원본 적용을 구분할 수 없다. | GovernedWorkUnit에 create/delete/only_write·검증 recipe·preimage를 보강한다. GovernedWorkPlan.delivery_mode는 patch_only/apply_to_source이며 approval subject에 들어간다. | WP09, WP10 |
| INT-07 · only_write | 파일 시스템 mount로 쓰기 전용을 선언해도 읽기와 별칭 접근이 가능할 수 있다. | only_write는 broker가 소유한 쓰기 전용 sink다. agent/test에 읽을 수 있는 fd/mount/별칭을 주지 않는다. 제공 환경이 이를 강제하지 못하면 해당 permission은 unsupported다. | WP03 |
| INT-08 · 리뷰 강도 | 첨부 prose의 위험도별 blind 검토와 config의 필수 reviewer가 완전히 같지 않다. | 모든 spec은 critic+blind, 모든 plan은 plan-reviewer, 모든 최종 산출물은 code-reviewer가 검토한다. high/critical은 security-reviewer를 추가한다. 동일 모델 사용은 독립 통계 표본을 뜻하지 않는다. | WP05, WP08, WP09 |
| INT-09 · 품질 정책 | 첨부는79자/설명72자, 기존 pyproject는88자다. | 이 프로젝트 목표 정책을79/72로 통일한다. 기존 코드 위반은 baseline audit에 남기고 WP00에서 도구 고정, 각 WP와 WP22에서 수정한다. 설정 변경만으로 전 코드 준수를 주장하지 않는다. 고객 프로젝트 규약은 별도 승인 대상으로 유지한다. | WP00, WP22 |
| INT-10 · 학습 기본값 | 첨부 예시에는 learning.enabled=true, 기존 준비 프로젝트는false다. | 실제 실행·학습·자동 승격·canary·원격 trace 모두 기본 비활성을 유지한다. 배포에 대한 동의가 외부 호출이나 자동 변경에 대한 포괄적 동의가 아니다. | WP16, WP23 |
| INT-11 · 보존 정책 | 첨부 본문과 예시 config의 payload/audit 보존 수치가 다르다. | 현재 제안은 metadata30일·redacted body7일·승인/정책 최소 metadata180일·평가 요약365일이다. raw secret은 보존하지 않는다. 숫자는 운영자가 승인할 기본 가설이지 법적 보존 결론이 아니다. | WP11, WP13, WP22 |
| INT-12 · 캐시와 기억 | memory를 고정 prefix에 매번 재작성하면 적극 recall과 cache가 충돌한다. | memory release는 epoch에 고정하되 query view는 task별 동적 tail이다. 선택한 안정 기억만 epoch 시작에 동결할 수 있다. 삭제·보안 철회는 cache 이점보다 우선한다. | WP05, WP11 |
| INT-13 · 로그와 비밀 | model-visible 재현성과 원문 무기한 보관은 같은 요구가 아니다. | 모델에 도달한 구성은 manifest로 식별하고 허가된 본문만 보관한다. 원문이 삭제되거나 처음부터 보존되지 않았다면 exact replay unavailable로 보고한다. 임의로 요약을 원문인 것처럼 대체하지 않는다. | WP13, WP14 |
| INT-14 · 전체 모니터링 | 모델/도구 callback만으로 native summarization·retry·child까지 관측했다고 할 수 없다. | 65개 typed event와 실제 경로 coverage matrix를 따로 둔다. 필수 control/audit 누락은 차단한다. provider가 제공하지 않는 cache metric은 지원 불가/unknown으로 표시하며 필수 보안 누락과 구분한다. | WP06, WP13 |
| INT-15 · 이벤트 revision | 매 token/telemetry가 control revision을 올리면 실행 중 계약이 계속 무효화된다. | event_seq는 저장 순서, producer_seq는 생산자 순서, control_revision은 업무 의미 변경에만 증가한다. subject가 바뀌지 않은 일반 관측은 새 권한 발급 사유가 아니다. | WP02, WP13 |
| INT-16 · 비용 | retry·부모 span 합산과 timeout 즉시 환불은 예산을 잘못 계산한다. | 실제 billable leaf attempt별 기록을 합산하고 parent는 별도 합계가 아니다. 가격/usage 불명은 null이며 미결 비용 예약을 outstanding liability로 유지한다. provider 지원 없는 exactly-once를 보장하지 않는다. | WP09, WP13, WP20 |
| INT-17 · 리플레이와 경로 B | 첨부 generic self-improvement가 기존 DREAM의 조건을 생략할 수 있다. | A는 입력 서명·부모·추가 dependency·모델/endpoint가 같은 지원 전이만 재사용한다. B의 기억/skill/질문/context/recipe/code 변경은 실제 paired 평가가 필요하며 old evaluation 재사용을 거부한다. | WP14–WP20 |
| INT-18 · 테스트 중복 | 원본 R01–R22가 세 개 자료에 존재한다. | 시나리오 내용은 보존하되 canonical INT-R01–22를 재사용한다. source124개 중 나머지102개는 UH- prefix, 새로운 통합 사례24개는 INTEG- prefix로 별도 관리한다. fixture 수가 독립 corpus 수가 되지 않는다. | WP07, WP20, WP22 |
| INT-19 · 개발 작업 번호 | 원본 WP00–21과 기존 WP00–23의 의미가 다르다. | 기존24개 작업 ID를 유지한다. source_work_packages에 universal:WPxx로 이름공간을 넣고 mapping JSON으로 연결한다. 번호순이 아니라 DAG가 실행 순서를 정한다. | 전체 WP |
| INT-20 · 초기 구축 승인 | 전체 governed 검증을 WP00 선행으로 요구하면 아직 만들지 않은 WP03/06에 의존한다. | WP00은 bootstrap 검증만 담당한다. 초기 개발은 외부 사람 리뷰와 제한된 사본으로 승인한다. 실제 adapter/governed/operational 검증은 담당 WP 완료 후 수행하며 자동 advisory fallback은 없다. | WP00, WP03, WP06, WP22 |
| INT-21 · API와 tool | 첨부 resource endpoint와 기존 generic command ingress가 다르다. | 기존 명령형 control ingress를 유지하고 payload_schema_ref로 타입을 고정한다. 필요한 조회/제안 tool만 추가한다. 모델에게 approve/grant/mark_ready/set_state 권한을 주지 않는다. | WP01, WP06, WP09 |
| INT-22 · SQL 병합 | 두 SQL 파일을 순서대로 executescript하면 기존 데이터와 의미를 검증하지 못한다. | 현재 Store schema, 기존 target-schema, 신규 governance extension을 세 단계로 구분한다. versioned migration·backup·dry-run·row/digest/ACL 검사를 WP02에서 구현한다. 첨부 DDL을 자동 적용하지 않는다. | WP02, WP19 |
| INT-23 · 원본 반영 실패 | 멀티파일 적용 중 일부만 바뀌거나 취소된 상태를 rollback 완료로 오인할 수 있다. | prepare/apply/verify journal을 기록한다. 부분 결과와 unknown effect를 먼저 reconcile하고 현재 preimage에 대한 별도 복구 승인을 받는다. harness pointer rollback은 사용자 코드 rollback이 아니다. | WP10, WP21, WP22 |
| INT-24 · 40점 증거표 | 문서와 기반 테스트가 있다고 항목 점수를 미리 줄 위험이 있다. | 사용자 15개 criterion은 제품 실행 증거로만 채점한다. 현재 scorecard는 not_evaluated/0이고 hard gate는 not_tested다. 점수로 승인 우회·비밀 유출·거짓 완료를 상쇄하지 않는다. | WP22, WP23 |

### 3. 런타임 책임 분리

Control plane은 신뢰된 사용자 이벤트·승인·scope ACL·상태·검증 판정·active release·outbox를 소유한다. Agent plane은 dcode와 얇은 Python extension, 허가된 context와 제안 tool만 가진다. Execution plane은 broker가 발급한 한정 permit으로 실제 명령·변경을 수행한다. 동일 OS 사용자 프로세스를 둘로 나누는 것만으로 강제 경계를 만들었다고 하지 않는다.

`../deepagents_code/cyrano/dcode`는 native dcode 연결과 관측 port를 담당하고 `deepagents_code.cyrano.kernel`은 승인·정책·세션 전이, `deepagents_code.cyrano.workflow`는 작업 분배와 검증·납품, `deepagents_code.cyrano.sqlite`는 원자 저장을 담당한다. extension이 control DB나 서명키에 직접 접근하지 않는다. 모든 모델 역할의 authority는 proposal_only이며 `security-reviewer`도 서명권자가 아니다.

### 4. 인증·계약의 처리 알고리즘

외부 mutation은 다음 순서다: payload byte/depth 제한 → 중복 JSON key/비정상 숫자/문자 거부 → 명시 `(kind, schema_version)` 선택 → JSON Schema → semantic validation → 인증 actor와 scope 확인 → 참조 artifact 존재와 digest 확인 → expected control revision/CAS → 목적별 permit/approval 확인 → state/event/outbox/idempotency receipt 원자 저장. 입력의 `passed`, `approved`, `target_state`를 권위로 읽지 않는다.

`TrustedApprovalReceipt`는 승인 action, 사용자·화면 이벤트, 표시 문서 digest, scope, runtime/policy/plan/release binding, budget, nonce, 유효기간, issuer를 정확히 결속한다. `ToolExecutionPermit`는 이를 축소한 실행 능력이며 WorkUnit·tool inventory·sandbox·fence·preimage·횟수·시간·출력 한도에 추가 결속한다. 권한 축소만 가능하다. 부모 승인 만료/철회/정책 epoch 변경이면 파생 permit도 무효다.

v2 signer는 `contracts/v2/digest-projections.json`의 subject 필드와 CYRANO-C14N-1을 사용한다. signature/attestation와 자기 digest는 subject에서 분리한다. scope/input/status 변경으로 서명 대상이 달라지면 이전 서명을 새 JSON에 붙이지 않는다. 검증키와 issuer allowlist는 모델이 변경할 수 없다. 테스트용 키는 production trust root로 등록하지 않는다.

### 5. 정확 파일 권한과 WorkPlan

`GovernedWorkUnit.write_paths`는 기존 파일 수정만 의미한다. 신규 파일은 `create_paths`, 삭제는 `delete_paths`, 읽을 수 없는 산출물 sink는 `only_write_paths`로 구분한다. 최종 permission은 조직·사용자·workspace·세션·사람 승인·역할·work unit grant의 교집합, deny는 합집합이다. 생략된 grant는 무제한이 아닌 빈 권한이다. 경로는 root_id 아래 정확한 상대 경로이며 wildcard/절대 경로/경로 이탈/제어 문자를 허용하지 않는다.

JSON 경로 검사는 1차 검사다. broker는 실제 열리는 대상의 root·inode·symlink/hardlink·case alias·TOCTOU를 확인하고, 원본 source는 read-only로 제공한다. 명령은 shell 문자열을 보간하지 않고 고정 recipe+argv 리스트로 해석한다. 테스트가 실행하는 프로젝트의 conftest·build hook·plugin도 코드 실행이다. 필요없는 네트워크·자격증명·host socket·승인 원장은 mount하지 않는다.

계획에는 요구사항과 수용 ID, input/preimage, 단계별 기대 관측, 실패 처리, 검사 recipe/기대 evidence, done_when, rollback, 총 예산, 독립 reviewer가 모두 필요하다. requirement→WorkUnit→verification의 양방향 연결을 검사한다. 단순 `pytest` 명령을 문자열로 남긴 것이 아니라 어떤 결과가 완료를 입증하는지 명시한다.

### 6. 세션 전이와 완료 판정

`contracts/v2/session-state-machine.json`의 29개 세션 상태와 `candidate` 상태는 서로 다른 aggregate다. 세션 전이는 현재 상태·신뢰된 사건·현재 binding에 대한 guard 결과로만 결정한다. 세부 guard 입력·오류·근거는 `session-guards.json` 및 [guard 구현 명세](../../subsystems/governance-guards.ko.md)에 있다. 일반 caller가 next state를 정하지 않는다.

기본 작업 경로는 intake→interview→spec 검토/승인→plan 검토/승인→execution 허가→실행→검증→최종 리뷰다. `patch_only`이면 검증된 변경 manifest와 패치 전달 evidence로 완료할 수 있지만 `apply_to_source`이면 추가 승인→실제 원본 적용→적용 후 최종 검사가 더 필요하다. 다른 delivery mode로 전환하면 계획과 그 승인·평가를 다시 결속한다.

`RunnerVerification`은 프로세스 종료, artifact correctness, requirement acceptance를 혼동하지 않는다. 테스트 0개·전체 skip·runner setup 실패는 관련 수용 완료 증거가 아니다. TDD red는 예상된 중간 관측이지 제품 검증 성공이 아니다. 재작업으로 postimage가 달라지면 그 영향의 검증·리뷰는 다시 실행한다.

`CANCELLING`은 신규 dispatch를 먼저 정지시키고 이미 시작한 작업을 정리하는 상태다. unknown side effect가 있으면 CANCELLED/FAILED/COMPLETED를 확정하지 않는다. `PAUSED`에서 caller가 임의 상태로 resume하지 않고 저장된 checkpoint와 현재 guard로 복귀한다. 사용자 요구 변경은 관련 결정·plan·review·approval·memory view를 역의존 관계로 무효화한다.

### 7. 인터뷰·프로필·역할

원본 R01–R22의 readiness 의무, 사용자 의도/관측 사실/가설 분리, 제한된 위임, 늦은 worker 결과 처리, 독립 blind handoff를 유지한다. source의 역할명과 제품의 kebab-case 역할은 명시 adapter table로 연결하며 이름 정규화만으로 권한을 부여하지 않는다.

`ResolvedTaskProfile`은 phase·task_kind·risk·권한·budget·필수 review를 합성한 결과다. 모델 이름 조건문은 없다. 기본 동시 worker 3개와 worker의 자식 spawn 0은 조정 가능한 제안 정책이며 조직 상한보다 커질 수 없다. 독립 검토는 작성자의 대화와 다른 reviewer 답을 숨기는 입력 격리·별도 실행 ID로 구현한다. 다른 모델을 썼다는 사실만으로 독립성을 입증하지 않는다.

인터뷰 export는 사용자가 본 원문/질문/답·결정 원장·SPEC·ACCEPTANCE·OPEN_QUESTIONS·evidence index·현재 review·명세 승인 binding을 포함한다. 명세 승인 export에 execution permit을 암묵적으로 생성하지 않는다. 사용자 답변이 없는 항목을 모델이 채워 넣으면 가설로 남기고 required obligation 해결로 세지 않는다.

### 8. Cache-aware Memory와 Skill

고정 lifetime을 공통 규칙→현재 release/역할/도구 catalog→동결된 skill metadata로 나눈다. 현재 user request, decision IDs, 작업 상태, 선택된 memory view, approval nonce, usage, 시간은 dynamic tail에 둔다. source의 L0–L5와 현 compiler 블록 수를 숫자로 일대일 대응시키지 않고 lifetime으로 매핑한다.

INTAKE/PLAN/IMPLEMENT/VERIFY/REVIEW에서 각각 적합한 기억을 적극 조회한다. tenant/user/workspace/session/task ACL을 relevance/top-k 전에 적용한다. MemoryAccessBinding으로 기억 release와 현재 query view를 구분한다. queried/selected/injected/referenced/applied는 다른 사건이며 applied는 plan diff·tool/verification evidence와 연결한다. 단순 hit 수를 개선 효과로 보고하지 않는다.

skill은 metadata→본문→resource 순서로 읽는다. 모든 skill 내용을 시스템 프롬프트에 붙이지 않는다. skill text/resource/code 변경은 전체 artifact manifest에 포함하고 새 release·epoch를 만든다. native /remember와 직접 AGENTS 수정 경로도 candidate 제출 경로로 통제한다. 비밀/권한/의무를 제거해 얻은 cache hit은 최적화가 아니다.

캐시 관측은 local digest, wire 관측, token 측정 출처, provider usage semantics를 별도로 기록한다. unknown을0으로 계산하지 않으며 모델/endpoint 변경 시 캐시 연속성이나 TTL을 추측하지 않는다. 보안 revoke/삭제는 active run에도 pause/invalidate를 적용하며 prefix 보존을 이유로 지연하지 않는다.

### 9. 관측·예산·보존

`GovernedEvent`는 metadata envelope이며 payload는 `event-catalog.json`이 정한 65개 개별 JSON Schema 중 하나다. payload_type, envelope event_type, payload 내부 event_type의 일치를 검사한다. producer ID는 연결에서 인증하며 body의 문자열만 신뢰하지 않는다. typed event의 required_on_read=true를 이해하지 못하는 소비자는 무시하지 말고 projection을 거부한다.

도메인 event/control mutation과 큰 redacted blob은 분리한다. 필수 audit event 저장 실패는 부작용 전에 차단하고 실행 후 실패이면 unknown/gap 경보와 reconcile을 남긴다. SSE는 scope 필터와 event_seq cursor를 사용하며 duplicate event_id를 제거한다. 대시보드는 8개 화면을 제공하고 승인 mutation은 인증·origin/CSRF 검사된 별도 경로다. loopback bind만으로 인증됐다고 하지 않는다.

모델 비용은 billable leaf별 실제 provider 보고값을 우선 사용한다. inference trace parent와 child를 동시에 합산하지 않는다. 호출 전 조직/run/experiment 잔여 예산을 원자 예약한다. timeout·usage 누락은 cost0 환불이 아니라 liability 유지다. 사용자 수정·예상 TDD red·정상 권한 거부·일시 환경 오류를 무조건 실패 학습 신호로 삼지 않는다.

보존 policy는 삭제/정정 요구를 우선 반영한다. 삭제 대상의 projection, index, export, backup 복원 시 tombstone 적용, replay dependency를 추적한다. 최소 감사 metadata를 남기더라도 원문을 그대로 복사하지 않는다. 외부 trace는 별도 승인 전 꺼져 있고, provider로 이미 보낸 내용의 반환 삭제까지 이 프로그램이 보장한다고 하지 않는다.

### 10. Self-improvement A/B와 평가

경로 A는 관측 가능한 branch history와 지원되는 recorded transition만 사용한다. parent 외 다른 branch 결과를 읽었다면 dependency edge를 기록한다. 없는 transition은 out_of_support이며 임의 성공/실패나 유사 실행으로 대체하지 않는다. hidden 미래 결과를 정책 프로세스에 전달하지 않는다.

경로 B는 기존 8개 변경 lane의 세부 설계를 유지한다. 학습계획은 원인 가설과 대안 설명, scope, exact diff, 보호 표면 영향, 최소 효과/비회귀 기준, 실험 corpus, 전체 비용 상한, rollback을 포함한다. candidate-author와 impact classifier, evaluator, release approver를 분리한다. static config 변경도 모델 입력 의미가 달라지면 B다.

실제 비교는 동일 task snapshot과 승인된 runtime/model/endpoint/budget 조건에서 baseline/candidate를 짝지어 수행한다. project-family와 시간 split을 사전 고정하고 holdout 공개·재사용 횟수를 제한한다. 같은 corpus 반복 실행은 독립 family 수를 늘리지 않는다. 모델 교체를 지원하되 모델별 custom policy를 배포하지 않는다. 품질 불확실·필수 측정 누락·표본 부족은 inconclusive다.

승격은 평가 결과와 다른 사건이다. evaluation이 eligible_for_review라고 해도 사람 또는 좁게 위임된 권한의 승인과 exact release subject가 필요하다. baseline pointer가 바뀌면 재base·재평가한다. 일반 활성화는 새 세션부터 적용하고 보안 철회는 진행 중 작업을 멈춘다. 하네스 rollback, workspace 복구, DB migration rollback을 각각 보고한다.

### 11. 저장·migration

현재 SQLite Store는 기반 실험 구현이다. 기존 target-schema.sql은 목표 스키마로서 migration이 아니다. 새 governance SQL은 별도 staging 영역이며 원본첨부 DDL을 기존 DB에 덧붙여 실행하지 않는다. [저장 전환 명세](../../subsystems/governance-storage.ko.md)의 표에 따라 current→target→governance binding을 단계별 구현한다.

데이터 이동 시 row count뿐 아니라 tenant/scope, entity digest, graph edge, signature 원문, event 순서, idempotency 결과, 미결 외부 실행, deletion tombstone을 비교한다. 서명을 다시 만드는 migration은 데이터 변환이 아니라 새 승인이다. write enable 전 backup restore drill과 post-migration invariant를 통과해야 한다.

## Alternatives considered

**첨부 ZIP 전체를 실행 기준으로 교체:** 경로 A/B·24개 작업·기존 fixture와 소비자를 잃고 권한 계약이 암묵 변환되므로 채택하지 않았다.

**부록 링크만 추가:** 생성/삭제/납품/상태/quality 충돌을 구현자가 다시 결정하게 하므로 채택하지 않았다. 새 규칙은 schema/config/WP/검사에도 반영한다.

**모든 내용과 기억을 상시 prompt로 주입:** 일관성을 높인다는 명분으로 context·cache·최소권한을 악화시키므로 채택하지 않았다. progressive loading과 source manifest를 사용한다.

## Acceptance criteria

110개 입력 파일 hash, 33개 장 소유, 15개 source schema mapping, 124개 source case mapping, 기존24WP DAG, 현재 canonical scenario owner, v1 schema 불변, v2 schema·projection·event payload·safe defaults를 기계 검사한다. 이 패키지 검사는 실제 승인 강제나 모델 효과의 증거가 아니다. 제품 완료는 각 WP의 실제 실행 evidence와 독립 결과 review 및 WP22/23 판정이 필요하다.

## Risks

더 엄격한79/72·typed event·권한 계약은 기존 기반 코드와 개발 비용을 늘린다. 초기 bootstrap은 CYRANO가 아직 강제하지 못하므로 외부 사람 검토와 격리 사본을 사용한다. 제공자 내부 cache/재시도·OS 권한·원본의 외부 동시 수정은 실측 없이 보장할 수 없다. 미지원 기능은 알려진 제한과 blocker로 남기고 기능을 몰래 끄거나 보호 수준을 낮춰 출시하지 않는다.
