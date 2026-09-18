# 개발 실행

프로젝트 경로는 deepagents monorepo의 `libs/code`다. [runbook](execution/TEST_RUNBOOK.ko.md)에 따라 정확한 commit과 로컬 sibling 의존성을 확인하고 native toolchain을 고정한다. CYRANO 디렉터리 내부에서 옛 `uv sync`를 실행하지 않는다.

대부분의 순수 준비 검사는 `python cyrano/scripts/dev.py check`, 계약 검사는 `python cyrano/scripts/dev.py schemas`, 신규 평가자료 검사는 `python cyrano/scripts/assessment.py validate`로 수행한다. 실제 제품 tests·루프 연결·품질 도구는 WP/TS의 실제 설치와 구현 후에 실행한다.

상세 계획·리뷰·승인 절차는 [개발 실행계획](development/TEST_DEVELOPMENT_PLAN.ko.md)을 따른다. 코드·계약·문서 변경 후 `python cyrano/scripts/build_docs.py`로 통합본을 재생성한다.
