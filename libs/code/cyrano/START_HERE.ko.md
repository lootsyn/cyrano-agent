# Cyrano Agent · 프로젝트 시작

프로젝트 표시명은 **Cyrano Agent**다. dcode base를 유지하고 우리가 개발할 제품 코드를 `../deepagents_code/cyrano/`에 둔다. 이 폴더는 설계·개발·실행·참고 문서를 관리한다.

처음에는 [개발 수행 가이드](docs/execution/DEVELOPER_GUIDE.ko.md)를 읽는다. 문서 유형별 [목차](docs/INDEX.ko.md), 작은 [길잡이](docs/NAVIGATION.ko.md), [구현 지시](IMPLEMENTATION_REQUEST.ko.md)를 제공한다.

평가 3·4의 원본은 [Memory](docs/design/MEMORY_LIFECYCLE.ko.md), [개선](docs/design/SELF_IMPROVEMENT_LIFECYCLE.ko.md), [관측](docs/design/OBSERVABILITY_PIPELINE.ko.md)다. 제품 runtime은 아직 연결/검증할 작업이 남아 있다. `evidence`에 있는 준비 검사와 40점 제품 평가를 혼동하지 않는다.

## R5 마지막 준비 검토

[R5 개발 수행 가이드](docs/execution/R5_EXECUTION_GUIDE.ko.md), [개발계획](docs/development/R5_MASTER_PLAN.ko.md), [검토 결과](docs/development/R5_REVIEW.ko.md)를 확인한다. RF00–RF11은 기존 WP·TS·RC를 보완한다. `python cyrano/scripts/check_r5.py`는 준비 검사이며 native/효과 통과를 뜻하지 않는다.
