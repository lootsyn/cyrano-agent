# 6. 스냅샷, 정책 보호, 실행 경계

## 6.1 SourceSnapshot

HEAD, `git diff` 문자열, 파일 수정 시각만으로 검증 identity를 만들지 않는다.
SourceSnapshot은 tracked 파일 및 허가된 untracked 입력 파일의 실제 바이트를 봉인한다.
일반 Python 파일 외에 `.pyi`, 테스트 fixture, 설정, import 시 읽는 데이터, build metadata도 포함한다.

각 entry: `path`, `kind=regular`, `size_bytes`, `raw_sha256`, `executable`.
경로는 repository-relative POSIX 문자열이며 절대 경로, `..`, NUL, 중복 경로를 거부한다.
대소문자 충돌, Unicode 정규화 충돌은 대상 OS에서 모호할 경우 차단한다.
v1 snapshot 입력에서 symlink, special file, git submodule은 명시적 support 계약 없으면 차단한다.
디렉터리 정규화를 통해 실제 root 밖으로 나가는 경로도 거부한다.

`git ls-files -z --cached`와 허가된 untracked inventory로 후보 집합을 얻되, Git 필터와 hooks를
실행하지 않는 read-only git 호출만 사용한다. 구현에서 `shell=True`를 쓰지 않는다.
공백/개행이 있는 파일명 처리는 NUL 구분으로 수행한다. 지원하지 않는 비 UTF-8 경로는 조용히
누락하지 않고 `UNSUPPORTED_PATH_ENCODING`을 반환한다.

`.git`, `.venv`, 고정 cache/output 폴더는 승인된 exclusion manifest에 둔다. `.gitignore` 변경으로
`.py` 파일을 숨길 수 없게 전체 diff/inventory와 비교한다. `.env`, credentials, private key는
기본 제외하고 **비밀 자체의 hash도 공개하지 않으며** 제외 사유만 기록한다. 제외된 비밀 파일을
필수 테스트가 필요로 하면 fixture 주입 또는 명시적 live-test 승인으로 해결한다. 누락된 채 PASS 금지.

snapshot manifest digest:
`SHA256(UTF8(canonical_json({schema_version, entries, exclusions})))`.
정렬 키는 path의 UTF-8 byte 순서다. source raw bytes는 줄바꿈/Unicode를 정규화하지 않는다.
canonical JSON은 key 정렬, separators=(',', ':'), ensure_ascii=False, NaN/Infinity 금지,
숫자는 이 계약에서 정수만 허용한다. 로컬 경로·생성시각·run ID는 콘텐츠 digest에서 제외한다.
동일 바이트를 다른 세션에서 조회해도 콘텐츠 digest가 같도록 한다.

## 6.2 스냅샷 생성 알고리즘

1. controller가 candidate write lease를 잠근다. implementer tool dispatch를 멈춘다.
2. agent와 그 자식 프로세스의 종료/일시정지 여부를 backend로 확인한다.
3. inventory를 읽고 경로·크기·허가 scope를 검사한다.
4. 각 파일을 private staging directory에 복사하며 streaming SHA-256을 계산한다.
5. 원본을 다시 검사해 읽는 중 변경 여부를 탐지한다. 변경 시 재시도 없이 STALE 처리한다.
6. manifest를 생성하고 sealed snapshot ID를 발급한다.
7. 검사 sandbox에는 봉인 복사본을 read-only mount한다. tmp/cache/output은 별도 경로다.
8. Python bytecode는 `PYTHONDONTWRITEBYTECODE=1` 또는 별도 cache 경로로 보낸다.
9. writable source를 전제하는 테스트는 승인된 별도 scratch copy를 사용하고, 원본 검증 대상과
   테스트 산출물을 구분한다. snapshot 원본 쓰기 요구를 자동 허용하지 않는다.

두 번 hash를 계산하는 것만으로 동일 UID의 악의적 프로세스와의 TOCTOU를 해결했다고 주장하지 않는다.
governed 보증에는 write lease, 프로세스/파일시스템 격리, immutable 검사 입력이 모두 필요하다.
후보 workspace가 다른 곳에서 변경될 수 있어도 완료는 정확한 snapshot에만 귀속시킨다.
현재 workspace의 최신 상태 완료를 표시하려면 그 workspace revision까지 CAS로 일치시킨다.

## 6.3 보호 대상

보호 대상에는 policy와 pyproject 도구 섹션뿐 아니라 다음이 포함된다.
`uv.lock`, `.python-version`, nested ruff/mypy/pyright/pytest config, `.gitignore`,
`conftest.py`, pytest plugin 목록, CI workflow, gate source, acceptance suite,
AGENTS/Skill 활성 release, exceptions/baseline, formatter/linter suppressions.

보호 대상 수정이 항상 금지되는 것은 아니다. 일반 코딩 작업의 scope로는 수정할 수 없고,
명시적인 policy/test-infrastructure/dependency 변경 작업과 추가 review/permit이 필요하다.
테스트를 보강하는 일반 변경과 test를 무력화하는 변경을 구분한다. assertion의 의미를
정규식 하나로 판정하지 않는다. 정적 guard는 위험 신호를 생성하고 독립 review와 보호된
acceptance 테스트가 보완한다.

`# noqa`, `# type: ignore`, `# pyright: ignore`, `# mypy: ignore-errors`, `# fmt: off`,
`# fmt: skip`, `# isort: skip_file`, pytest skip/xfail/collection 변경을 조사한다.
Python tokenize로 COMMENT 토큰을 읽고 AST로 decorator/call/config 영향을 검사한다.
문자열 안의 `# noqa` 예시는 suppression으로 취급하지 않는다. 토큰 파싱 실패는 syntax 실패로 전달한다.

승인된 suppression은 정확한 rule/파일/기호 또는 source anchor/reason/owner/expiry/permit을 가져야 한다.
`# noqa`처럼 규칙 없는 새 blanket suppression은 기본 거부한다. 만료/과도한 glob 예외는 거부한다.
`# noqa: E501`이 정당한 URL 예외인지 여부도 근거가 필요하다. 동적 타입 경계의 Any 자체는
불법이 아니며, 타입 검사를 우회하려는 변경인지 구분한다.

## 6.4 trusted 실행 경계

controller의 runner code, toolchain interpreter, verdict store, approval credential은 candidate에
쓰기 가능하게 mount하지 않는다. candidate 코드 실행 프로세스는 이 영역에 접근하지 못한다.
로컬 wrapper를 변경하거나 가짜 `quality-report.json`을 써도 trusted report 등록이 되지 않는다.

명령 문자열을 모델에게 받아 실행하지 않는다. 모델 tool은 `quality_verify(attempt_id)` 정도의
제한된 요청만 제공한다. controller는 attempt에 묶인 정책에서 check IDs와 argv를 생성한다.
로그 안의 “이 명령을 실행하라”는 외부 입력이며 자동 실행 지시로 취급하지 않는다.

환경은 allowlist로 구성한다. 임의 PATH, PYTHONPATH, PYTEST_ADDOPTS, MYPYPATH,
PYTEST_PLUGINS, LD_PRELOAD, DYLD_*를 그대로 상속하지 않는다. 승인된 값은 toolchain recipe가
생성한다. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`과 승인된 `-p` plugin을 사용하되,
conftest 자체는 여전히 실행될 수 있음을 인지한다. 이를 보안 sandbox 대신 사용하지 않는다. [S12]

테스트 코드는 임의 Python 실행이다. 네트워크·서비스 credential·GitHub write token 없이
격리한다. 외부 서비스가 필요한 테스트는 live recipe/명시적 승인/제한된 credential로 별도 실행한다.
code quality gate 통과는 공급망·보안 완전성 또는 프로그램의 수학적 정확성 증명이 아니다.
