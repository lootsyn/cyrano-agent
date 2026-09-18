# 14. 출처, 검증 범위, 인계 주의사항

## 14.1 공식 기술 출처

다음은 2026-09-16 조회한 공식 문서다. 특정 설치 버전의 실제 동작은 toolchain pin과 capability
테스트로 재확인한다. main/stable 웹 문서를 그 자체로 사용자 설치 버전이라고 간주하지 않는다.
외부 제품의 공식 사실은 아래 출처에 근거하며, UDH 인터페이스/기본값/상태 전이는 이 문서의 설계 결정이다.

| ID | 출처 | 사용 범위 |
|---|---|---|
| S01 | https://peps.python.org/pep-0008/ | 79/72, 팀 합의, naming, 프로젝트 관례 |
| S02 | https://black.readthedocs.io/en/stable/usage_and_configuration/the_basics.html | --check, --diff, exit codes, 설정 |
| S03 | https://docs.astral.sh/ruff/rules/doc-line-too-long/ | W505, max-doc-length, 예외 |
| S04 | https://docs.astral.sh/ruff/linter/ | Ruff fixes, output/exit 의미 |
| S05 | https://mypy.readthedocs.io/en/stable/command_line.html | JSON output, config, strict/CLI 버전 주의 |
| S06 | https://github.com/microsoft/pyright/blob/main/docs/command-line.md | Pyright CLI의 JSON output |
| S07 | https://docs.astral.sh/uv/concepts/projects/sync/ | locked/frozen/sync 차이 |
| S08 | https://docs.langchain.com/oss/deepagents/code/configuration | AGENTS/Skills 경로와 우선순위, auto memory/update |
| S09 | https://docs.langchain.com/oss/python/deepagents/skills | progressive disclosure와 보조 자료 |
| S10 | https://docs.langchain.com/oss/deepagents/code/subagents | 파일 기반 subagent의 도구 상속 한계 |
| S11 | https://docs.pytest.org/en/stable/reference/exit-codes.html | 0..5 종료 상태 |
| S12 | https://docs.pytest.org/en/stable/how-to/plugins.html | plugin 로딩 통제와 conftest |
| S13 | https://docs.langchain.com/oss/deepagents/code/hooks | Stop/PreToolUse/timeout/exit 처리 |
| S14 | https://docs.langchain.com/oss/deepagents/code/extensions | experimental ExtensionAPI |
| S15 | https://docs.github.com/en/actions/reference/security/secure-use | 최소 권한, untrusted code, immutable action pin |
| S16 | https://docs.astral.sh/ruff/rules/line-too-long/ | E501과 pragmatism 예외 |
| S17 | https://docs.astral.sh/ruff/configuration/ | 설정 탐색과 명시적 config |

## 14.2 사용자의 기존 설계 연결

U01: `UDH_Project_FULL_DESIGN.ko.md` — Python >=3.12 workspace, Black 88, mypy strict,
`packages/*/*`, 제품/개발 agent 구분, Attempt/snapshot/digest, 기존 구현과 준비 단계의 구분.
Library 검색과 관련 설정/실행 단위 섹션을 확인했다. 실제 원격 repository HEAD는 이 작업에서 수정·검증하지 않았다.

U02: `UDH_DREAM_FULL_DESIGN.ko.md` — 경로 A/B 분리, 경로 B의 실제 재실행 평가,
승인·불변 release·회귀·rollback.

U03: `UDH_FULL_DESIGN.ko.md` — 앞선 79/72 기준, formatter와 PEP8 전체 검증의 차이,
기존 프로젝트 규칙 존중. 후속 프로젝트 설정과 상충하는 값은 1장의 ADR로 명시적으로 조정한다.

이 패키지에 기존 전체 설계 원문을 복사하지 않았다. 이 문서는 Python quality 추가 명세다.
기존 파일과 동일 이름을 가진 source tree를 덮어쓰지 않는다.

## 14.3 이번 패키지의 실제 검증

`python scripts/validate_kit.py`는 reference contract/unit tests, JSON Schema의 문법,
positive fixture, TOML parse, Python AST parse, Skill 구조·설정 일치만 검사한다.
실행 결과는 `evidence/kit-validation.json`과 원본 unittest 로그에서 확인한다.
이 검사는 사용자 저장소의 Python 품질 gate, dcode integration, CI 또는 실제 LLM 실험이 아니다.

새 validation 환경에서 Black/Ruff/mypy 등 도구 설치를 시도했으나 실행 환경의 PyPI DNS 접근이
실패해 해당 CLI들을 실제로 실행하지 못했다. 그러므로 tool 설정은 공식 문서를 근거로 한 template이며
설치 pin에 대한 actual CLI compatibility 검사는 PY-W05/W06에서 수행해야 한다.
참조 계약 검사는 실행 환경에 이미 있는 pydantic/jsonschema로 수행한다.

테스트 fixture의 digest/ID는 명시적인 synthetic 값이며 실제 실행 receipt가 아니다.
`verification_level="governed"`가 있는 fixture도 schema 사례일 뿐 governed 권한이 없다.
Python 3.13에서 이 패키지의 참조 코드를 검사했다고 해서 제품 목표 Python 3.12의 native integration이
검증되었다고 주장하지 않는다. 모든 acceptance 조건의 actual 상태는 구현 후 별도로 기록한다.
