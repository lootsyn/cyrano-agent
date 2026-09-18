# 조사 출처와 검증 경계

조회 기준: 2026-09-16. 실제 GitHub API로 main commit을 확인하고 아래 파일을 고정 revision에서 읽었다. full upstream archive를 이 환경에 clone하지 않았으며 실제 dcode test/빌드/런타임은 검증하지 않았다.

- [현재 branch commit](https://github.com/langchain-ai/deepagents/commit/7f9e8ed3a555933902045792da9bb184950ee7b2): 2026-09-15T21:00:57Z.
- [dcode pyproject](https://github.com/langchain-ai/deepagents/blob/7f9e8ed3a555933902045792da9bb184950ee7b2/libs/code/pyproject.toml): 0.1.69, Python>=3.12, deepagents==0.7.14, Ruff/ty, local sibling dependencies, hatch package include.
- [agent.py](https://github.com/langchain-ai/deepagents/blob/7f9e8ed3a555933902045792da9bb184950ee7b2/libs/code/deepagents_code/agent.py): reviewed ranges 2800–2990, 3390–3530. Blob d3d441f5afb94025b2b9d0c2c957138ca8336b6f. Middleware assembly, memory/skills, subagent policy, rubric, extension registry, create_deep_agent.
- [PEP8](https://peps.python.org/pep-0008/): coding style and project consistency; formatter alone is not full compliance.
- [Deep Agents skills](https://docs.langchain.com/oss/python/deepagents/skills): progressive disclosure; CYRANO release/authority remains our implementation responsibility.

`references/packs/dcode-analysis`의 1d3232c0852c47af09119edea10eeec887e4f0da 분석은 원본 상태로 보존한다. 기존 분석의 파일명·라인·버그 후보를 현재 사실로 전환하려면 WP00에서 실제 source와 테스트로 재확인한다. 특히 parser/server/ACP/TUI 등 세부 삽입 위치는 현재 검토한 agent.py 범위 이상의 구현 확인이 필요하다. 분석팩 71문서는 annotated source clone이 아니다.

Python 설계팩은 상세 계약·정책·테스트 디자인의 참고이며 실행 코드 설치·실제 CI enforcement의 증거가 아니다. toolchain 및 native 배치 차이는 R3 ADR로 명시한다.


## 코드·공식 문서 근거 목록

외부 소스의 이름·URI·검토 범위는 연구자료다. 현재 실행 권한을 발급하지 않는다.

<a id="ns01"></a>
### NS01 · dcode current main

- 원문: https://api.github.com/repos/langchain-ai/deepagents/branches/main
- 조회: 2026-09-17
- 확인 수준: repository_metadata
- 확인 범위: 0.1.70 release commit; dependency installation and publishing were not verified
- 실제 실행: False
- 고정 소스: `229ffef3d41bbe6dcfff3852bbd2058331aabe01`

<a id="ns02"></a>
### NS02 · dcode extensions

- 원문: https://github.com/langchain-ai/deepagents/blob/7f9e8ed3a555933902045792da9bb184950ee7b2/libs/code/EXTENSIONS.md
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: async extension registration, no custom slash command API
- 실제 실행: False
- 고정 소스: `7f9e8ed3a555933902045792da9bb184950ee7b2`

<a id="ns03"></a>
### NS03 · dcode source baseline

- 원문: https://github.com/langchain-ai/deepagents/blob/7f9e8ed3a555933902045792da9bb184950ee7b2/libs/code/deepagents_code/agent.py
- 조회: 2026-09-17
- 확인 수준: prior_baseline_source
- 확인 범위: Existing reviewed baseline; current 0.1.70 source not fully re-audited
- 실제 실행: False
- 고정 소스: `7f9e8ed3a555933902045792da9bb184950ee7b2`

<a id="ns04"></a>
### NS04 · Hermes memory implementation

- 원문: https://github.com/NousResearch/hermes-agent/blob/16bddc88dd325c5eef27c2cc71bbb14c16b870aa/tools/memory_tool.py
- 조회: 2026-09-17
- 확인 수준: source_slice
- 확인 범위: lines 1–190: frozen session prompt, staging, gate import fallback, background consolidation
- 실제 실행: False
- 고정 소스: `16bddc88dd325c5eef27c2cc71bbb14c16b870aa`

<a id="ns05"></a>
### NS05 · Hermes releases

- 원문: https://github.com/NousResearch/hermes-agent/releases
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: tag v2026.9.14, display v0.21.3; latest release observed, not installed
- 실제 실행: False

<a id="ns06"></a>
### NS06 · Hermes memory guide

- 원문: https://hermes-agent.nousresearch.com/docs/user-guide/features/memory
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: small persistent memory and search; do not infer security enforcement
- 실제 실행: False

<a id="ns07"></a>
### NS07 · Gajae ambiguity floor

- 원문: https://github.com/Yeachan-Heo/gajae-code/blob/9da99cdd708ce3b97d64111d8eefc98a7e0921ee/packages/coding-agent/src/gjc-runtime/deep-interview-ambiguity.ts
- 조회: 2026-09-17
- 확인 수준: source_slice
- 확인 범위: lines 1–200: fact disputes, gap pressure, score floor, retraction
- 실제 실행: False
- 고정 소스: `9da99cdd708ce3b97d64111d8eefc98a7e0921ee`

<a id="ns08"></a>
### NS08 · Gajae releases

- 원문: https://github.com/Yeachan-Heo/gajae-code/releases
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: v0.16.7 and v0.16.8-nightly.20260913102120.34830784995.g9da99cdd708c
- 실제 실행: False

<a id="ns09"></a>
### NS09 · OMO recall gate

- 원문: https://github.com/code-yeongyu/oh-my-openagent/blob/fbcc57e374c180c41ffc8562c0ab7e7414935811/packages/memory-core/src/recall/gate.ts
- 조회: 2026-09-17
- 확인 수준: source_slice
- 확인 범위: lines 1–180: candidate membership, caps, pending identity, expiry, hint admission
- 실제 실행: False
- 고정 소스: `fbcc57e374c180c41ffc8562c0ab7e7414935811`

<a id="ns10"></a>
### NS10 · OMO releases

- 원문: https://github.com/code-yeongyu/oh-my-openagent/releases
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: Latest-labelled v5.0.0-beta.68 is prerelease, not stable
- 실제 실행: False

<a id="ns11"></a>
### NS11 · Senpi keepalive implementation

- 원문: https://github.com/code-yeongyu/senpi/blob/f32905c8199b70e45acd866159170d390e48715b/packages/coding-agent/src/core/extensions/builtin/cache-keepalive/index.ts
- 조회: 2026-09-17
- 확인 수준: source_slice
- 확인 범위: lines 1–260: generation, idle, request cap, cost, lastCompletedAt scheduling
- 실제 실행: False
- 고정 소스: `f32905c8199b70e45acd866159170d390e48715b`

<a id="ns12"></a>
### NS12 · Senpi releases

- 원문: https://github.com/code-yeongyu/senpi/releases
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: v2026.9.16-3; experimental project classification retained
- 실제 실행: False

<a id="ns13"></a>
### NS13 · Pi message transformation

- 원문: https://github.com/earendil-works/pi/blob/e4c75a73222ae2c72abb5f5314fa35ee8effc508/packages/ai/src/api/transform-messages.ts
- 조회: 2026-09-17
- 확인 수준: source_slice
- 확인 범위: lines 1–185: IDs, opaque thinking, images, synthetic missing results
- 실제 실행: False
- 고정 소스: `e4c75a73222ae2c72abb5f5314fa35ee8effc508`

<a id="ns14"></a>
### NS14 · Pi releases

- 원문: https://github.com/earendil-works/pi/releases
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: release history reviewed; latest stable tag not reliably captured
- 실제 실행: False

<a id="ns15"></a>
### NS15 · Oh My Pi hashline prompt

- 원문: https://github.com/can1357/oh-my-pi/blob/a2d83061c5d673bf3ee495d7652b63ee5a0ceb14/packages/coding-agent/src/edit/hashline-compact.md
- 조회: 2026-09-17
- 확인 수준: source_excerpt
- 확인 범위: model-visible patch language; parser/runtime implementation not audited
- 실제 실행: False
- 고정 소스: `a2d83061c5d673bf3ee495d7652b63ee5a0ceb14`

<a id="ns16"></a>
### NS16 · Oh My Pi releases

- 원문: https://github.com/can1357/oh-my-pi/releases
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: v18.2.2, replay-safe retry and context notes
- 실제 실행: False

<a id="ns17"></a>
### NS17 · protoCLI SprintContractService

- 원문: https://github.com/protoLabsAI/protoCLI/blob/480f23e1c119a7fe305fcbb20092b2d1394623d4/packages/core/src/services/sprintContractService.ts
- 조회: 2026-09-17
- 확인 수준: source_file
- 확인 범위: parse, activateScopeLock, persist, load, resumeFromDisk
- 실제 실행: False
- 고정 소스: `480f23e1c119a7fe305fcbb20092b2d1394623d4`

<a id="ns18"></a>
### NS18 · protoCLI harness guide

- 원문: https://github.com/protoLabsAI/protoCLI/blob/480f23e1c119a7fe305fcbb20092b2d1394623d4/docs/explanation/agent-harness.md
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: scope primitive retained despite removing opinionated skill
- 실제 실행: False
- 고정 소스: `480f23e1c119a7fe305fcbb20092b2d1394623d4`

<a id="ns19"></a>
### NS19 · protoAgent repository metadata

- 원문: https://api.github.com/repos/protoLabsAI/protoAgent
- 조회: 2026-09-17
- 확인 수준: repository_metadata
- 확인 범위: Python/LangGraph/A2A; updated 2026-09-16; not full source review
- 실제 실행: False

<a id="ns20"></a>
### NS20 · protoAgent releases

- 원문: https://github.com/protoLabsAI/protoAgent/releases
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: v0.168.0; late A2A responses, output budget, timestamps removed from model messages
- 실제 실행: False

<a id="ns21"></a>
### NS21 · Open SWE architecture and operations

- 원문: https://github.com/langchain-ai/open-swe/blob/main/README.md
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: Agent, Reviewer, Analyzer, Chat, Scheduler; persistent sandbox; limitations
- 실제 실행: False

<a id="ns22"></a>
### NS22 · Open SWE releases

- 원문: https://github.com/langchain-ai/open-swe/releases
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: Desktop v0.2.10 observed; not a backend version
- 실제 실행: False

<a id="ns23"></a>
### NS23 · Pactrail workspace transaction

- 원문: https://github.com/AKMessi/pactrail/blob/582a22db473b455f7f5bdc185bf430639b88a49f/crates/pactrail-workspace/src/transaction.rs
- 조회: 2026-09-17
- 확인 수준: source_slice
- 확인 범위: lines 1–220: snapshot copying, source reread, strict reopen; full apply routine not audited
- 실제 실행: False
- 고정 소스: `582a22db473b455f7f5bdc185bf430639b88a49f`

<a id="ns24"></a>
### NS24 · Pactrail overview

- 원문: https://github.com/AKMessi/pactrail/blob/main/README.md
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: transaction/evidence architecture; project claims, not independent runtime validation
- 실제 실행: False

<a id="ns25"></a>
### NS25 · Pactrail package manifest

- 원문: https://github.com/AKMessi/pactrail/blob/main/Cargo.toml
- 조회: 2026-09-17
- 확인 수준: source_file
- 확인 범위: version 1.0.0 and Rust 1.95; release publication not separately verified
- 실제 실행: False

<a id="ns26"></a>
### NS26 · OpenCode agent modes

- 원문: https://opencode.ai/docs/agents/
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: Build/Plan permissions; Plan write/bash ask is not a sandbox
- 실제 실행: False

<a id="ns27"></a>
### NS27 · OpenCode releases

- 원문: https://github.com/anomalyco/opencode/releases
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: v1.18.31; ACP/history/auth fixes
- 실제 실행: False

<a id="ns28"></a>
### NS28 · Cline Plan and Act

- 원문: https://docs.cline.bot/core-workflows/plan-and-act
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: planning/execution interaction, not enforcement proof
- 실제 실행: False

<a id="ns29"></a>
### NS29 · Cline releases

- 원문: https://github.com/cline/cline/releases
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: Desktop 0.0.29, SDK 0.0.83 and CLI 3.0.62 are separate components
- 실제 실행: False

<a id="ns30"></a>
### NS30 · OpenHands SDK

- 원문: https://docs.openhands.dev/sdk
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: agent, tool, workspace and security SDK; benchmark claims not transferred
- 실제 실행: False

<a id="ns31"></a>
### NS31 · OpenHands releases

- 원문: https://github.com/OpenHands/OpenHands/releases
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: v1.19.0 product repo; SDK package versions are separate
- 실제 실행: False

<a id="ns32"></a>
### NS32 · Continue modes

- 원문: https://docs.continue.dev/ide-extensions/agent/how-it-works
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: Chat/Plan/Agent and tool availability; link can redirect
- 실제 실행: False

<a id="ns33"></a>
### NS33 · Continue releases

- 원문: https://github.com/continuedev/continue/releases
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: v2.0.0-vscode observed; other component latest unresolved
- 실제 실행: False

<a id="ns34"></a>
### NS34 · Qwen Code overview

- 원문: https://github.com/QwenLM/qwen-code
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: terminal/IDE/headless/SDK; qwen serve experimental
- 실제 실행: False

<a id="ns35"></a>
### NS35 · Qwen Code releases

- 원문: https://github.com/QwenLM/qwen-code/releases
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: v0.24.0 and 0.24.0-nightly.20260916.b8def02aad
- 실제 실행: False

<a id="ns36"></a>
### NS36 · Crush overview

- 원문: https://github.com/charmbracelet/crush
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: terminal and tool integrations; native runtime not copied
- 실제 실행: False

<a id="ns37"></a>
### NS37 · Crush releases

- 원문: https://github.com/charmbracelet/crush/releases
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: v0.95.0 and nightly channel
- 실제 실행: False

<a id="ns38"></a>
### NS38 · Kilo Code releases

- 원문: https://github.com/Kilo-Org/kilocode/releases
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: v7.7.2; goal/review/worktree product surfaces, docs endpoints failed
- 실제 실행: False

<a id="ns39"></a>
### NS39 · Goose overview

- 원문: https://github.com/aaif-goose/goose
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: canonical redirect from block/goose; recipe and tool harness overview
- 실제 실행: False

<a id="ns40"></a>
### NS40 · Goose releases

- 원문: https://github.com/aaif-goose/goose/releases
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: v1.50.1; preceding release includes cache anchors and ACP context changes
- 실제 실행: False

<a id="ns41"></a>
### NS41 · Aider repository map

- 원문: https://aider.chat/docs/repomap.html
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: compact repository map and selective context; not a full dynamic call graph
- 실제 실행: False

<a id="ns42"></a>
### NS42 · Aider releases

- 원문: https://github.com/Aider-AI/aider/releases
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: v0.86.0; not presented as a 2026 innovation
- 실제 실행: False

<a id="ns43"></a>
### NS43 · mini-SWE-agent docs

- 원문: https://mini-swe-agent.com/latest/
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: minimal model-agent-environment architecture, ablation baseline
- 실제 실행: False

<a id="ns44"></a>
### NS44 · mini-SWE-agent releases

- 원문: https://github.com/SWE-agent/mini-swe-agent/releases
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: v2.4.6
- 실제 실행: False

<a id="ns45"></a>
### NS45 · Gemini CLI core

- 원문: https://geminicli.com/docs/core/
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: core tools/policy/sessions; experimental routing not a portability proof
- 실제 실행: False

<a id="ns46"></a>
### NS46 · Gemini CLI releases

- 원문: https://github.com/google-gemini/gemini-cli/releases
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: v0.60.0 stable, prerelease channel separate
- 실제 실행: False

<a id="ns47"></a>
### NS47 · Kiro specifications

- 원문: https://kiro.dev/docs/specs/
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: feature/bugfix/quick specs; capability differs across IDE/CLI/Web
- 실제 실행: False

<a id="ns48"></a>
### NS48 · Kiro changelog

- 원문: https://kiro.dev/changelog/
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: IDE 1.1 on 2026-09-14; CLI v2 path separate; closed internals
- 실제 실행: False

<a id="ns49"></a>
### NS49 · Amp documentation

- 원문: https://ampcode.com/docs
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: commercial product interface; source internals unverified
- 실제 실행: False

<a id="ns50"></a>
### NS50 · Amp chronicle

- 원문: https://ampcode.com/chronicle
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: 2026-09-13 Free Agent and other updates; no verified numeric stable
- 실제 실행: False

<a id="ns51"></a>
### NS51 · Cursor Plan mode

- 원문: https://cursor.com/docs/agent/plan-mode
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: reviewable planning before build; no independent authorization guarantee
- 실제 실행: False

<a id="ns52"></a>
### NS52 · Cursor changelog

- 원문: https://cursor.com/changelog
- 조회: 2026-09-17
- 확인 수준: release_notes
- 확인 범위: Projects beta and 2026-09-02 self-hosted agents; no version conflation
- 실제 실행: False

<a id="ns53"></a>
### NS53 · Claude prompt caching

- 원문: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: TTL starts at request START, prefix identity, provider-specific boundaries
- 실제 실행: False

<a id="ns54"></a>
### NS54 · OpenAI prompt caching

- 원문: https://developers.openai.com/api/docs/guides/prompt-caching
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: provider caching guide; no assumed uniform TTL or shared cache
- 실제 실행: False

<a id="ns55"></a>
### NS55 · Gemini context caching

- 원문: https://ai.google.dev/gemini-api/docs/caching
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: provider-specific cache semantics; not a generic local cache
- 실제 실행: False

<a id="ns56"></a>
### NS56 · LangGraph persistence

- 원문: https://docs.langchain.com/oss/python/langgraph/persistence
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: checkpoint/resume; business authority remains Cyrano-owned
- 실제 실행: False

<a id="ns57"></a>
### NS57 · LangGraph interrupts

- 원문: https://docs.langchain.com/oss/python/langgraph/interrupts
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: interrupt and resume; no external exactly-once guarantee
- 실제 실행: False

<a id="ns58"></a>
### NS58 · Agent Client Protocol v1

- 원문: https://agentclientprotocol.com/protocol/v1/overview
- 조회: 2026-09-17
- 확인 수준: official_specification
- 확인 범위: capability negotiation, prompt, cancel, permission, filesystem and terminal
- 실제 실행: False

<a id="ns59"></a>
### NS59 · A2A specification

- 원문: https://a2a-protocol.org/latest/specification/
- 조회: 2026-09-17
- 확인 수준: official_specification
- 확인 범위: agent tasks/status/artifacts; dynamic latest must be pinned before implementation
- 실제 실행: False

<a id="ns60"></a>
### NS60 · MCP 2025-11-25

- 원문: https://modelcontextprotocol.io/specification/2025-11-25
- 조회: 2026-09-17
- 확인 수준: official_specification
- 확인 범위: dated tool/resource/prompt protocol; not asserted latest
- 실제 실행: False

<a id="ns61"></a>
### NS61 · Agent Skills specification

- 원문: https://agentskills.io/specification
- 조회: 2026-09-17
- 확인 수준: official_specification
- 확인 범위: progressive skill discovery; instructions are not execution authority
- 실제 실행: False

<a id="ns62"></a>
### NS62 · ACE paper

- 원문: https://arxiv.org/abs/2510.04618
- 조회: 2026-09-17
- 확인 수준: paper_abstract
- 확인 범위: 2025 incremental playbook/context adaptation; abstract-level review only
- 실제 실행: False

<a id="ns63"></a>
### NS63 · MemRL paper

- 원문: https://arxiv.org/abs/2601.03192
- 조회: 2026-09-17
- 확인 수준: paper_abstract
- 확인 범위: 2026 retrieval relevance plus utility, frozen model; abstract-level review only
- 실제 실행: False

<a id="ns64"></a>
### NS64 · LLMCompiler paper

- 원문: https://arxiv.org/abs/2312.04511
- 조회: 2026-09-17
- 확인 수준: paper_abstract
- 확인 범위: 2023 foundational planner/task scheduler/executor; not new in 2026
- 실제 실행: False

<a id="ns65"></a>
### NS65 · Mem2Evolve paper

- 원문: https://arxiv.org/abs/2604.10923
- 조회: 2026-09-17
- 확인 수준: paper_abstract
- 확인 범위: 2026 experience and asset evolution; abstract only, code not executed
- 실제 실행: False

<a id="ns66"></a>
### NS66 · Beads repository

- 원문: https://github.com/gastownhall/beads
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: canonical redirect; dependency-aware task ledger, not a replacement store
- 실제 실행: False

<a id="ns67"></a>
### NS67 · Superpowers planning

- 원문: https://github.com/obra/superpowers/blob/main/skills/writing-plans/SKILL.md
- 조회: 2026-09-17
- 확인 수준: prior_reference
- 확인 범위: R6 conversation reference; no current-version source reread in this supplement
- 실제 실행: False

<a id="ns68"></a>
### NS68 · Spec Kit agentic SDD

- 원문: https://github.com/github/spec-kit/blob/main/docs/reference/agentic-sdd.md
- 조회: 2026-09-17
- 확인 수준: prior_reference
- 확인 범위: R6 conversation reference; keep existing review/approval separation
- 실제 실행: False

<a id="ns69"></a>
### NS69 · OpenSpec

- 원문: https://github.com/Fission-AI/OpenSpec
- 조회: 2026-09-17
- 확인 수준: prior_reference
- 확인 범위: change-scoped documents, no second workflow authority
- 실제 실행: False

<a id="ns70"></a>
### NS70 · Inception official repository

- 원문: https://github.com/Milind220/inception/blob/main/README.md
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: Milind220/inception matches generated-workflow description; npm publication marked incomplete; claims not independently reproduced
- 실제 실행: False
- 고정 소스: `blob:8181018b5360df6641f6ab27e820b978c0c5f29a`

<a id="ns71"></a>
### NS71 · Inception execution implementation

- 원문: https://github.com/Milind220/inception/blob/main/packages/runtime/src/run.ts
- 조회: 2026-09-17
- 확인 수준: source_slice
- 확인 범위: lines 1–240: shared budget/depth/limiter, null on item failure, best-effort orchestration; no runtime execution
- 실제 실행: False
- 고정 소스: `blob:9778fddb87aa6bebb7b5f9b87c08659499c25b43`

<a id="ns72"></a>
### NS72 · Inception journal implementation

- 원문: https://github.com/Milind220/inception/blob/main/packages/runtime/src/journal.ts
- 조회: 2026-09-17
- 확인 수준: source_file
- 확인 범위: call key, schema fingerprint fallback, image-count key, best-effort journal, occurrence matching
- 실제 실행: False
- 고정 소스: `blob:9fd4aee15f18494ed6275e60835440ecd6a9dfca`

<a id="ns73"></a>
### NS73 · LangGraph Interrupts

- 원문: https://docs.langchain.com/oss/python/langgraph/interrupts
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: resume reruns node prefix; correlate parallel interrupt IDs; not a Cyrano authorization implementation
- 실제 실행: False

<a id="ns74"></a>
### NS74 · LangGraph Persistence

- 원문: https://docs.langchain.com/oss/python/langgraph/persistence
- 조회: 2026-09-17
- 확인 수준: official_documentation
- 확인 범위: checkpoint persistence; no external exactly-once guarantee inferred
- 실제 실행: False
