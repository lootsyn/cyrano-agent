# Coding Agent 기술 조사와 채택 판단

문서 유형: 참고·분석. 기준일: 2026-09-16. 출처별 URL과 고정 가능한 revision은 `../../references/research/r5-sources.json`에 있다. 아래 외부 기능 설명은 공식 문서·논문에서 확인했으며, 해당 프로젝트의 실행·보안 감사·성능 재현 결과가 아니다. 설계 결정은 `../design/`의 소유 문서에 있다. 논문은 HTML 본문으로 검토했다.

## 적용할 연구와 적용하지 않을 주장

| 근거 | 확인한 방식 | Cyrano에 반영 | 의도적으로 제외 |
|---|---|---|---|
| Hermes [S03] | 작은 세션 고정 기억, 필요할 때 과거 검색, skill 개선·승인 대기·관측 | stable release, episodic search, durable learning queue, pending diff와 learning timeline | unrestricted memory write, 개인 성향 자동 추론, 다른 agent loop 전체 의존 |
| ACE [S04] | 생성·회고·curation, 부분 단위 context 수정 | entry ID 기반 add/refine/link/deprecate delta, 반례·근거·중복 검사 | 매번 전체 시스템 프롬프트 재작성, 연구 점수를 제품 개선률로 전용 |
| MemRL [S05] | 관련성 검색과 경험의 효용을 나눈 회수 | 관련성·ACL·freshness가 우선인 실험적 utility overlay | 사실의 진위를 utility로 판단, 단순 점수 갱신을 논문 전체 RL 재현으로 표기 |
| A-Mem [S06] | 원자적 note·태그·연결·진화 | 근거 있는 관계, 역방향 무효화, 버전 이력 | LLM이 만든 관계를 사실·권한으로 취급, 원문 파괴적 덮어쓰기 |
| Mem-pi [S07] | 언제/무엇을 제공할지 학습한 정책 | 무관한 과제에서 recall하지 않는 abstention 가설·검증 | 별도 가중치 학습 의존성; 현재 목표의 모델 비특화 원칙 유지 |
| AGENTS 평가 [S08][S09] | 실험 범위 내 개선 없음·비용 증가 또는 bounded null | 작은 상시 규칙, 선택 로딩, agent instruction 자체 A/B 검증 | 문서가 길수록 좋다거나 모든 문서를 없애야 한다는 일반화 |

Hermes의 문서는 frozen snapshot을 cache 친화적이라고 설명하지만 실제 cache hit은 제공자 usage로만 판단한다. 동일 모델이라도 endpoint·system·tools·중간 context가 달라지면 cache 재사용을 보장하지 않는다. Hermes의 in-memory review 대기열처럼 종료 시 사라질 수 있는 운영 선택은 Cyrano에 복제하지 않고 기존 outbox·lease 기반 내구성을 유지한다. UI 알림을 끄는 것과 학습 실행을 끄는 것은 별도 설정이다.

논문의 성능 수치, 별점, 인기 순위는 도입 근거로 사용하지 않는다. 서로 다른 데이터·모델·판정에서는 숫자를 비교하지 않는다. 개선 효과는 Cyrano의 holdout/family/time 분리 실험으로만 주장한다.

## 여섯 도구의 identity와 최신 정보 함정

Serena [S13]의 확인한 소스는 GPL-3.0-or-later다. 과거 소개글의 MIT 표시를 현재 배포 조건으로 사용하지 않는다. 개발자가 별도 도구로 설치하는 선택 경로만 제공하며, 제품 배포·결합 형태에 대한 별도 라이선스 검토 없이 기본 제품 의존성으로 만들지 않는다. 별도 프로세스라고 자동으로 법적 의무가 사라진다고 주장하지 않는다.

Graphify [S14]의 현재 default branch는 `v8`이다. `main`에서 읽은 과거 0.1.14와 현재 README를 섞으면 API·라이선스가 맞지 않는다. 이번 recipe는 `graphifyy==0.9.62`, 코드 실행 이름은 `graphify`다. 라이선스 metadata는 Apache-2.0이며 LICENSE-MIT·NOTICE도 배포 확인 대상이다. 현재 명령의 code-only와 no-cluster를 실제 help에서 다시 확인한다. 문서·PDF·이미지 처리에는 모델 호출이 필요할 수 있으므로 개발용 기본 recipe에서 제외한다.

QMD [S16][S17]는 `@tobilu/qmd==2.8.3`에 대응하는 npm package다. 프로젝트 문서의 검색 보조이며 Memory의 권위 있는 DB가 아니다. Node·native SQLite·llama 관련 설치 script·모델 다운로드를 숨은 필수 작업으로 만들지 않는다. keyword-only부터 도입하고 semantic mode는 별도 동의·모델 해시·용량·CJK 검증 후 사용한다.

SCIP [S18][S19]는 정적 코드 인덱스 형식이며 `scip-python`은 생산 도구다. LSP와 동일 기능을 켠 두 상시 서버로 만들지 않는다. index를 로컬에서만 사용하고 공식 예제의 `src code-intel upload`는 실행하지 않는다. Knip [S20][S21]은 JS/TS 범위에서만 의미가 있다. Python-only 개발의 필수 검사로 넣지 않는다.

## dcode native 조사 범위

확인한 source baseline은 `7f9e8ed3a555933902045792da9bb184950ee7b2`다. `command_registry.py`의 SlashCommand/BypassTier와 COMMANDS catalog, TUI 디렉터리, extension 제약은 현재 소스로 확인했다. `app.py` 전체는 connector 크기 제한 때문에 이번 fetch에서 읽을 수 없었다. 첨부 dcode-analysis의 `_handle_command`는 위치 탐색 힌트만으로 사용하고 RF07에서 실제 checkout AST/grep으로 재확인해야 한다. 오래된 줄 번호를 patch 주소로 사용하지 않는다. 이 제한은 internal TUI의 실현 가능성 판단과 실제 native wiring 완료 여부를 구분하기 위한 기록이다.



## 연구 범위와 판단의 사용법

자료는 2026-09-17까지 확인된 출처의 관측이다. 최신 버전의 보장이나 성능 실험 결과가 아니다. 모델 지시·권한은 현재 설계가 소유하며 외부 프로젝트의 자체 보안·성능 주장은 자동 승계하지 않는다. 기계 원본은 `references/research/agent-landscape.json`, `adoption-decisions.json`, `source-register.json`이다.

<a id="agent-a01"></a>
## A01 · Hermes Agent

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `NousResearch/hermes-agent`. 최신 안정 버전 관측: **v2026.9.14 (표시 v0.21.3)**. 개발·실험 상태: **main 소스 16bddc88… 별도 스냅샷**. 의미 있는 업데이트 근거: release 2026-09-14; source 조회 2026-09-17. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

작은 MEMORY/USER 내용을 세션 시작에 고정하고, 이후 쓰기는 저장소에 남겨 다음 세션에서 사용한다. write staging과 무인 검토의 교체·삭제 제한을 별도 경로로 둔다.

## 확인 한계와 failure mode

관측한 _gate_or_stage는 gate 모듈 import 실패 시 쓰기 허용 값을 반환한다. 전체 배포의 보안 결함을 단정하지 않지만, Cyrano의 강제 승인 경로에는 이 fallback을 가져올 수 없다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

핵심 기억 snapshot과 작업별 recall을 분리한다. 모든 active 변경은 broker-owned candidate/release로 통과시킨다. 고정 context는 유지하되 권한 철회는 cache보다 우선한다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

gate import 오류, 세션 중 저장, 새 프로세스 회수, 삭제·복원, 무인 교체를 시험한다.

## 자료

- [NS04 · Hermes memory implementation ](SOURCES.ko.md#ns04) — https://github.com/NousResearch/hermes-agent/blob/16bddc88dd325c5eef27c2cc71bbb14c16b870aa/tools/memory_tool.py
- [NS05 · Hermes releases ](SOURCES.ko.md#ns05) — https://github.com/NousResearch/hermes-agent/releases
- [NS06 · Hermes memory guide ](SOURCES.ko.md#ns06) — https://hermes-agent.nousresearch.com/docs/user-guide/features/memory


<a id="agent-a02"></a>
## A02 · gajae-code

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `Yeachan-Heo/gajae-code`. 최신 안정 버전 관측: **v0.16.7**. 개발·실험 상태: **v0.16.8-nightly.20260913102120.34830784995.g9da99cdd708c**. 의미 있는 업데이트 근거: 릴리스 09-13 / nightly 09-14; 9da99cdd…. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

분쟁 중 사실, 점수가 없는 활성 구성요소, 자동 응답 비율에서 계산한 하한으로 LLM 모호도 점수를 보정한다. 철회한 답변의 사실을 disputed로 바꾸며 원보고를 보존한다.

## 확인 한계와 failure mode

계수와 낮은 모호도 점수는 요구 충족이나 승인의 증명이 아니다. ralplan 전체 구현은 이번에 읽지 않아 해당 이름만으로 독립 리뷰 강제를 주장하지 않는다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

기존 필수 interview와 R01–R22 유지. 점수는 질문 우선순위 보조로만 쓰고 unresolved blocker가 준비도를 막는다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

사용자 방향 전환, sibling 요구 누락, auto-answer, 이미 답한 질문 재사용·무효화를 검증한다.

## 자료

- [NS07 · Gajae ambiguity floor ](SOURCES.ko.md#ns07) — https://github.com/Yeachan-Heo/gajae-code/blob/9da99cdd708ce3b97d64111d8eefc98a7e0921ee/packages/coding-agent/src/gjc-runtime/deep-interview-ambiguity.ts
- [NS08 · Gajae releases ](SOURCES.ko.md#ns08) — https://github.com/Yeachan-Heo/gajae-code/releases


<a id="agent-a03"></a>
## A03 · OMO / oh-my-openagent

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `code-yeongyu/oh-my-openagent`. 최신 안정 버전 관측: **안정판 최신값 미확정**. 개발·실험 상태: **Latest 표시 v5.0.0-beta.68; fbcc57e3…**. 의미 있는 업데이트 근거: beta.68 릴리스와 recall gate 소스 조회. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

Kibitzer는 후보 기억에 짧은 사실 힌트를 제안한다. 부모가 candidate set, 이미 표출한 항목, 개수·형식과 pending session identity·만료를 검사한다.

## 확인 한계와 failure mode

정규식의 명령형 탐지는 보안 경계가 아니다. 과거 허용 규칙으로 수집된 힌트를 replay하는 호환 정책도 현재의 ACL·철회보다 우선할 수 없다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

event-triggered RecallHint를 도입하되 DB ACL/freshness를 먼저 적용한다. 힌트는 근거 조회의 제안일 뿐 지시·승인이 아니다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

다른 세션 파일, 만료, 같은 id 새 revision, 무효화 후 replay, 복합 프롬프트 주입을 검사한다.

## 자료

- [NS09 · OMO recall gate ](SOURCES.ko.md#ns09) — https://github.com/code-yeongyu/oh-my-openagent/blob/fbcc57e374c180c41ffc8562c0ab7e7414935811/packages/memory-core/src/recall/gate.ts
- [NS10 · OMO releases ](SOURCES.ko.md#ns10) — https://github.com/code-yeongyu/oh-my-openagent/releases


<a id="agent-a04"></a>
## A04 · Senpi

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `code-yeongyu/senpi`. 최신 안정 버전 관측: **날짜 태그 v2026.9.16-3 관측; 안정성 보증 아님**. 개발·실험 상태: **실험적 Pi fork; f32905c8…**. 의미 있는 업데이트 근거: 2026-09-16 태그 및 cache-keepalive 구현. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

유휴·대기 입력·지원 제공자·횟수·비용을 확인하고 현재 context와 도구를 이용해 cache-warm 요청을 보낸다. generation은 늦은 동작 반영을 제한한다.

## 확인 한계와 failure mode

lastCompletedAt을 쓰는 타이밍을 모든 제공자에 일반화할 수 없다. Claude 공식 TTL은 request start 기준이다. 취소된 요청도 이미 비용이 발생했을 수 있다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: EXPERIMENT

우선 cache 관측과 고정 prefix만 채택. warming은 제공자 검증·명시 예산·사용자 동의가 있는 독립 실험으로 기본 꺼둔다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

긴 streaming, start/finish 차이, pending input 경합, model 전환, 늦은 과금, cap 소진을 검사한다.

## 자료

- [NS11 · Senpi keepalive implementation ](SOURCES.ko.md#ns11) — https://github.com/code-yeongyu/senpi/blob/f32905c8199b70e45acd866159170d390e48715b/packages/coding-agent/src/core/extensions/builtin/cache-keepalive/index.ts
- [NS12 · Senpi releases ](SOURCES.ko.md#ns12) — https://github.com/code-yeongyu/senpi/releases
- [NS53 · Claude prompt caching ](SOURCES.ko.md#ns53) — https://platform.claude.com/docs/en/build-with-claude/prompt-caching


<a id="agent-a05"></a>
## A05 · Pi

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `earendil-works/pi (badlogic/pi-mono redirect)`. 최신 안정 버전 관측: **최신 stable tag 미확정**. 개발·실험 상태: **e4c75a73… message transform**. 의미 있는 업데이트 근거: 소스 및 release history 조회. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

provider 전환에서 tool id와 result 연결을 정규화한다. signature·image·missing tool-result 처리를 한 메시지 투영 경로에 모은다.

## 확인 한계와 failure mode

관측 코드의 cross-model thinking→text와 이미지 생략을 그대로 복제하지 않는다. 합성된 missing result는 실제 도구 실행의 성공/실패 관측과 다르다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

기존 LangChain 메시지를 보존하며 얇은 정규화 검사·변환 원장을 추가한다. opaque reasoning은 제공자 경계 밖으로 자동 전송하지 않는다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

fragment, orphan, duplicate id, tool result order, required image, signed block의 전환 시험을 수행한다.

## 자료

- [NS13 · Pi message transformation ](SOURCES.ko.md#ns13) — https://github.com/earendil-works/pi/blob/e4c75a73222ae2c72abb5f5314fa35ee8effc508/packages/ai/src/api/transform-messages.ts
- [NS14 · Pi releases ](SOURCES.ko.md#ns14) — https://github.com/earendil-works/pi/releases


<a id="agent-a06"></a>
## A06 · Oh My Pi

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `can1357/oh-my-pi`. 최신 안정 버전 관측: **v18.2.2**. 개발·실험 상태: **a2d83061… hashline prompt; notes 기능 실험**. 의미 있는 업데이트 근거: release notes + 모델 노출 patch 지시 조회. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

읽은 줄을 anchor로 지정하는 편집 인터페이스와 retry-safe stream 정책을 제시한다.

## 확인 한계와 failure mode

이번에 본 것은 hashline 지시와 릴리스 기록이다. parser의 충돌·정규화·원자적 쓰기 보장은 실행 검증하지 않았다. 짧은 해시는 고유 식별이나 허가가 아니다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

기존 편집 recipe에 전체 파일 digest+정확한 범위+원문 일치를 결속한다. hashline 문법은 작은 비교 실험으로 평가한다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

동일 줄 반복, 해시 충돌, CRLF/Unicode, source drift, 읽지 않은 구간 편집을 시험한다.

## 자료

- [NS15 · Oh My Pi hashline prompt ](SOURCES.ko.md#ns15) — https://github.com/can1357/oh-my-pi/blob/a2d83061c5d673bf3ee495d7652b63ee5a0ceb14/packages/coding-agent/src/edit/hashline-compact.md
- [NS16 · Oh My Pi releases ](SOURCES.ko.md#ns16) — https://github.com/can1357/oh-my-pi/releases


<a id="agent-a07"></a>
## A07 · protoCLI

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `protoLabsAI/protoCLI`. 최신 안정 버전 관측: **최신 stable 조회 미확정**. 개발·실험 상태: **480f23e1… SprintContractService**. 의미 있는 업데이트 근거: 현행 계약 소스와 skill 제거 설명 확인. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

수정·생성 파일과 완료 조건의 계약으로 session scope lock을 활성화한다. choreography skill과 강제 primitive를 분리했다.

## 확인 한계와 failure mode

parse가 배열 요소를 강타입 검증하지 않고 load 오류를 null로 접는 경로가 있다. 파일 시스템 scope lock만으로 shell·MCP 우회나 OS 격리를 증명할 수 없다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

plan 내용과 강제 guard의 책임 분리를 유지하고, 누락·손상·권한거부·호환불가를 서로 다른 오류로 처리한다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

손상 JSON, 배열의 비문자열, traversal, 계약 없음과 읽기 실패, stale resume를 검사한다.

## 자료

- [NS17 · protoCLI SprintContractService ](SOURCES.ko.md#ns17) — https://github.com/protoLabsAI/protoCLI/blob/480f23e1c119a7fe305fcbb20092b2d1394623d4/packages/core/src/services/sprintContractService.ts
- [NS18 · protoCLI harness guide ](SOURCES.ko.md#ns18) — https://github.com/protoLabsAI/protoCLI/blob/480f23e1c119a7fe305fcbb20092b2d1394623d4/docs/explanation/agent-harness.md


<a id="agent-a08"></a>
## A08 · protoAgent

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `protoLabsAI/protoAgent`. 최신 안정 버전 관측: **v0.168.0**. 개발·실험 상태: **main; A2A/LangGraph; 전체 구현 미검토**. 의미 있는 업데이트 근거: 2026-09-15 릴리스 / 09-16 push. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

변경 기록은 A2A 작업의 즉시 반환, 지연 응답 회수, 출력 예산과 모델 입력에서 timestamp 제거를 다룬다.

## 확인 한계와 failure mode

README의 template 표현만으로 작은 템플릿이라고 단정하지 않는다. 반대로 skill distillation과 remote exactly-once가 구현됐다고 추정하지 않는다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

원격 결과의 늦은 도착을 원장·과금에는 수용하되 철회된 작업 결과로 적용하지 않는다. 시간 정보는 안정된 prompt에 넣지 않는다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

no-progress deadline, 취소 후 결과, 결과 중복, 증거 누락, output budget을 검증한다.

## 자료

- [NS19 · protoAgent repository metadata ](SOURCES.ko.md#ns19) — https://api.github.com/repos/protoLabsAI/protoAgent
- [NS20 · protoAgent releases ](SOURCES.ko.md#ns20) — https://github.com/protoLabsAI/protoAgent/releases


<a id="agent-a09"></a>
## A09 · Open SWE

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `langchain-ai/open-swe`. 최신 안정 버전 관측: **Desktop v0.2.10 — backend 버전과 별도**. 개발·실험 상태: **Agent/Reviewer/Analyzer/Chat/Scheduler; active development**. 의미 있는 업데이트 근거: Desktop 2026-09-16; README 조회. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

기존 Deep Agents 위에 역할별 graph와 지속 sandbox, PR 검토·CI·사용자 피드백을 결합한다.

## 확인 한계와 failure mode

Analyzer README가 설명하는 review-style 학습을 실제 품질 개선 증거로 보지 않는다. 공개 OpenAPI가 모든 인증 요건을 포함한다고 가정하지 않는다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

리뷰와 수정 역할 분리, feedback 후보화, 살아 있는 workspace 재연결을 채택한다. SaaS·다섯 서버를 별도 제품으로 들여오지 않는다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

sandbox 분실 시 새 빈 환경으로 재개 금지, review read-only, CI flaky 예외 악용을 검사한다.

## 자료

- [NS21 · Open SWE architecture and operations ](SOURCES.ko.md#ns21) — https://github.com/langchain-ai/open-swe/blob/main/README.md
- [NS22 · Open SWE releases ](SOURCES.ko.md#ns22) — https://github.com/langchain-ai/open-swe/releases


<a id="agent-a10"></a>
## A10 · Inception

문서 유형: 참고·비교 분석. 조회일 2026-09-17.

## 식별과 버전

첨부 설명과 일치하는 공식 저장소 **Milind220/inception**을 추가 검색으로 찾았다. 초기에 이름만으로 식별하지 못한 상태를 유지하지 않고 다음 소스 확인으로 갱신했다. 최신 stable 릴리스는 미확정이며 README의 npm publish는 미완료다. 작은 초기 프로젝트라는 상태와 README의 테스트/실행 성공 주장을 구분한다. 이번에 테스트를 재현하지 않았다.

## 실제 읽은 동작

모델이 작성한 JavaScript orchestration을 runtime의 agent/parallel/pipeline/workflow primitive로 실행한다. 공유 budget·동시실행 제한·깊이 제한·journal을 제공한다. `run.ts`의 limiter 진입 후 실행 상태를 기록하고 queued 중 budget을 다시 확인하는 순서는 참고할 만하다. 부모와 재귀 workflow가 동일 budget을 공유한다. [NS71](SOURCES.ko.md#ns71)

일반 child 실패를 null로 반환하고 journal 쓰기 오류를 삼키는 코드가 있다. call key에서 image의 수만 포함하고 직렬화 불가 schema를 같은 present 값으로 취급한다. mutable source·credential/scope·도구부작용이 다른 실행을 같은 prompt 결과로 재사용하지 않도록 Cyrano에서는 더 강한 결속이 필요하다. [NS72](SOURCES.ko.md#ns72)

## 판단: ADAPT

generated orchestration이라는 입력 방식을 bounded IR로 적용한다. Flue/JS runtime 설치와 임의코드 실행, null 필수작업 무시, best-effort audit·결과 memo는 가져오지 않는다. 이는 새로운 독립 runtime을 들여오지 않고 현재 workflow coordinator에 계획 입력을 추가하는 설계다. 기대 효과는 coordinator context와 반복 호출 감소라는 가설이며 비용·정확성·human intervention을 paired 평가한다.

구현 비용은 중간~높음이다. IR 검증·scheduler·실패 전파·권한·effect 원장을 유지해야 한다. 기존 LangGraph/dcode 모델 loop를 그대로 쓰므로 Flue SDK 버전 충돌과 새 JavaScript 실행권한을 만들지 않는다. 실패하면 기존 검토된 WorkUnit plan 또는 명시적 pause로 복귀한다.

## 필수 검증

동일 이미지 수/다른 bytes, schema fingerprint 실패, source 변경, child 실패, journal disk-full, 병렬 예산 reserve, 취소와 late 비용을 시험한다. 필수 child 오류는 부모 완료 blocker이며, log 저장 실패는 optional UI와 mandatory audit를 나누어 처리한다. response 결과 cache와 외부 effect 재사용은 같은 문제가 아니다.

## 자료

- https://github.com/Milind220/inception
- [NS70–NS72 원문과 확인 범위](SOURCES.ko.md#ns70)
- [NS64 LLMCompiler 기초 연구](SOURCES.ko.md#ns64)


<a id="agent-a11"></a>
## A11 · Pactrail

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `AKMessi/pactrail`. 최신 안정 버전 관측: **manifest 1.0.0 / 공개 release 최신값 별도 미확정**. 개발·실험 상태: **582a22db… Rust source**. 의미 있는 업데이트 근거: transaction create/open 소스 조회. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

candidate snapshot을 만든 뒤 복사 결과와 원본을 다시 확인한다. reopen에서 메타데이터 형식·버전·경로를 검사한다. 공식 설계는 receipt-bound apply와 effect journal을 중심에 둔다.

## 확인 한계와 failure mode

전체 apply 구현이나 crash 주입 시험을 실행한 것은 아니다. 해시 체인만으로 공격자가 전체 기록을 재작성하지 못한다는 보장은 없다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

Cyrano Broker의 snapshot·effect fence·원본 반영 검사를 보강한다. 새 Rust 실행 엔진이나 별도 DB는 들이지 않는다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

snapshot 도중 source 변경, 중간 적용 crash, receipt 불일치, 권한철회, 원복 source drift를 검사한다.

## 자료

- [NS23 · Pactrail workspace transaction ](SOURCES.ko.md#ns23) — https://github.com/AKMessi/pactrail/blob/582a22db473b455f7f5bdc185bf430639b88a49f/crates/pactrail-workspace/src/transaction.rs
- [NS24 · Pactrail overview ](SOURCES.ko.md#ns24) — https://github.com/AKMessi/pactrail/blob/main/README.md
- [NS25 · Pactrail package manifest ](SOURCES.ko.md#ns25) — https://github.com/AKMessi/pactrail/blob/main/Cargo.toml


<a id="agent-a12"></a>
## A12 · OpenCode

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `anomalyco/opencode`. 최신 안정 버전 관측: **v1.18.31**. 개발·실험 상태: **main; ACP resume/fork fixes**. 의미 있는 업데이트 근거: 2026-09-14 릴리스. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

Build·Plan·Explore 역할과 도구 권한을 구분한다. Plan의 write/bash는 ask 정책이므로 완전한 무변경 sandbox라는 뜻은 아니다.

## 확인 한계와 failure mode

모드명이나 대화상 승인만으로 전 경로 강제를 입증할 수 없다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

계획 단계의 도구 가용성은 runtime 정책으로 좁히고 외부 worker는 conformance를 거친다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

Plan 모드 shell·MCP·resume 우회, ACP 권한 요청과 cancel을 시험한다.

## 자료

- [NS26 · OpenCode agent modes ](SOURCES.ko.md#ns26) — https://opencode.ai/docs/agents/
- [NS27 · OpenCode releases ](SOURCES.ko.md#ns27) — https://github.com/anomalyco/opencode/releases


<a id="agent-a13"></a>
## A13 · Cline

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `cline/cline`. 최신 안정 버전 관측: **Desktop0.0.29 / SDK0.0.83 / CLI3.0.62 관측**. 개발·실험 상태: **구성요소별 릴리스; extension 최신값 미확정**. 의미 있는 업데이트 근거: 최신 release 페이지 조회. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

Plan/Act UX로 탐색·질문과 구현을 분리하고 모드별 모델 선택을 제공한다.

## 확인 한계와 failure mode

제품 구성요소 버전을 하나로 합치거나 모델별 prompt를 Cyrano에 복제하지 않는다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

검토 가능한 계획 화면과 피드백 루프를 참고하되 실제 승인 원장은 기존 시스템에 둔다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

계획 수정과 승인 혼합, mode 전환 후 유효성, 다른 모델 review 결속을 검사한다.

## 자료

- [NS28 · Cline Plan and Act ](SOURCES.ko.md#ns28) — https://docs.cline.bot/core-workflows/plan-and-act
- [NS29 · Cline releases ](SOURCES.ko.md#ns29) — https://github.com/cline/cline/releases


<a id="agent-a14"></a>
## A14 · OpenHands

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `OpenHands/OpenHands`. 최신 안정 버전 관측: **v1.19.0 (SDK와 별도)**. 개발·실험 상태: **SDK/서버/작업 환경**. 의미 있는 업데이트 근거: 공식 SDK 문서와 제품 릴리스 조회. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

작업 환경과 에이전트·도구를 API로 분리하는 SDK 방식이다.

## 확인 한계와 failure mode

Cyrano의 dcode runtime을 SDK로 대체하지 않는다. 게시된 benchmark는 우리 비교가 아니다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: DEFER

원격 worker 상호운용 후보로만 남기고 dcode 동일 프로세스에 새 loop를 넣지 않는다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

remote artifact 검증·workspace scope·명령 부작용을 입증한 후 활성화한다.

## 자료

- [NS30 · OpenHands SDK ](SOURCES.ko.md#ns30) — https://docs.openhands.dev/sdk
- [NS31 · OpenHands releases ](SOURCES.ko.md#ns31) — https://github.com/OpenHands/OpenHands/releases


<a id="agent-a15"></a>
## A15 · Continue

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `continuedev/continue`. 최신 안정 버전 관측: **v2.0.0-vscode 관측; 다른 구성요소 unknown**. 개발·실험 상태: **Chat/Plan/Agent**. 의미 있는 업데이트 근거: 공식 modes와 releases 조회. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

Chat·읽기 중심 Plan·도구 Agent를 구분해 기능 가용성을 노출한다.

## 확인 한계와 failure mode

IDE mode가 host 파일 접근의 보안 격리를 보장하지 않는다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

UI의 기능표와 runtime capability 검사 결과를 일치시킨다. 지원되지 않는 도구를 감추고 자동 대체하지 않는다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

미지원 호출, 계획 단계 write 차단, capability 불일치 표시를 검증한다.

## 자료

- [NS32 · Continue modes ](SOURCES.ko.md#ns32) — https://docs.continue.dev/ide-extensions/agent/how-it-works
- [NS33 · Continue releases ](SOURCES.ko.md#ns33) — https://github.com/continuedev/continue/releases


<a id="agent-a16"></a>
## A16 · Qwen Code

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `QwenLM/qwen-code`. 최신 안정 버전 관측: **v0.24.0**. 개발·실험 상태: **0.24.0-nightly.20260916.b8def02aad; serve 실험**. 의미 있는 업데이트 근거: nightly 2026-09-16. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

CLI·SDK·headless와 실험적 serve를 별도 진입점으로 제공한다.

## 확인 한계와 failure mode

특정 모델 계열에 대한 내장 최적화를 모델독립 성능 보장으로 읽지 않는다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: EXPERIMENT

ACP worker 후보. 동일 작업·권한·예산의 live conformance 이후 비교한다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

터미널 접근, hook 우회, background 작업, cancel·재개를 검사한다.

## 자료

- [NS34 · Qwen Code overview ](SOURCES.ko.md#ns34) — https://github.com/QwenLM/qwen-code
- [NS35 · Qwen Code releases ](SOURCES.ko.md#ns35) — https://github.com/QwenLM/qwen-code/releases


<a id="agent-a17"></a>
## A17 · Crush

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `charmbracelet/crush`. 최신 안정 버전 관측: **v0.95.0**. 개발·실험 상태: **nightly 채널**. 의미 있는 업데이트 근거: 공식 repo·release 조회. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

터미널 UX에서 제공자와 도구 통합을 다룬다.

## 확인 한계와 failure mode

Go TUI를 가져와 Textual 옆에 다른 화면 엔진을 만들지 않는다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

Cyrano TUI에 도구 건강·실행 상태를 분리해 보이는 UX 원칙만 반영한다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

연결 실패·미설치·권한없음을 하나의 비활성 상태로 합치지 않는지 검사한다.

## 자료

- [NS36 · Crush overview ](SOURCES.ko.md#ns36) — https://github.com/charmbracelet/crush
- [NS37 · Crush releases ](SOURCES.ko.md#ns37) — https://github.com/charmbracelet/crush/releases


<a id="agent-a18"></a>
## A18 · Kilo Code

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `Kilo-Org/kilocode`. 최신 안정 버전 관측: **v7.7.2**. 개발·실험 상태: **prerelease와 IDE 구성요소 별도**. 의미 있는 업데이트 근거: release 기록 조회; 일부 docs 경로 접근 실패. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

목표 pause/resume·PR review·알림·worktree 작업의 제품 동작을 지속 확장한다.

## 확인 한계와 failure mode

기능 존재가 정확한 상태 복구·승인 강제를 뜻하지 않는다. 접근 실패한 문서를 읽었다고 하지 않는다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

기존 durable goal·작업 원장과 통합된 알림을 개선하고 별도 Agent Manager 상태를 만들지 않는다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

pause 이후 신규 dispatch, 알림 중복, worktree 소유권·삭제 경합을 검사한다.

## 자료

- [NS38 · Kilo Code releases ](SOURCES.ko.md#ns38) — https://github.com/Kilo-Org/kilocode/releases


<a id="agent-a19"></a>
## A19 · goose

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `aaif-goose/goose (block/goose redirect)`. 최신 안정 버전 관측: **v1.50.1**. 개발·실험 상태: **ACP·context·cache 변경**. 의미 있는 업데이트 근거: v1.50 계열 release 기록 조회. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

변경 기록에 cache anchor, 구조화 context summary, ACP client 분리와 이벤트 identity 개선이 나타난다.

## 확인 한계와 failure mode

개별 fixes를 모든 provider에 통하는 캐시·재개 보장으로 일반화하지 않는다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

요약의 필수 의무·도구 호출 관계 보존, scope 지정 event identity를 보강한다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

compaction 전후 미완료 의무와 tool-call/result 연결, request epoch를 비교한다.

## 자료

- [NS39 · Goose overview ](SOURCES.ko.md#ns39) — https://github.com/aaif-goose/goose
- [NS40 · Goose releases ](SOURCES.ko.md#ns40) — https://github.com/aaif-goose/goose/releases


<a id="agent-a20"></a>
## A20 · Aider

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `Aider-AI/aider`. 최신 안정 버전 관측: **v0.86.0**. 개발·실험 상태: **latest main commit 미확정**. 의미 있는 업데이트 근거: release 페이지 + repo-map 공식 문서. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

전체 소스 대신 구조·signature 중심의 작은 repo map을 context에 제공한다.

## 확인 한계와 failure mode

성숙한 아이디어를 2026 신규 연구라 부르지 않는다. 이름 기반 참조는 실제 동적 호출의 증거가 아니다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

필요한 파일을 찾는 저비용 첫 단계로 selective map을 제공하고 LSP/AST 근거로 확장한다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

지도예산, stale signature, 동명이인 symbol, 비지원 언어 fallback을 검증한다.

## 자료

- [NS41 · Aider repository map ](SOURCES.ko.md#ns41) — https://aider.chat/docs/repomap.html
- [NS42 · Aider releases ](SOURCES.ko.md#ns42) — https://github.com/Aider-AI/aider/releases


<a id="agent-a21"></a>
## A21 · mini-SWE-agent

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `SWE-agent/mini-swe-agent`. 최신 안정 버전 관측: **v2.4.6**. 개발·실험 상태: **v2 문서**. 의미 있는 업데이트 근거: 공식 docs·release 조회. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

모델·agent·환경을 작게 분리한 비교 기준을 제공한다.

## 확인 한계와 failure mode

작은 코드 규모가 우리 안전·HITL 요구 충족을 의미하지 않는다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADOPT

복잡한 개선의 순효과를 측정할 ablation baseline 설계에 사용한다. 제품 loop는 바꾸지 않는다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

동일 데이터·모델·시간/비용 예산에서 품질과 추가 overhead를 비교한다.

## 자료

- [NS43 · mini-SWE-agent docs ](SOURCES.ko.md#ns43) — https://mini-swe-agent.com/latest/
- [NS44 · mini-SWE-agent releases ](SOURCES.ko.md#ns44) — https://github.com/SWE-agent/mini-swe-agent/releases


<a id="agent-a22"></a>
## A22 · Gemini CLI

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `google-gemini/gemini-cli`. 최신 안정 버전 관측: **v0.60.0**. 개발·실험 상태: **prerelease; 일부 routing 실험**. 의미 있는 업데이트 근거: 2026-09-15 stable 릴리스. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

core policy·도구·session 계층을 나누며 CLI 실행을 조합한다.

## 확인 한계와 failure mode

Gemini 중심 API의 장점을 다른 제공자에서 당연히 사용할 수 있다고 하지 않는다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

native 정책의 확인 방법과 optional external worker 가용성 표를 참고한다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

tool-policy ordering, provider signature, CLI permission callback을 검증한다.

## 자료

- [NS45 · Gemini CLI core ](SOURCES.ko.md#ns45) — https://geminicli.com/docs/core/
- [NS46 · Gemini CLI releases ](SOURCES.ko.md#ns46) — https://github.com/google-gemini/gemini-cli/releases


<a id="agent-a23"></a>
## A23 · Kiro

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `kiro.dev`. 최신 안정 버전 관측: **IDE1.1; CLI v2 계열은 별도**. 개발·실험 상태: **Projects/spec 기능은 실행면마다 다름**. 의미 있는 업데이트 근거: IDE 2026-09-14 changelog. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

명세를 feature·bugfix·quick 경로로 다루고 구현 전 문서·시나리오를 구조화한다.

## 확인 한계와 failure mode

IDE 전용 속성 시험을 CLI 공통 기능으로 표기하지 않는다. 내부 source·권한강제는 확인 불가다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

작업 유형별 계획 깊이를 조절하되 필수 인터뷰·완료 조건·리뷰는 제거하지 않는다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

작은 수정·대형 변경 모두 단계별 blocker가 유지되는지 검사한다.

## 자료

- [NS47 · Kiro specifications ](SOURCES.ko.md#ns47) — https://kiro.dev/docs/specs/
- [NS48 · Kiro changelog ](SOURCES.ko.md#ns48) — https://kiro.dev/changelog/


<a id="agent-a24"></a>
## A24 · Amp

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `ampcode.com`. 최신 안정 버전 관측: **숫자 stable 버전 미확정**. 개발·실험 상태: **연속 업데이트형 상용 제품**. 의미 있는 업데이트 근거: 2026-09-13 chronicle. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

공식 문서와 chronicle에서 worker·도구·제품 진입점을 설명한다.

## 확인 한계와 failure mode

비공개 orchestration·모델 정책을 역추정하지 않는다. BYO 제공이 모델 손실 없는 성능 증거는 아니다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: DEFER

외부 worker 요구가 실제 생기면 인증·artifact·비용 계약을 검증한다. 지금 의존성을 추가하지 않는다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

완료 자기보고와 runner evidence 구분, native approval 연결을 시험한다.

## 자료

- [NS49 · Amp documentation ](SOURCES.ko.md#ns49) — https://ampcode.com/docs
- [NS50 · Amp chronicle ](SOURCES.ko.md#ns50) — https://ampcode.com/chronicle


<a id="agent-a25"></a>
## A25 · Cursor

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `cursor.com`. 최신 안정 버전 관측: **숫자 stable 버전 미확정**. 개발·실험 상태: **Projects beta / self-hosted 기능**. 의미 있는 업데이트 근거: 2026-09-02 변화와 최신 changelog 조회. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

코드 탐색·질문·검토 가능한 계획을 Build 앞에 두는 UX를 제공한다.

## 확인 한계와 failure mode

계획 UX는 receipt-bound 실행 허가의 구현 증거가 아니다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

사람이 수정 전후와 위험·검증을 볼 수 있는 공동 검토 원칙을 유지한다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

수정 후 재표시, stale 화면, bulk approve, 숨은 권한 확대를 검사한다.

## 자료

- [NS51 · Cursor Plan mode ](SOURCES.ko.md#ns51) — https://cursor.com/docs/agent/plan-mode
- [NS52 · Cursor changelog ](SOURCES.ko.md#ns52) — https://cursor.com/changelog


<a id="agent-x01"></a>
## X01 · Beads

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `gastownhall/beads`. 최신 안정 버전 관측: **이번 조회에서 최신 stable 미확정**. 개발·실험 상태: **영속 작업·의존성 문서**. 의미 있는 업데이트 근거: 공식 repo 조회. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

작업과 의존 관계를 대화 컨텍스트 밖에 유지하는 접근을 참고한다.

## 확인 한계와 failure mode

기존 Cyrano ledger 옆에 다른 authoritative task DB를 만들지 않는다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

기존 작업 원장의 dependency·claim·이력 조회를 개선한다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

동시 claim·lease 만료·외부 task 수정과 CAS 충돌을 시험한다.

## 자료

- [NS66 · Beads repository ](SOURCES.ko.md#ns66) — https://github.com/gastownhall/beads


<a id="agent-x02"></a>
## X02 · LLMCompiler

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `논문 arXiv:2312.04511`. 최신 안정 버전 관측: **논문 2023-12-07**. 개발·실험 상태: **최신 구현 repo 상태 미조사**. 의미 있는 업데이트 근거: 기초 연구로 구분. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

계획을 task graph로 만들고 scheduler가 병렬 실행하는 아이디어다.

## 확인 한계와 failure mode

초록 검토는 코드 실행이나 안전한 generated-code 증거가 아니다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: ADAPT

임의 Python/JS가 아니라 허용 노드·조건식의 bounded IR를 기존 workflow에 추가 설계한다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

cycle·동적 확장·예산 합계·scope·취소·실패 격리를 검증한다.

## 자료

- [NS64 · LLMCompiler paper ](SOURCES.ko.md#ns64) — https://arxiv.org/abs/2312.04511


<a id="agent-x03"></a>
## X03 · Orin tool retrieval

문서 유형: 참고·비교 분석. 조회일: 2026-09-17. 제품의 보안/효과 인증이 아니다.

## 식별과 최신 상태

Repository/공식 식별: `식별 미확정`. 최신 안정 버전 관측: **unknown**. 개발·실험 상태: **unknown**. 의미 있는 업데이트 근거: 명칭 및 tool retrieval 검색. 유지보수 판단은 이 관측 범위에 한정한다. production maturity는 Cyrano 환경에서 미검증이다.

## 무엇이 있고 어떻게 동작하는가

첨부의 이름을 특정 공식 tool retrieval 프로젝트로 확정하지 못했다.

## 확인 한계와 failure mode

동명 하드웨어나 다른 제품으로 대체하지 않는다.

source-level이라고 적은 경우도 명시한 함수/줄 범위의 정적 확인이다. 테스트 파일의 존재와 실제 실행 성공은 다르다. 릴리스 버전은 구성요소에 붙이며 nightly·beta와 stable을 섞지 않는다. closed-source는 내부 loop·정규화·checkpoint semantics를 추정하지 않는다.

## Cyrano 판단: DEFER

제품 채택 보류. tool exposure의 평가 기반 설계는 Cyrano 자체 제안으로 분리한다.

이 판단은 제품을 통째로 설치하라는 뜻이 아니다. 현재 요청의 산출물은 문서만이다. 실제 dependency, 라이선스, 공급망, 정적/동적 테스트가 필요한 구현 변경은 소유 WP의 계획 리뷰 후 수행한다. 우리 구조를 새 framework로 교체하는 것은 범위 밖이다.

## 기대 효과·비용·복잡도·유지보수

기대 효과는 누락·오류·맥락 낭비를 줄이는 가설이며 실측 개선이 아니다. 코드 수준 채택은 adapter와 conformance fixture의 유지비를 발생시킨다. UX/절차 채택은 skill 지침만으로 runtime 강제를 대신하지 못한다. 독립 daemon·DB·provider SDK를 추가해야 한다면 기존 기능 대비 비용을 WP20에서 먼저 측정한다. 장애 시 이전 검증 release 또는 명시적 미지원 상태로 돌아가며, 더 약한 권한 검사로 조용히 fallback하지 않는다.

## 필수 검증

공식 repo와 구현을 확인하면 동일 scope·schema drift 시험으로 재평가한다.

## 자료

- [NS61 · Agent Skills specification ](SOURCES.ko.md#ns61) — https://agentskills.io/specification



핵심 mechanism은 후보 카드에 있다. `미검토`는 기능 없음이 아니라 이번 조사에서 해당 구현을 확인하지 못했다는 뜻이다. docs/release는 source와 같은 깊이가 아니다. 모든 행의 native 실행·효과는 미검증이다.

| 후보 | core/model 확인 | context/cache 확인 | memory/skill 확인 | 계획·병렬·evidence 확인 | 적용 |
|---|---|---|---|---|---|
| Hermes Agent | 전체loop 미검토 | 세션snapshot 소스 | memory gate 소스 | 권한fallback 제한분석 | ADAPT |
| gajae-code | 전체provider 미검토 | cache 미검토 | 인터뷰fact하한 소스 | revision·retraction 소스 | ADAPT |
| OMO / oh-my-openagent | 전체loop 미검토 | candidatehint 입력 제한 | recallgate 소스 | pendingidentity·expiry | ADAPT |
| Senpi | Pi extension 소스 | warmtimer·비용 소스 | memory 전체 미검토 | generation·idle 조건 | EXPERIMENT |
| Pi | message normalizer 소스 | signature/image변환 | 전체memory 미검토 | call/result연결 소스 | ADAPT |
| Oh My Pi | runtime 미검토 | release notes | notes release기록 | hashline prompt·재시도기록 | ADAPT |
| protoCLI | 계약service 소스 | contextformat 소스 | 학습은문서 | scopeactivate/load 소스 | ADAPT |
| protoAgent | A2A/LangGraph 문서 | timestamp/output release기록 | distillation 소스 미검토 | late task release기록 | ADAPT |
| Open SWE | graph분리 문서 | thread/sandbox 문서 | Analyzer 문서 | review/CI 문서 | ADAPT |
| Inception | runtime run.ts 소스 | journalmemo 소스 | portable skill 문서 | budget/parallel/journal 소스 | ADAPT |
| Pactrail | Rust계층 문서 | boundedcontext 문서 | receiptmemory 문서 | snapshot/create/open 소스 | ADAPT |
| OpenCode | modes 문서 | 구현미검토 | 구현미검토 | permission docs/ACP release | ADAPT |
| Cline | plan/act 문서 | 구현미검토 | 구현미검토 | UX문서 | ADAPT |
| OpenHands | SDK공식문서 | 구현미검토 | 구현미검토 | workspace/security문서 | DEFER |
| Continue | modes공식문서 | 구현미검토 | 구현미검토 | read/write역할문서 | ADAPT |
| Qwen Code | repo/API문서 | 구현미검토 | 구현미검토 | serve 실험/release | EXPERIMENT |
| Crush | terminal/provider문서 | 구현미검토 | 구현미검토 | release/도구통합 | ADAPT |
| Kilo Code | release기록 | 구현미검토 | 구현미검토 | goal/PR/worktree변경 | ADAPT |
| goose | repo/release | cacheanchor·summary release | 구현미검토 | ACP/id release | ADAPT |
| Aider | 구현미검토 | repo-map공식문서 | 구현미검토 | release기록 | ADAPT |
| mini-SWE-agent | 최소agent docs | 간소한구조 docs | 추가기능미검토 | ablationbaseline 설계 | ADOPT |
| Gemini CLI | core공식문서 | 구현미검토 | 구현미검토 | policy/session공식문서 | ADAPT |
| Kiro | 비공개 | 비공개 | 비공개 | spec공식문서 | ADAPT |
| Amp | 비공개 | 비공개 | 비공개 | 공식docs/changelog | DEFER |
| Cursor | 비공개 | 비공개 | 비공개 | Plan공식문서 | ADAPT |
| Beads | loop아님 | 미검토 | 미검토 | taskledger문서 | ADAPT |
| LLMCompiler | 논문초록 | scheduler개념 | 범위아님 | planner/parallel초록 | ADAPT |
| Orin tool retrieval | 식별미확정 | 식별미확정 | 식별미확정 | 식별미확정 | DEFER |


모든 결정은 문서 설계 판단이다. 설치·활성화는 수행하지 않았다. ADOPT도 현재 제품 구현완료라는 뜻이 아니다. 유지보수 비용은 각 adapter/schema/conformance fixture의 upstream drift 확인 비용까지 포함한다.

| ID | 기술 | 결정 | 작업 | 비용·복잡도 | 기대 효과 | 위험 | 의존성 | 실패/복구 |
|---|---|---|---|---|---|---|---|---|
| T01 | Provider capability/typed message normalization | ADAPT | WP06 | 중간 | 프로토콜 손실·재시도 오류 감소 | SDK 중복변환·서명손상 | native adapter 검사·현재 probe | unsupported를 명시; 원래검증경로유지 |
| T02 | Streaming call completion gate | ADOPT | WP06 | 중간 | 부분 JSON의 조기실행 차단 | 내부 retry 중복 | 실제 stream hook | 불완전call은실행하지않음 |
| T03 | 고정 prefix·context epoch | ADOPT | WP05 | 중간 | cache 안정성과재현성 | 중요정보갱신지연 | context manifest | 철회는cache보다우선 |
| T04 | 유휴 cache warming | EXPERIMENT | WP05 | 중간~높음 | 후속호출비용절감가설 | 과금·TTL오해·취소경합 | provider실측·명시예산 | 기본off;사용자작업우선 |
| T05 | 의무 보존 compaction | ADAPT | WP05 | 중간 | 맥락압박에도권한/계획보존 | 요약의사실손실 | 원문artifact·kernel원장 | 실패시기존epoch유지/pause |
| T06 | Kibitzer형 JIT recall | ADAPT | WP11 | 중간 | 관련기억만주입 | retrievalpollution·주입공격 | ACL+freshness+evidence | hint거부·필요근거재조회 |
| T07 | 기억 utility 학습 | EXPERIMENT | WP11 WP20 | 높음 | 반복효과반영 | selectionbias·stale상승 | pairedsample·불확실성 | 기본관련성검색유지 |
| T08 | Lesson→skill delta·deprecation | ADAPT | WP16 | 높음 | 재사용절차개선 | 검증기준변조·근거소실 | B actual eval·release broker | oldrelease/revoke |
| T09 | Bounded WorkflowIR | ADAPT | WP09 | 중간~높음 | 병렬실행재현성 | DAG확장권한우회 | 기존workflow/permit | compile거부·기존검증계획 |
| T10 | 임의 generated JavaScript/Python 실행 | REJECT | WP09 | 높음 | 현재목표보다위험큼 | 권한우회·무한loop·dependency폭증 | 새runtime필요 | 허용IR로표현 |
| T11 | Task lease·mailbox·작업원장 | ADOPT | WP09 | 중간 | 장기작업재개와충돌방지 | 이중claim·stale결과 | transaction+fencing | pause·reconciliation |
| T12 | worktree 후보 격리 | ADOPT | WP09 | 중간 | 파일충돌감소 | Git공유·OS미격리 | Broker/sandbox | 단일approvedcandidate |
| T13 | Hash anchored edits | ADAPT | WP03 | 중간 | 잘못된대상편집감소 | 짧은hash충돌·인코딩 | snapshot+전체digest | 정확재읽기;fuzzy금지 |
| T14 | LSP/AST/graph 단계 조회 | ADAPT | WP03 | 중간~높음 | 관련코드탐색 | stale/추정edge오용 | 검증tool/indexbinding | text탐색만낮은보장으로표시 |
| T15 | ACP 외부 coding worker | EXPERIMENT | WP10 | 높음 | worker교체가능성 | 원격효과·권한손실 | capabilityconformance | dcode기본worker유지 |
| T16 | A2A 기본제품활성 | DEFER | WP10 | 높음 | 지금필수아님 | 인증/운영/비용증가 | 실제remote요구 | adapter설계만 |
| T17 | MCP scope/schema snapshot | ADOPT | WP10 | 중간 | 도구권한일관성 | discovery/schema drift | trustedprofile·protocolpin | stale서버호출차단 |
| T18 | Evidence transaction/effect fence | ADAPT | WP03 WP13 | 높음 | 완료·복구진실성 | 다중파일원자성오해 | trustedrunner·저장소 | unknown효과확인 |
| T19 | OTel 선택 exporter | ADAPT | WP13 | 중간 | 기존관측backend연동 | 개인정보·queueoverflow | redaction·localjournal | localCLI조회유지 |
| T20 | Agent의 정책·승인키·holdout 자기수정 | REJECT | WP16 | 해당없음 | 목표와모순 | 평가기준조작 | 보호경로 | 정상candidate제안만 |
| T21 | dcode 대체 engine/별도 task DB | REJECT | WP00 | 높음 | 구조보존요구위반 | 이중상태·migration | 불필요 | 기존모듈확장 |
| T22 | 상시 peer swarm | DEFER | WP09 | 높음 | 소규모task효용미확인 | 비용폭증·coordination | 실측효과 | 필요worker만dispatch |
| T23 | Review feedback 학습 | ADAPT | WP16 | 중간 | 수정반복감소 | 취향을정답으로오인 | finding·evidence·B eval | scope제한candidate |
| T24 | Thin model-name behavior preset | REJECT | WP06 | 높음 | 범용목표에불필요 | profile증식·근거없는능력점수 | protocol차이만필요 | thin protocol adapter |

## 충돌 해결

첨부의 `deepagents-code-nextgen-research/01-research...`는 산출물 목적 분류로만 해석하고 새 프로젝트 트리를 만들지 않는다. 현재 사용자 지시가 우선한다. 첨부의 thin model-specific adaptation은 provider protocol compatibility로 좁히며 기존 모델별 행동특화 금지를 해제하지 않는다.

모든 기능을 새롭게 구현한다는 문장으로 기존 심층 인터뷰·Memory·monitor 설계를 덮어쓰지 않는다. 실제 R6에 동등 기능이 존재하면 새 인터페이스를 중복 생성하지 않고 수용 사례와 구현계획만 합친다. 어느 문서가 authoritative인지 불명확하면 의미충돌을 사람이 검토한 뒤 owner 문서에 해결을 남긴다.

## 검토되지 않은 영역

새로운 모든 agent의 전체 repository·runtime·보안·성능을 감사한 것은 아니다. 25개 명시 후보를 식별·공식문서/릴리스 수준으로 각각 조사하고, 채택 판단의 핵심은 읽은 source slice까지 내려가 구분했다. 비공개 제품과 미확정 release·Orin 식별은 제한을 명시했다. README의 테스트 수·benchmark·‘production ready’는 Cyrano의 검증 증거가 아니다.
