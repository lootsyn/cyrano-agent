# Code Intelligence·문서 검색·프로젝트 설치 상세 설계

문서 유형: 목표 상세 설계. `intelligence/contracts.py`는 일부 순수 검사를 제공한다. 실제 subprocess·LSP·MCP·QMD 연결은 RF01–RF03 구현 대상이다. 외부 source 라이선스 및 API 근거는 [R5 연구](../reference/R5_RESEARCH.ko.md) [S10]–[S21]이다.

## 1. 데이터와 소유권

`AnalysisSession` 필드: analysis_id, tenant/user/workspace, source_digest, environment_digest, acl_digest, provider_digest, requested_capabilities, verified_capabilities, state, process_lease, generation, budget_ref. state는 requested→preparing→ready→stale/stopping/failed→closed. 임의 provider가 source_digest를 정하지 않는다. Broker의 snapshot manifest가 기준이다.

`CodeQuery`: operation, source_ref, position, position_encoding, query, limit, expected_binding. scope는 인증한 run token에서 유도한다. `CodeAnswer`: query_id, provider, binding, kind(exact_symbol/lexical/ast_edge/inferred_edge), locations, evidence_refs, truncated, unsupported_fields, completeness, elapsed_ms. confidence 숫자를 진실 확률로 표시하지 않는다. result 텍스트의 shell 명령은 실행하지 않는다.

`IndexManifest`: schema_version, provider_digest, source_digest, environment_digest, acl_digest, corpus_digest, index_digest, supported_operations, source_files[{path,sha256}], entry_count, truncated, built_at. hash는 파일 내용 증명이지 안전성 증명이 아니다. 공급자와 승인된 policy를 따로 검증한다. 삭제·권한 철회 후 cached index가 계속 결과를 주지 않도록 canonical tombstone/ACL을 query 시 재검사한다.

## 2. LSP lifecycle 알고리즘

`AnalysisManager.open(binding, request) -> AnalysisSession`는 scope별 lease를 얻고, 격리 환경에서 승인된 absolute executable과 argv로 서버를 띄운다. dcode/.venv의 ty를 쓸 경우 runtime-lock과 executable 해시를 먼저 비교한다. language server는 immutable workspace clone을 rootUri로 보고 temp 산출물만 쓸 수 있다. environment/site-packages resolution 경로는 승인된 interpreter manifest에서 읽는다.

initialize에서 client supported position encodings를 명시하고 서버 응답의 capabilities와 encoding을 저장한다. initialized 후 didOpen/didChange의 version과 source hash를 결속한다. 현재 구현은 closed snapshot 질의를 우선 지원한다. 편집 중 buffer를 지원할 때에는 disk snapshot과 overlay buffer version을 별도 manifest로 기록하고 과거 index와 혼합하지 않는다.

각 요청은 id, generation, timeout, cancellation token을 가진다. stdout은 Content-Length framed JSON-RPC만, stderr는 bounded redacted log다. partial frame, malformed UTF-8/JSON, 초과 payload, 알 수 없는 response ID, restart 이전 late response를 거부한다. UTF-16과 UTF-8 위치를 변환할 때 한국어·이모지·CRLF fixture를 반드시 사용한다. `workspace/applyEdit`, rename, codeAction의 edit, executeCommand는 읽기 gateway에서 거부한다. 사용자가 refactor를 요청해도 LSP edit은 candidate patch로 바꾸고 Broker 승인 후 적용해야 한다.

request 종료·workspace 이동 시 shutdown→exit→제한 시간 후 process-tree kill한다. server가 재시작하면 generation이 바뀌고 기존 response cache는 폐기한다. 같은 입력 중복 query는 in-flight coalesce 가능하지만 scope가 다른 요청끼리 합치지 않는다. global server 한 개로 여러 고객 프로젝트를 바꿔 활성화하지 않는다.

## 3. Graphify와 SCIP batch indexing

Graphify는 `graphify extract <snapshot> --code-only --no-cluster`를 기본으로 쓴다. 실행할 pinned package의 help에 두 flag가 있어야 한다. model key를 전달하지 않고 egress를 막아 code-only 계약을 동적으로 검사한다. subprocess CWD와 output 모두 owned scratch이며 프로젝트 root에 graph.json·hooks·AGENTS를 쓰지 않는다. generated/doc/holdout/secrets는 export 전에 제외한다. `reflect`, `save-result`, `global`, `hook`, `install --strict`, `--dedup-llm`은 자동 호출 목록에 없다.

SCIP은 `scip-python index <snapshot> --project-name=cyrano --environment=<json>`로 배치 생성한다. 환경 JSON은 실제 개발 환경 metadata에서 만든다. 임의 pip 상태나 전역 virtualenv를 이용해 잘못된 import graph를 만들지 않는다. protobuf의 size/recursion/entry cap, path traversal, symbol string parser, 외부 package symbol resolution을 검증한다. index의 source hash가 바뀌면 즉시 stale. Graphify·SCIP 결과는 canonical memory로 자동 저장하지 않고 근거 후보로만 전달한다.

AST edge는 구문 분석 결과이고 런타임 dispatch의 완전한 call graph가 아니다. 동적 plugin registration·reflection·monkey patch는 incomplete로 남긴다. Knip의 unused 보고도 dynamic entrypoints의 증거와 수동 검토 없이 삭제 근거가 되지 않는다.

## 4. QMD corpus·SDK

`CorpusExporter.export(scope, document_ids, release) -> CorpusManifest`는 원본에서 ACL·status·freshness·sensitivity를 검사한 파일만 새 디렉터리에 복사한다. 개발 corpus는 docs/design/development/execution의 승인된 범위와 선택 참고문서다. `references` 전체, 원시 trace, credentials, hidden tests, 승인 원장, generated 통합본을 무조건 넣지 않는다. source 문서 ID→export path→SHA256의 역매핑을 기록한다.

QMD [S17] SDK의 `createStore({dbPath,config:{collections:{docs:{path,pattern:'**/*.md'}}}})`, `update({collections:['docs']})`, `searchLex(query,{limit})`, `close()`만 keyword 기본 adapter에서 사용한다. `search({query})`는 자동 query expansion·vector·reranking을 유발할 수 있어 keyword 대체로 쓰지 않는다. unknown option 무시 가능성을 고려하여 QMD의 collection/filter 인자를 ACL의 유일한 장치로 사용하지 않는다. scope별 DB+corpus로 물리 분리하고 반환 path·digest를 broker가 재검증한다.

embedding/rerank는 별도 opt-in. model URL·revision·SHA·license·download bytes·disk/GPU budgets·CJK 결과를 model manifest에 기록한다. keyword 실패 시 embedding으로 몰래 전환하지 않는다. offline disabled 상태에서 model download가 일어나면 test hard fail. model 변경 시 새 index, 전역 shared cache는 사용자 문서 검색 결과를 저장하지 않는다.

## 5. Side effects와 해결 책임

| 위험 | 제어 | 필수 검증 |
|---|---|---|
| package/source 의존성 충돌 | tool별 venv/node_modules, native uv.lock 무수정 | 설치 전후 source/lock diff |
| 임의 build/lifecycle 코드 | 승인·secret-free build·OS sandbox | canary secret·network tripwire |
| 글로벌 home·hooks 오염 | explicit state path·실행 명령 allowlist | 임시 HOME/상위 AGENTS pre/post hash |
| index 불일치 | snapshot/env/provider/ACL 결속·stale | 한 파일/권한 변경 후 답변 거부 |
| cache 파괴 | metadata 안정·외부 index output offload | 같은 epoch prompt manifest 불변 |
| Memory 중복 학습 | 외부 memory writes 비노출·Cyrano candidate only | write_memory/shell/reflect 시도 거부 |
| CJK 검색 저하 | 한국어 fixture, lexical/vector 각각 기준 | recall@k+실제 plan 적용; 임의 영어 번역 강제 금지 |
| CPU/RAM·watcher 폭주 | explicit index task·max workers·취소·동시성 1 | 큰 repo·restart·cancel 부하 시험 |
| copyleft/NOTICE 의무 | direct/transitive license manifest·배포 승인 | wheel/SBOM/NOTICE 검토; Serena 기본 미배포 |

## 6. 제품 패키지와 first-use

Cyrano wheel에는 실행 코드와 승인된 compact role/skill/schema asset만 포함한다. development docs·원본 팩·node_modules는 포함하지 않는다. 실제 wheel include는 dcode hatch config를 RF10에서 수정·검증한다. JSON asset이 소스 트리에 있다고 wheel에 자동 들어갔다고 가정하지 않는다.

optional tool 처음 사용 시 operator에게 tool identity/version/license, 설치 위치, 다운로드·build·네트워크·읽을 snapshot 범위를 표시한다. `installed`, `probe_passed`, `authorized`, `enabled` 네 상태가 모두 충족되어야 provider가 usable이다. 설치 실패는 lexical fallback 여부를 명시적으로 보여 주고, optional 기능을 끈 기본 coding 기능은 보존한다.

## 7. SCIP 환경 manifest의 정확한 형식

공식 scip-python의 `--environment`는 package 배열이다. 원소는 `{"name":"PyYAML","version":"6.0","files":["yaml/__init__.py","PyYAML-6.0.dist-info/INSTALLER"]}` 형태다. pip freeze 문자열이나 name/version만 있는 pip list JSON과 혼동하지 않는다. RF03은 승인된 interpreter의 importlib.metadata에서 distribution별 파일 목록까지 수집하여 정렬·hash하고 source/import path 설정과 함께 보관한다. 파일을 직접 import하거나 pip install하지 않는다. editable distribution에 파일 목록이 없으면 불완전 상태를 보고하고 빈 환경을 정답처럼 사용하지 않는다. 생성 명령은 sourcegraph upload와 분리하며 이 프로젝트는 자동 업로드하지 않는다. [S18]

SCIP protobuf reader를 구현할 때 공식 schema의 source commit·license·codegen version을 고정하고 별도 dependency review를 남긴다. 현재 ZIP은 생성된 SCIP parser를 포함하지 않는다. 미확인 format을 JSON으로 간주하거나 LLM이 유사 구조를 추정해서 읽게 하지 않는다.

## 1. 작은 조회에서 정확한 근거로 확장

text search → 구조적 repo map → symbol index → LSP 질의 → AST/graph를 필요에 따라 사용한다. 모든 단계가 항상 실행되는 pipeline은 아니다. `IntelligenceResult`는 provider, source digest, environment digest, ACL scope, path/range, relation kind, confidence class, expires/dependencies를 가진다.

`lexical_reference`, `syntax_relation`, `language_server_symbol`, `inferred_semantic_relation`을 구분한다. semantic edge를 runtime call graph라고 부르지 않는다. 같은 이름의 symbol을 발견했다고 동일 identity라고 합치지 않는다. 테스트 선택을 줄이려면 영향 분석의 누락률을 실제 regression으로 검증해야 한다.

## 2. 기존 외부 도구 정책 유지

LSP/ty는 우선 기존 dcode 환경을 검증한다. Graphify는 선택적인 code-only 자료, QMD는 선택 문서 검색, SCIP는 static snapshot으로 처리한다. Serena/Knip을 의무 dependency로 바꾸지 않는다. raw MCP tools에 unrestricted edit/shell을 노출하면 승인 경로가 우회되므로 wrapper 또는 별도 principal로 제한한다.

인덱스 build는 source snapshot에서만 실행하며 target 원본에 `.serena`/`.graphify`/SQLite/모델파일을 자동 설치하지 않는다. read-only 검증 범위에서 실행하고 프로젝트 전용 scratch를 사용한다. 외부 scanner도 임의 config/plugin을 실행할 수 있으므로 build script 신뢰를 별도 검사한다.

## 3. PatchAnchor

anchor에는 전체 파일 digest, 원문 exact byte range, expected content digest, path identity, encoding/newline policy를 가진다. 보기 좋게 줄 옆에 짧은 hash를 표시할 수 있지만 그것은 보조 주소다. 실제 판정은 전체 파일 snapshot과 정확한 원문 비교를 사용한다. [Oh My Pi의 hashline 지시](../reference/SOURCES.ko.md#ns15)는 이런 인터페이스의 비교 후보다.

`validate_patch`는 경로·scope·symlink·file type·mode·baseline을 검증한 다음 in-memory candidate에 모든 hunk를 적용한다. 하나라도 실패하면 전체 요청은 무효다. fuzzy offset으로 재시도하지 않는다. stale anchor이면 새 원문을 읽고 patch를 새로 제안한다. 긴 파일의 elision은 읽은 것으로 취급하지 않는다.

## 4. 원자성의 정확한 의미

여러 파일을 OS 한 번의 rename으로 원자 반영할 수 있다고 주장하지 않는다. candidate 준비는 한 artifact로 불변화하고, 원본 반영은 journaled multi-file transaction으로 복구 가능하게 만든다. apply 전 source가 baseline과 같은지, 적용 중 각 파일을 누가 소유하는지, crash 후 어떤 파일이 교체됐는지를 추적한다. [Pactrail source](../reference/SOURCES.ko.md#ns23)의 source-after-copy 검사는 참고하지만 전체 crash-safe 구현을 이식했다는 뜻은 아니다.

순서: `prepared → authorized → effect_fenced → applying → applied → post_verified`. 실패는 `needs_reconciliation` 또는 `rollback_pending`이다. 파일별 before/after digest와 mode를 기록한다. journal 쓰기 실패 시 효과를 시작하지 않는다. 복원 중 사용자가 수정한 파일은 덮어쓰지 않고 conflict로 중단한다.

## 5. TOCTOU와 freshness

mutable 디렉터리에서 path.resolve()를 한 번 호출한 뒤 일반 open()하는 것만으로 symlink race를 막지 못한다. Broker는 변경 불가능한 승인 snapshot 또는 검증된 directory-descriptor 기반 파일 접근을 제공한다. Windows/macOS/Linux별 구현이 이 계약을 충족하는지 실측한다. 환경이 제공하지 못하면 advisory로 표시하고 governed 모드에서 멋대로 fallback하지 않는다.

파일 변경뿐 아니라 language server 버전·compiler options·dependency graph·ACL이 바뀌어도 관련 index를 invalidation한다. 삭제 요청은 semantic retrieval·cached hints·exports까지 도달해야 한다. 읽기 권한이 철회되면 기존 인덱스로 해당 내용을 다시 보여주지 않는다.

## 6. 완료 조건

같은 코드 작업에서 naive text edit와 anchor edit의 실패·재읽기·정확성·비용을 비교한다. 한 benchmark의 편집 성공률을 모든 프로젝트로 일반화하지 않는다. 실제 product acceptance는 CRLF, 한글 조합형/분해형, 같은 줄 반복, rename·mode 변경, binary, symlink race, disk-full, crash-before/after journal을 포함한다.
