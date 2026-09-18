# 실행계획: 첫 부팅부터 실제 운영까지

문서 유형: 실행계획 · 상태: 제품 구현 후 수행할 절차와 현재 준비 절차를 구분


## Problem

실행계획이 개발계획과 분리되지 않으면 압축파일을 받자마자 유료 학습·운영 명령이 실행되거나 구현하지 않은 기능의 CLI를 성공적으로 실행했다고 오해할 수 있다. 현재 가능한 명령과 구현 후 승인된 환경에서 할 명령을 분명히 나눠야 한다.

## Proposal

### 통합 R2 실행 기준

본운영workflow와함께2026-09-16-integrated-development-execution.ko.md의WP별구현/검사/인수를사용한다. runtime검증은bootstrap/adapter/governed/operational로구분한다. 실제모델/학습/승격/canary/export는별도활성허가대상이다. 이전준비검사결과는history이고이번결과만currentevidence다.

자세한 해석·충돌 해결은 [Universal Harness 통합 설계](../design/architecture/2026-09-16-universal-harness-integration.ko.md)를 따른다. 원본첨부에 있는 더 느슨한예시로 이규칙을낮추지 않는다.

### 1. 지금 실행 가능한 준비 확인

Python3.12 이상이 설치된 환경에서 압축파일 최상위 디렉터리로 이동한다. 아래 명령은 외부 모델을 호출하거나 고객 repo를 수정하지 않는다.

```sh
python cyrano/scripts/dev.py status
python cyrano/scripts/dev.py demo-context
python cyrano/scripts/dev.py demo-impact
python cyrano/scripts/dev.py check
```

`check`는 실제 foundation tests와 repository hygiene를 실행한다. JSON Schema 검증 도구가 있는 경우 `python cyrano/scripts/dev.py schemas`를 추가한다. `python cyrano/scripts/dev.py quality`는 필요한 Ruff/ty가 없으면 blocked로 종료한다. 임의 설치·상위 권한 요청·외부 실행으로 우회하지 않는다.

### 2. 개발환경 고정

일반 네트워크 사용이 허용된 개발 환경에서는 `uv sync --locked`로 로컬 workspace를 설치한다. 첫 build backend 다운로드가 필요할 수 있다. lock은 13개 로컬 distribution을 포함하고 dcode/API provider를 설치하지 않는다. 별도 검토 후 `tools/quality/requirements.in`을 resolve하여 quality lock을 작성하고 설치한다. lock을 손으로 만들어 설치 검증을 흉내내지 않는다.

WP00은 `runtime/requirements.in`에 기록한 dcode 관측 버전을 실제 설치/검증해 runtime-lock으로 만든다. upstream main의 version 문자열은 설치된 wheel 검증 결과가 아니다. 설치 조합이 불가능하면 이를 보고하고 호환되는 새 artifact를 운영자가 명시 승인하도록 한다. 조용히 다른 SDK agent로 대체하지 않는다.

### 3. 구현 에이전트에 작업 전달

`IMPLEMENTATION_REQUEST.ko.md`를 먼저 전달한다. coordinator는 `.agents/work/plan.json`에서 선행 verified와 write resource lock을 만족하는 WP를 고른다. 처음에는 WP00/WP01의 조사·계약 작업부터 시작한다. 각 worker에는 WP 파일, 해당 note, 소유 package README, 필요한 schema/fixture만 전달한다. FULL_DESIGN 전체를 매 model request마다 system prompt에 넣지 않는다.

worker는 계획 draft→독립 사전 review→구현→targeted tests→결과 review→evidence→상태 전환 순서를 지킨다. 코드·계약·data migration에 영향을 주는 수정은 관련 consumer와 tests를 같이 갱신한다. 구현 도중 새로운 중요한 모호성이 발견되면 허가 범위 안의 기술 선택은 기록해 결정하고, 사용자 목적/권한 변경은 trusted 입력 없이는 확정하지 않는다.

### 4. 승인과 외부 행동

이번 ZIP 생성 요청은 원격 commit/push·고객 저장소 변경·운영 배포·유료 LLM 실험·자동 학습 켜기에 대한 승인이 아니다. 구현 에이전트는 명시적으로 허가된 개발 scope 안에서 작업한다. key가 파일에 있다는 이유로 paid evaluator를 실행하지 않는다.

초기 configs는 network/live_model/learning/auto_promotion/remote_trace가 off이고 canary0이다. 이것은 기능 제외가 아니라 안전한 최초 실행 상태다. 기능 구현 후 runtime compatibility·목적별 approval·예산을 모두 갖춘 경우에만 별도 command로 활성화한다.

### 5. 실제 dcode integration 단계

WP06을 구현한 후 검증된 명령과 실제 adapter entrypoint만 문서에 추가한다. 현재 미구현 `cyrano run`, `cyrano approve`, `cyrano learn`를 사용하는 예제는 이 계획에 없다. launcher가 extension health를 확인하고 source·principal·권한을 고정한 뒤 안전한 probe task부터 실행한다.

첫 integration은 read-only fact inspection, 허가된 scratch write, scope 밖 write 거부, native shell·subagent 경계, cancellation·unknown outcome을 확인한다. 모든 probe를 통과하기 전 고객 업무나 자동 B 학습으로 넘어가지 않는다.

### 6. Seed data와 학습 시작

개발 task의 실제 terminal events에서 episode를 수집한다. test fixture를 실제 성공/실패 경험으로 학습 corpus에 넣지 않는다. 최초 충분한 사례가 없으면 observation mode로 유지하고 데이터가 부족하다고 보고한다. artificial task는 synthetic이라는 origin과 별도 split을 가진다.

A는 supported replay world를 만들고 bounded policy 후보를 선별한다. B는 학습계획·candidate·impact를 만든 뒤 actual paired evaluator로 검증한다. 두 경로 모두 최종 actual evidence·independent review·trusted promotion authority가 있어야 release를 만든다.

### 7. 운영 도입 순서

기능 통합→OS 보안·복구 drill→사전 등록된 실제 paired study→독립 결과 검토→운영자 승인→새 run 일부 대상 canary→후속 품질·비용·누락 관측 순이다. 효과가 inconclusive면 baseline을 유지하고 실험을 더 할지 운영자가 판단한다. 기능이 동작한다는 이유로 사용자 업무 성공률 개선을 단정하지 않는다.

### 8. 중단·재개·복구

권한 철회·source 변경·예산 소진·미지원 runtime·보안 사건은 새 dispatch를 멈춘다. 진행 외부 행동은 취소 가능한 범위만 취소하고 unknown을 남긴다. 재개 시 current release·snapshot·pending approvals·worker fences를 reconcile한다. 이전 terminal job을 다시 실행해 비용을 두 번 쓰지 않는다.

### 9. 전달/인수 완료 산출물

개발 인수는 working source, locked dependencies, runtime compatibility, schema/migration, target acceptance evidence, scope-specific live evaluation, deployment/rollback guide, signed immutable release refs를 포함한다. 준비 ZIP은 이 중 source foundation·계약·명세·작업계획·실행 가능한 offline checks를 제공한다. 아직 없는 runtime/효과 evidence는 명시적으로 남긴다.

## Alternatives considered

**압축 해제 후 자동 설치·실험:** 사용자 권한과 비용 의도를 넘을 수 있다. read-only/offline 준비 명령을 기본으로 한다.

**모든 skill과 전체 문서를 매번 넣기:** 읽기량과 cache 변경이 커진다. 필요한 WP·역할·skill만 progressive 로딩한다.

## Acceptance criteria

깨끗한 ZIP 추출 경로에서 offline 명령이 동작하고 absolute 임시 경로에 의존하지 않아야 한다. 실제 기능이 없는 명령은 성공하지 않아야 한다. runtime·quality·live 미검증 항목이 launch readiness에 그대로 남아야 한다. 인수 보고는 무엇을 실행했는지와 계획만 존재하는 부분을 구분한다.

## Risks

환경별 Python·build backend·network 차이가 첫 설치를 막을 수 있다. metadata probe와 offline 검사로 원인을 분리하고 임의 sudo·silent fallback으로 감추지 않는다.

## Native CLI 모니터링의 현재 설계 연결

사용자 운영 모니터링의 기본은 [dcode 내부 Monitor](../design/NATIVE_MONITOR_TUI.ko.md)다. 기존 dashboard 용어는 이 native 화면의 읽기 view를 포함하는 개념이며 외부 웹 UI 필수 요구가 아니다. 실행은 RF07–RF09에서 native 명령·인증 query·Textual·실제 호출 coverage를 함께 검증한다.
