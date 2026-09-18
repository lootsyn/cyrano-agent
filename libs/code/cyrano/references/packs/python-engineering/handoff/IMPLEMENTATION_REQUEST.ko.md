# 하위 구현 모델 전달 요청문

이 패키지의 `UDH_PYTHON_ENGINEERING_FULL_DESIGN.ko.md`와
`docs/development/PY_IMPLEMENTATION_PLAN.ko.md`를 기준으로 Python Engineering Quality Harness를
기존 UDH/dcode workspace에 구현하라. 문서 제안으로 끝내지 말고, 허가된 작업 범위 안에서 코드·테스트·
실제 실행 증거를 만들라. 현재 문서 kit에 있는 reference contract 검증을 제품 완성으로 오인하지 마라.

먼저 현재 repository/branch/dirty state와 실제 Python/uv/tool versions를 읽어 기록하라.
사용자가 지정하지 않은 reset/checkout/clean, 전체 pyproject 교체, 전체 reformat, commit/push를 하지 마라.
기존 Python 3.12 workspace/Black/mypy 설정을 유지하고 이 명세의 추가 정책을 ADR로 통합하라.
다른 대상 프로젝트의 Python 3.11/Pyright 설정을 UDH 제품 설정과 섞지 마라.

W01부터 순서대로 진행하되 매 WorkUnit을 시작하기 전에 요구/수정 범위/test obligations가 있는
계획과 실제 독립 plan review를 남겨라. requirement_ids/acceptance_ids/Attempt를 기존 계약에 연결하라.
각 작업의 실패/예외/환경 부족을 숨기지 말고 next dependency와 분리해서 보고하라.

필수 구현 원칙:
- Skill은 절차, pyproject는 tool policy, controller는 승인·완료 권한이다.
- quality check는 source를 바꾸지 않는다. fix와 verify를 분리하라.
- toolchain/version/정책/테스트/snapshot을 모두 묶은 receipt를 만들라.
- 임의 subprocess 문자열, LLM 생성 PASS JSON, 다른 attempt의 보고서로 완료할 수 없게 하라.
- legacy의 raw 실패를 숨기지 말고 PASS_WITH_BASELINE을 분리하라.
- missing/skipped/no-tests/error/timeout/stale를 PASS로 바꾸지 마라.
- Hook timeout이나 미설치에도 외부 completion gate가 남아 있어야 한다.
- 실제 dcode가 지원하지 않는 frontmatter/hook API를 만들지 마라.
- review prompt만으로 OS read-only 권한이 생겼다고 가정하지 마라.
- Self-improvement는 evidence→proposal→실제 평가→승인→immutable release만 허용하라.

구현 후 13장 PY-T01..PY-T60을 테스트 manifest로 작성하고, 실행한 범위/미실행 사유를 표시하라.
실제 모델 credential·CI 관리권한·sandbox가 없으면 관련 항목을 BLOCKED로 남겨라.
제품 구현을 대신하는 mock 결과를 actual E2E로 보고하지 마라.

최종 보고에는 수정 파일 목록, 실행한 명령/exit code, 실제 tests, 증거 경로,
완료/미완료 WorkUnit, 운영 권한 blocker를 포함하라. PASS를 위해 lint/type/test 규칙을 약화하지 마라.
