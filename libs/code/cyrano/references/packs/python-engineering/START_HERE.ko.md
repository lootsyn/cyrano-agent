# UDH Python Engineering Quality Harness 상세설계 Kit

**하위 구현 모델용 · dcode 기반 · PEP8 스타일 + 실행 가능한 품질 gate**

작성 기준일: 2026-09-16 / 문서 버전: 1.0.0-design.

한 파일로 읽으려면 `UDH_PYTHON_ENGINEERING_FULL_DESIGN.ko.md`를 시작점으로 사용한다.
실제 구현은 `docs/development/PY_IMPLEMENTATION_PLAN.ko.md`의 W01..W12 순서로 진행한다.
다른 모델에 전달할 요청문은 `handoff/IMPLEMENTATION_REQUEST.ko.md`다.

## 포함 내용

`docs/design/`: 구조·정책·Skill·계획·snapshot·runner·계약·baseline·dcode·CI·자기개선·60개 인수 조건.
`templates/`: AGENTS/Skill/reviewer, Python tool 설정 조각, dcode profile 설정 조각, CI 실행 계약.
`contracts/`: Pydantic 참조 계약과 JSON Schemas. 인증/프로세스 실행 구현은 포함하지 않는다.
`fixtures/`: synthetic positive/negative 사례. 실제 제품 검증 evidence가 아니다.
`tests/`와 `scripts/validate_kit.py`: 이 설계 kit의 참조 계약/설정 검사.
`evidence/`: 이번 환경에서 실행한 kit 검사의 실제 결과와 미실행 범위.

## 중요한 적용 경계

이 패키지는 **상세 설계 + 구현 기준 + 일부 실행 가능한 참조 계약**이다.
완성된 native dcode extension, governed runner, CI 설치 패키지 또는 사용자 저장소의 수정본이 아니다.
`udh quality ...`, QualityService, quality_verify tool은 새로 구현할 인터페이스다.
CI contract YAML은 실제 GitHub workflow가 아니다. 승인된 runner/actions pins와 repo 설정은
PY-W11에서 실제 구현·검증한다.

UDH의 기존 Python3.12/uv workspace/Black88/mypy strict를 기준으로 통합한다.
대상 repo가 Python3.11/Pyright이면 별도 policy를 사용하고, 기존 설정을 자동 교체하지 않는다.
원격 저장소의 commit/push나 사용자 전역 dcode 설정 변경은 수행하지 않았다.

## 검증 명령

Python 3.12+와 pydantic v2, jsonschema가 있는 환경에서:

```bash
python scripts/validate_kit.py
```

필요 dependency의 이번 검사 버전은 `requirements-validation.txt`와
`evidence/kit-validation.json`에 있다. production toolchain lock이 아니다.
PyPI 접근 실패로 실제 Black/Ruff/mypy/Pyright CLI와 dcode E2E는 실행하지 못했다.
따라서 보고된 PASS는 **설계 kit 참조 검사** 범위만 의미한다.

## 전달 순서

START_HERE → FULL_DESIGN → IMPLEMENTATION_PLAN → IMPLEMENTATION_REQUEST.
구현 모델은 실제 저장소를 읽고 W01 계획 리뷰부터 시작해야 한다. template들을 기존 프로젝트 root에
통째로 덮어쓰지 않는다. 파일 manifest는 `MANIFEST.sha256`에 있다.
