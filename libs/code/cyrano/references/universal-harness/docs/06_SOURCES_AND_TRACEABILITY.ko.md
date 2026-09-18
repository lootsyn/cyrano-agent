# 출처·첨부 설계 보존·요구사항 추적

## 외부 1차 자료

조회 기준: 2026-09-15. 아래는 공개 문서/main에서 확인한 기능 범위다. 사용자 설치 버전을 실행 검증한 자료가 아니다. 외부 URL은 변할 수 있으므로 WP00에서 실제 배포 artifact·버전·hash·API 계약 결과를 별도로 고정한다. 확장 기능의 존재와 UDH가 제안하는 강제 보안·업무 엔진은 서로 다른 주장이다.

### [S01] dcode Python extensions
- 원문: https://github.com/langchain-ai/deepagents/blob/main/libs/code/EXTENSIONS.md
- 확인 범위: experimental flag, registration methods, user/plugin distribution, custom slash-command exclusion, storage and security boundary

### [S02] dcode Hooks
- 원문: https://github.com/langchain-ai/deepagents/blob/main/libs/code/HOOKS.md
- 확인 범위: lifecycle hooks, trust, concurrency, failure semantics

### [S03] Deep Agents Memory
- 원문: https://docs.langchain.com/oss/python/deepagents/memory
- 확인 범위: persistent memory/backend concepts; not a claim that UDH is built in

### [S04] Deep Agents Skills
- 원문: https://docs.langchain.com/oss/python/deepagents/skills
- 확인 범위: metadata and on-demand skill context

### [S05] Deep Agents graph assembly
- 원문: https://github.com/langchain-ai/deepagents/blob/main/libs/deepagents/deepagents/graph.py
- 확인 범위: native middleware and integration assembly; actual version must be tested

### [S06] LangChain custom middleware
- 원문: https://docs.langchain.com/oss/python/langchain/middleware/custom
- 확인 범위: model/tool/lifecycle extension interfaces and ordering

### [S07] PEP 8
- 원문: https://peps.python.org/pep-0008/
- 확인 범위: style baseline, line length, project conventions

### [S08] dcode threat model
- 원문: https://github.com/langchain-ai/deepagents/blob/main/libs/code/THREAT_MODEL.md
- 확인 범위: user state, trust roots and runtime security context

### [S09] dcode package metadata
- 원문: https://github.com/langchain-ai/deepagents/blob/main/libs/code/pyproject.toml
- 확인 범위: observed main Python/dependency/version declarations, not user runtime pin

### [S10] OpenTelemetry GenAI semantic conventions
- 원문: https://github.com/open-telemetry/semantic-conventions-genai
- 확인 범위: optional version-pinned GenAI telemetry mapping

### [S11] LangSmith tracing
- 원문: https://docs.langchain.com/langsmith/trace-with-langchain
- 확인 범위: optional trace integration; no default raw remote export in UDH

### [S12] Deep Agents sandboxes
- 원문: https://docs.langchain.com/oss/python/deepagents/sandboxes
- 확인 범위: execution backends; UDH governed isolation is a separate contract

### [S13] Deep Agents subagents
- 원문: https://docs.langchain.com/oss/python/deepagents/subagents
- 확인 범위: delegation interfaces; policy inheritance requires testing

### [S14] dcode architecture
- 원문: https://github.com/langchain-ai/deepagents/blob/main/libs/code/ARCHITECTURE.md
- 확인 범위: client/server and integration context

### [S15] Ruff formatter documentation
- 원문: https://docs.astral.sh/ruff/formatter/
- 확인 범위: formatter/linter role distinction; UDH chooses Black as sole formatter

### [S16] Black code style
- 원문: https://black.readthedocs.io/en/stable/the_black_code_style/current_style.html
- 확인 범위: 기본 행 길이 88, PEP8 전체 규칙과 formatter의 차이.

## [I01] 첨부 Decision Interview 설계

입력: `interview-plugin-design-kit.zip`. 14개 파일을 `source_interview/`에 그대로 보존했다. SHA-256 및 bytes는 `fixtures/source-interview-manifest.json`에 있다. 검색 인덱스가 ZIP 본문을 반환하지 않아 실제 압축 파일을 안전하게 해제하고 문서·계약·fixture를 읽었다. 원본 문서의 기존 웹 출처는 배경 자료로 보존했으며 그 과거 저장소 commit을 이번에 재검증했다고 주장하지 않는다.

| 원본 핵심 | UDH 반영 | 회귀 증거 |
|---|---|---|
| deterministic kernel / host와 engine 분리 | 2·4·5·21–24장 | 원본 R01–R22 + RUN |
| 사용자 의도 / 관측 사실 / 가설 구분 | 4·6·30장 | R02/R03/R06/R10/R11 |
| blocker 중심 준비도, 점수로 우회 금지 | 5·6·30장 | R01/R07/R09/R15/R16 |
| Scout/Critic/Blind Handoff | 6·8·29장, 역할 prompt | R17/R18/R21/R22 |
| 원문·revision·idempotency·snapshot | 4·5·24장 | R04/R05/R12/R13/R14/R20 |
| 계획용 승인 ≠ 실행 승인 | 7·9·28장 | PLAN-07/AUTH-03 |
| HMAC v1 receipt | 원본 유지, 신규 v2 Ed25519 별도 schema | AUTH-02/AUTH-03 |
| readiness fixture 22개 | 내용 그대로 통합 | source hash + text comparison |
| WORKER 계약·policy·prompts | 원본 보존, UDH-specific 새 계약 추가 | schema negatives/role authority tests |

## 요구사항별 구현 연결

| 요구 | 문서 장 | WP | 테스트 그룹 |
|---|---|---|---|
| 비침습 dcode 확장 | 1–3,10,29 | 00,05,10,20 | OPS/AUTH |
| 모델 비특화 전체 기능 | 0,8,11,13,30 | 00,10,11,17 | CACHE-10/OPS |
| 인터뷰 | 4–6,30 | 04,06,07 | R01–R22 |
| 사전 계획·리뷰 | 5,7,16,22–25 | 07,08,09,15 | PLAN |
| 캐시·컨텍스트 | 11,30 | 11,14,21 | CACHE |
| 적극 Memory | 12,28,30 | 12,16 | MEM |
| Self-Improving | 13,28,30 | 16,17,18 | LEARN |
| 전체 모니터링 | 14,16,18 | 14,15,19 | OBS |
| PEP8 및 Python 품질 | 15–16 | 01,13,21 | PY |
| 승인·격리·회복 | 9,18,23–24 | 02,03,05,09,20 | AUTH/RUN/OPS |

UDH의 상태기계 확장, typed contracts, 보안 broker, 기억 검색/승격 규칙, 평가·관측·테스트 설계는 본 요청을 위한 제안이다. 기존 dcode가 이 모든 것을 기본 제공한다고 표현하지 않는다.
