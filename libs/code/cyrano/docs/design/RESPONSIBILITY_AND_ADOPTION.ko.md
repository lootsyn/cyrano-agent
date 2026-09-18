# 기능 책임과 개발용·제품용 도입 결정

문서 유형: 상세 설계. R5에서 새로 확정한 책임의 원본. 현재 기능이 완성됐다는 의미가 아니다. code/skill/config/provider/evidence를 별도 산출물로 관리한다. 관련 출처는 [연구 분석](../reference/R5_RESEARCH.ko.md), 구현 작업은 [R5 개발계획](../development/R5_MASTER_PLAN.ko.md)이다.

## 1. 어디에서 해결할 것인가

| 기능 | 반드시 구현할 코드 | skill·agent 설정의 책임 | 운영 설정 | 책임 WP/RF |
|---|---|---|---|---|
| 계획 전 변경 차단 | Kernel 상태 전이, 서명 승인·permit 검사, Broker·OS 격리 | 요구/범위/완료 조건 수집, 계획안과 리뷰 finding 작성 | 위험별 승인·허가 범위 | WP04–WP09, RF00 |
| Python 품질 | runner·최종 판정·baseline·docstring 분석, CI required checks | naming/import/docstring 작성·검토 절차 | 대상 저장소 formatter 정책 | WP10/WP22, TS01–TS03 |
| 관련 코드 이해 | CodeIntelligenceGateway, LSP lifecycle, snapshot·경로 검증 | grep→symbol→references→근거 비교 사용 순서 | 언어별 provider·쿼터 | WP03/WP06, RF02–RF03 |
| 기억의 영속·ACL | MemoryStore·revision·outbox·tombstone | 기억 후보 추출과 근거·범위 설명 | 크기·보존·승인·회수 예산 | WP11, RF04 |
| 기억 실제 활용 | ContextBinder·ApplicationChecker | 계획의 memory 의존·반례를 명시 | phase별 recall | WP11/WP12, RF04 |
| 자기개선 | CandidateStore·paired Eval·Release CAS·rollback | analyst·critic·curator의 가설·delta 생성 | 예산·trigger·위임 범위 | WP16–WP20, RF05–RF06 |
| CLI 모니터링 | 인증 query service·순수 reducer·Textual 화면·native command | 실패 조사 절차; 상태는 도구로 조회 | 표시 갱신·보존·redaction | WP13, RF07–RF09 |
| 설치·공급망 | pin/lock/receipt·probe·프로세스 감독·asset packaging | 설치 계획·license 검토 체크리스트 | local tool profile | WP00/WP22, RF01/RF10 |

Skill에 '수정하지 마라'고 쓴 것만으로 수정 차단을 구현했다고 판정하지 않는다. 반대로 결정적 Kernel에 모든 질문·회고 문장을 하드코딩하지 않는다. skill은 후보의 품질을 높이고 code는 허가된 행동과 상태를 강제한다. plugin은 등록·배포 단위이며 권한을 우회할 수 있는 특별 계층이 아니다.

## 2. 도입 결정표

| 도구 | Cyrano 개발 때 | 최종 Cyrano 제품 | 이유와 제외되는 중복 |
|---|---|---|---|
| LSP + ty | 권장. 기존 native ty 우선, 독립 설치 recipe 제공 | 선택 활성화되는 Python semantic provider를 정식 구현 | definition/references/diagnostics; 같은 workspace에 같은 의미 서버 중복 금지 |
| Serena | GPL 확인 후 개발자 선택 설치. snapshot-only 실험 | 기본 포함·wheel 결합 안 함. 별도 도입 심사 없이는 미배포 | LSP+MCP 편의는 유용하나 편집·shell·자체 기억·web dashboard가 Cyrano 제어와 충돌 |
| Graphify | 선택. code-only AST graph로 대규모 구조 검토 | 외부 graph의 검증된 읽기 importer만 설계, runtime 필수 아님 | 문서 추론·hooks·reflection을 두 번째 학습 엔진으로 켜지 않음 |
| QMD | 선택. 승인된 개발 문서 corpus keyword 검색 | 선택적 검색 backend. canonical Memory와 분리 | SQLite FTS 기본을 대체 강제하지 않음. CJK·semantic 비용 평가 후 승격 |
| SCIP / scip-python | 선택. snapshot별 offline symbol index | index reader만 선택 제공; Node indexer 항상 탑재 안 함 | 실시간 LSP와 batch index를 동시에 자동 rebuild하지 않음 |
| Knip | 현재 Python-only 범위에는 추가 안 함 | 기본 제외. JS/TS 작업을 수행할 때 승인된 verification recipe 가능 | Python unused 분석 도구가 아님. dynamic export/plugin 오탐과 --fix 위험 |
| Hermes/ACE/MemRL 구현 전체 | 설치하지 않음 | 다른 agent loop/학습 모델 의존성 없음 | 방식만 채택, 기존 dcode·Cyrano 계약 유지 |
| Textual/Rich/pytest 계열 | dcode의 고정 의존성 재사용 | native TUI runtime 재사용 | 새 dashboard 프레임워크·Node 프론트엔드 불필요 |

기능 불필요와 기능 미구현을 혼동하지 않는다. 선택 기능을 사용자가 켰는데 probe가 실패하면 `unsupported/failed`로 표시한다. 조용히 grep으로 대체하고 semantic 분석에 성공했다고 말하지 않는다. lexical fallback을 쓸 경우 result.kind=lexical, completeness=unknown이다.

## 3. 설치와 배포의 네 계층

1. 개발 문서·원본 skill: `libs/code/cyrano/.agents/`와 `plugins/cyrano/`. 개발 절차와 제품 절차를 복제하지 않는다.
2. 개발 도구 실행환경: `libs/code/cyrano/tools/.state/<tool>/`. Git에 포함하지 않는 venv/node_modules/cache. resolver가 lock을 만들고 개발자가 hash를 검토한다.
3. 제품 runtime Python: `libs/code/deepagents_code/cyrano/`. 고객 프로젝트에 `.agents`, Node·Python 의존성을 생성하지 않는다.
4. 제품 tool 환경: 설치한 Cyrano의 외부 profile 아래 content-addressed tool environments. control DB/approval key/holdout과 분리된 principal. source recipe를 재사용하되 개발 경로는 제품에서 읽지 않는다.

공식 upstream 설치법은 package-manager를 사용하되 global 옵션을 제거하고 격리 경로를 지정한다. npm lifecycle·Python build backend는 제3자 코드 실행이다. secret 없는 환경과 네트워크·filesystem 제한을 가진 작업으로 다루며 `$HOME` 변경만으로 sandbox가 된다고 설명하지 않는다. 설치 파일을 project payload에 포함했다는 말은 dependency binaries까지 ZIP에 담았다는 뜻이 아니다.

## 4. 표준 capability와 tool schema

모델 노출은 `cyrano_code_query`, `cyrano_docs_query`, `cyrano_memory_query`, `cyrano_memory_propose`처럼 작은 고정 기능으로 제공한다. 외부 MCP의 수십 개 tool을 원시 노출하지 않는다. 각 provider capability는 artifact hash·schema digest·license·permission·runtime probe와 결속한다. 같은 tool 이름을 두 provider가 등록하면 부팅 실패다.

프로젝트 source·scope·언어·질의 종류로 provider를 선택한다. 모델 이름으로 provider를 고르지 않는다. 실행 도중 optional package가 업데이트돼 tool description/schema가 바뀌면 current epoch를 바꾸지 않고 신규 epoch에서만 활성화한다. 응급 revoke는 기존 작업도 pause한다.

## 5. 금지되는 편의 기능

자동 global install, Graphify hook/strict install, Serena write_memory/execute_shell/직접 source editing, SCIP remote upload, QMD 전체 HOME indexing, 외부 도구가 자동으로 생성한 AGENTS를 상위 지침으로 승격하는 동작을 허용하지 않는다. 외부 데이터는 항상 untrusted evidence이며 지침·도구 요청·승인으로 해석하지 않는다. 누락 기능을 skill에 존재한다고 적어 runtime에서 이미 제공한다고 주장하지 않는다.
