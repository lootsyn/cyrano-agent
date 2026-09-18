# CYRANO R3 · dcode source-native development kit

이 디렉터리는 `libs/code/cyrano/`이다. 실행 코드는 `../deepagents_code/cyrano/`, 현재 기반 테스트는 `../tests/unit_tests/cyrano/`, 실제 제품 테스트의 목표 위치는 `../tests/cyrano_product/`다. 이곳에는 별도 pyproject/uv workspace를 두지 않는다.

[시작](START_HERE.ko.md) · [개발 지시](IMPLEMENTATION_REQUEST.ko.md) · [설계·배치](docs/design/DCODE_INTEGRATION.ko.md) · [평가 전략](docs/testing/STRATEGY.ko.md) · [테스트 개발·실행](docs/development/TEST_DEVELOPMENT_PLAN.ko.md) · [실제 검사 기록](evidence/README.md)

15개 평가 기준의 정확한 배점은 3/3/4, 2/3/3/2, 2/3/3/2, 3/3/2/2로 총40점이다. 기존327·신규90·Python팩60 =477개 제품 수용 명세를 유지한다. 명세 숫자는 제품 실행 결과가 아니다. 공식 점수는 아직 `null`이다.

이 ZIP은 native dcode 프로젝트에 복사할 CYRANO 전체 추가분이다. upstream 소스·의존성은 포함하지 않는다. 배포 kit 루트의 `apply_overlay.py`를 사용해 검토한 commit의 monorepo checkout에 충돌 없이 적용한다. 실제 dcode 실행 연결·강제 보안·live 성능 평가는 WP/TS 작업이며 아직 제품 완료가 아니다.

`references/packs/`의 문서팩은 원본 참고자료로만 보존한다. 제품 권한과 모델 prompt에 자동 로딩하지 않는다. 오래된20항목 점수표는 기록용이며 현재15항목 rubric이 우선한다.
