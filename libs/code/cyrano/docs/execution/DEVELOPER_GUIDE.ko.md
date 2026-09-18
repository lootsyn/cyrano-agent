# Cyrano Agent 개발 준비·실행 안내

문서 유형: 실행 진입점. 전체 준비·실행 절차는 [개발 수행 가이드](R5_EXECUTION_GUIDE.ko.md)가 소유한다. 개발할 cwd는 deepagents monorepo의 `libs/code`다.

Base 소스와 Cyrano 영역의 상세 경계는 [dcode 통합 설계](../design/DCODE_INTEGRATION.ko.md), 요구·계획·리뷰·승인 로직은 [개발 workflow 설계](../design/features/2026-09-16-plan-memory-execution.ko.md), 작업 의존성과 구현 책임은 [개발계획](../development/R5_MASTER_PLAN.ko.md)을 따른다.

```bash
python cyrano/scripts/doc_route.py --task WP00 --stage plan --content
```

기반 코드·schema·포장 검사는 제품 완성/보안/실제 개선 성능을 보장하지 않는다.
