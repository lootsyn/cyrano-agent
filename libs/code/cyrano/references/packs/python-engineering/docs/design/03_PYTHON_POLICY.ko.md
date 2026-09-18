# 3. Python 품질 정책

## 3.1 검사 범위별 책임

| 축 | 기본 도구/절차 | 성공이 의미하는 것 |
|---|---|---|
| 모양 | Black check | 선택한 Black 버전/설정과 포맷 일치 |
| 스타일·이름·일부 버그 | Ruff | 선택된 rule 범위의 진단 부재 또는 승인 baseline |
| 타입 | UDH: mypy strict / 대상 repo: 승인된 checker | 해당 분석 범위에서 타입 검사 통과 |
| 동작 | pytest unit/integration/acceptance | 수집·실행된 테스트의 기대 동작 충족 |
| 의미·유지보수 | 독립 code review | 요구사항·설계·예외 타당성에 대한 근거 있는 검토 |
| 무결성 | trusted guard + completion | 같은 입력·정책·승인에 근거한 판정 |

Black은 docstring 문장을 자동으로 모두 72자에 재배치하지 않으며, 모든 긴 문자열을
line-length 이하로 만들지도 않는다. 따라서 Black 성공과 E501/W505 위반은 함께 나올 수 있다.
문장을 의미 보존하면서 수동 분리하거나, 꼭 필요한 예외를 검토한다. [S01,S02,S03]

## 3.2 기본값

`team88-doc72`: code=88, doc=72. 팀 합의 profile임을 ADR에 기록한다.
`pep8-79-doc72`: code=79, doc=72. 프로파일 변경은 전체 포맷 영향과 baseline 재검토를 필요로 한다.
두 프로파일은 설정값만 다르며 모델 종류와 무관하다.

Ruff 규칙 초기 집합은 E, F, W, I, B, UP, N, RUF100과 선택된 D 규칙이다.
E/F/W/I만으로 함수명·클래스명·docstring을 충분히 검사한다고 설명하지 않는다.
N은 naming을 보완하고 D100/D101/D102/D103/D104/D205/D400은 public API 문서화를 보완한다.
모든 D 규칙을 한꺼번에 선택해 서로 충돌하는 문서 스타일을 강제하지 않는다.

`SIM`, complexity, security rule은 대상 repo의 승인 범위에 따라 후속 profile에 추가한다.
품질 규칙은 많을수록 무조건 좋다고 보지 않는다. compatibility 예외는 정확한 범위로 기록한다.

## 3.3 UDH용 설정 조각

아래는 기존 pyproject의 관련 table에 **merge할 설정**이다. `[project]`, workspace,
기존 dependencies를 통째로 덮어쓰지 않는다. 현재 `ignore=["E501"]` 제거는 별도 승인 migration이다.

```toml
[tool.black]
line-length = 88
target-version = ["py312"]

[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = [
  "E", "F", "W", "I", "B", "UP", "N", "RUF100",
  "D100", "D101", "D102", "D103", "D104", "D205", "D400"
]
# E203과 Black slice spacing의 충돌을 피하기 위한 고정 예외다.
# 비활성/preview 여부는 고정 Ruff 버전의 capability test로 확인한다.
ignore = ["E203"]

[tool.ruff.lint.pycodestyle]
max-doc-length = 72
ignore-overlong-task-comments = false

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["D100", "D101", "D102", "D103", "D104"]
"**/tests/**" = ["D100", "D101", "D102", "D103", "D104"]

[tool.mypy]
python_version = "3.12"
strict = true
namespace_packages = true
explicit_package_bases = true
show_error_codes = true
warn_unused_ignores = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers --strict-config"
markers = [
  "integration: isolated integration test",
  "live: explicit authorization and external credentials required"
]
```

`W505`는 선택만으로는 충분하지 않고 `max-doc-length=72`도 필요하다. Ruff에는 URL이나
한 단어 행 등 문서화된 예외가 있다. 따라서 “물리적 모든 줄이 예외 없이 72자”라고 주장하지 않는다.
이 예외가 허용되지 않는 별도 조직 규정은 별도 검사기를 추가하고 같은 이름의 PEP8 준수와 혼동하지 않는다. [S03]

`RUF100`은 불필요한 noqa를 찾지만, 필요한 noqa의 정책적 정당성까지 판단하지는 않는다.
`guard`가 신규 suppressions의 승인 여부를 검사해야 한다. pylint/mypy directive도 함께 조사한다.

## 3.4 타입 검사기 선택

UDH 자체: mypy strict를 유지한다. discovery가 workspace pyproject/build metadata에서 src roots를
모아 실제 존재하는 루트와 import namespace를 검증한다. 무조건 `mypy .`를 실행하지 않는다.
중복 모듈 이름을 피하도록 확인된 src roots를 사용하고, 실행에 필요한 dependency/stub은 lock한다.

대상 repo Pyright: `typeCheckingMode`는 기존 합의를 유지하되 신규 프로젝트 템플릿은 strict를
제안한다. 사용자가 standard를 사용하고 있으면 변경 계획 없이 strict로 바꾸지 않는다.
CLI `--outputjson`을 이용하고 version-pinned parser fixture를 가진다. [S06]

타입 힌트는 런타임 입력 유효성 검사를 대신하지 않는다. 외부 JSON/모델 tool 입력에는 별도의
구조 검증이 필요하다. 인터페이스를 숨기기 위한 Any 또는 cast 남용은 code review 대상이다.

## 3.5 dependency와 lock

실제 tool 버전은 기존 uv.lock을 존중하고, 승인된 도입 과정에서 필요한 dev 그룹을 추가한다.
문서에서 검증하지 않은 “최신 버전 번호”를 임의로 고정하지 않는다.

도입 명령은 `uv add --dev black ruff mypy pytest` 또는 이미 존재하는 dependency group의
정확한 수정이다. 기존 도구를 불필요하게 upgrade하지 않는다. lock 생성은 도입 작업에서 수행하고
평상시 검증은 `uv sync --locked --all-packages --group dev` 후 준비된 환경을 사용한다.
단일 패키지 repo는 `--all-packages`를 생략할 수 있다.

`--frozen`은 lock과 pyproject의 일치 검사를 생략하므로 stale lock 검증을 대체하지 않는다.
`uv run --locked`는 lock 변경을 거부하지만 환경을 sync할 수 있다. governed runner는 별도 준비
단계에서 환경을 고정한 뒤 절대 경로의 interpreter/tool을 호출해 검사 도중 설치하지 않는다. [S07]

설치·build backend·pytest는 코드를 실행하므로 sandbox 안에서 실행한다. lock pin은 dependency의
무해함이나 모든 OS에서 동일한 동작을 보증하지 않는다. toolchain에는 Python patch, OS/architecture,
uv version, package distributions, lock digest, sandbox image digest를 기록한다.
