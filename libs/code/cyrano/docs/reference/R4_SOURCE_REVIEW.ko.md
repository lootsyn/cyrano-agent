# 원본 dcode 검토 근거 · R4

문서 유형: 참고/조사 기록. 조회일: 2026-09-16. main 확인 SHA: `7f9e8ed3a555933902045792da9bb184950ee7b2`. 아래는 원본 사실이며 Cyrano 제품 구현 증거가 아니다.

| 확인 자료 | 확인한 사실 | 설계 영향 |
|---|---|---|
| GitHub branches/main | 위 SHA가 조회됨 | 설치 baseline 고정 |
| `libs/code/DEVELOPMENT.md` | 전체 clone 후 `libs/code`에서 개발; `uv sync --group test`, `uv run deepagents-code`; make bootstrap은 hooks도 설치 | copy destination과 dependency/bootstrap 절차 분리 |
| `libs/code/pyproject.toml` | `deepagents`, `deepagents-acp`, partners 로컬 경로 의존; native Ruff/ty; wheel resources 설정 | 전체 monorepo 필요; 독립 pyproject 복사 금지; package smoke 필수 |
| `deepagents_code/__init__.py` | logging setup와 lazy cli import 존재 | empty parent package로 runtime smoke 대체 금지 |
| `libs/code/EXTENSIONS.md`(앞선 확인) | experimental async extension; middleware/tools/backend/shutdown; slash command API 없음 | 가정한 신규 native CLI/extension 지원을 완료로 표시하지 않음 |
| 이전 agent.py source 검토 | Memory/Skills, children, cost observer, extension merge, `create_deep_agent` | WP06 native adapters 소유, runtime 테스트 전 자동 보장 없음 |

재조회 가능한 1차 출처:

- https://api.github.com/repos/langchain-ai/deepagents/branches/main
- https://github.com/langchain-ai/deepagents/blob/7f9e8ed3a555933902045792da9bb184950ee7b2/libs/code/DEVELOPMENT.md
- https://github.com/langchain-ai/deepagents/blob/7f9e8ed3a555933902045792da9bb184950ee7b2/libs/code/pyproject.toml
- https://github.com/langchain-ai/deepagents/blob/7f9e8ed3a555933902045792da9bb184950ee7b2/libs/code/deepagents_code/__init__.py
- https://github.com/langchain-ai/deepagents/blob/7f9e8ed3a555933902045792da9bb184950ee7b2/libs/code/EXTENSIONS.md

웹 일반 fetch와 컨테이너의 직접 다운로드는 이번 환경에서 실패했고, 연결된 GitHub 읽기는 성공했다. 따라서 최신 source 읽기와 전체 checkout 실행은 구분한다. 라이브 import·build·캐시·격리·provider 호출은 미검증이다. 기존 첨부 분석팩의 revision·줄 번호는 이 SHA에서 재검증하기 전 확정 근거로 사용하지 않는다.
