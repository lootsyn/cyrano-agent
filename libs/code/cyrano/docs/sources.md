# 조사 출처와 채택 범위

조회 기준:2026-09-16. DeepSeek Harness snapshot은 `0d1f50007f9bca3f52b06e1c3074fa14d5fb0720`다. 공개 root/package/docs/Agent Notes 구조를 확인했으며 전체 upstream 실행·보안 감사를 수행하지 않았다. 공식 dcode main 문서의 확인과 설치 호환성 증거를 구분한다.

| ID | 1차 자료 | 사용 범위 |
|---|---|---|
| S01 | [DeepSeek Harness architecture](https://github.com/deepseek-ai/deepseek-harness/blob/0d1f50007f9bca3f52b06e1c3074fa14d5fb0720/docs/architecture.md) | plugin/service/provider/consumer, composition, model-visible logs |
| S02 | [DeepSeek Harness Agent Notes](https://github.com/deepseek-ai/deepseek-harness/blob/0d1f50007f9bca3f52b06e1c3074fa14d5fb0720/.agents/notes/README.md) | lifecycle/class, proposed/implemented headers, alternatives |
| S03 | [DeepSeek Harness documentation and agent rules](https://github.com/deepseek-ai/deepseek-harness/blob/0d1f50007f9bca3f52b06e1c3074fa14d5fb0720/docs/AGENTS.md) | one home per fact, short AGENTS, package README/subsystems/skills |
| S04 | [dcode Python extensions](https://github.com/langchain-ai/deepagents/blob/main/libs/code/EXTENSIONS.md) | async factory, supported registrations, rebuild, trust limitations |
| S05 | [Deep Agents skills](https://docs.langchain.com/oss/python/deepagents/skills) | progressive disclosure metadata/body/resources |
| S06 | [LangChain custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom) | lifecycle/model/tool extension boundaries |
| S07 | [OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) | exact prefix and actual usage; not response caching |
| S08 | [Anthropic prompt caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) | provider native cache controls, not universal TTL |
| S09 | [OpenRouter prompt caching](https://openrouter.ai/docs/guides/best-practices/prompt-caching) | provider routing/cache semantics need actual observation |
| S10 | [DREAM](https://dream-rsi.com/) | prior supplied DREAM analysis and replay design; no product effectiveness replication |
| S11 | [dcode package metadata](https://github.com/langchain-ai/deepagents/blob/main/libs/code/pyproject.toml) | main observed code0.1.69/deepagents0.7.14/Python>=3.12; not local install |
| S12 | [PEP8](https://peps.python.org/pep-0008/) | Python style reference; formatter alone does not prove all rules |

## 많이 채택한 구조

기능별 package, apps composition root, service definition/provider/consumer, reversible lifecycle, typed durable events, root/subtree AGENTS, 역할과 progressive skills, lifecycle/class Agent Notes, 문서 계층, source/artifact 분리, 실제 실행 evidence와 generated reference 검사를 채택했다.

## 의도적으로 채택하지 않은 구현

Cordis/TypeScript 실행 엔진, 모든 부분의 자유로운 runtime hot replacement, JS를 평가하는 config, 특정 모델 중심 preset, 사용자 목적과 다른 Node application launcher는 이식하지 않았다. 코딩 실행은 dcode에 유지하고 권한·evaluator·audit는 일반 비신뢰 plugin에서 교체하지 못한다.

## 기존 첨부

references/input-manifest.json에 ZIP hash를, references/interview와 references/dream에 원문을 보존했다. 외부 모델/서버를 실행하거나 연구 성과를 재현한 증거는 없다. 새 상세 설계는 그 자료의 입력을 프로젝트 구조·계약·작업계획으로 구체화한 제안이다.
