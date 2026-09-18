# 7. QualityRunner와 도구 어댑터

## 7.1 단일 진입점

개발 편의 CLI(구현 후 사용):

```text
udh quality inspect --workspace PATH
udh quality check --workspace PATH --mode local
udh quality fix --workspace PATH --changed-from APPROVED_SNAPSHOT
udh quality report --report-id ID
```

governed 서비스 요청은 workspace 문자열을 믿지 않고 authenticated session의 Workspace/Attempt를
조회한다. 모델에게 `--mode governed`, `--approve`, 임의 output 경로를 노출하지 않는다.
`check --mode local` 결과는 `verification_level=local_advisory`이며 완료 증거가 아니다.

`quality fix`는 편의 기능으로 원본을 수정할 수 있고, `quality check`는 source를 수정하지 않는다.
fix는 changed .py/.pyi만 대상으로 안전한 import 정렬(`ruff check --select I --fix`) 후 Black을
실행한다. 더 넓은 Ruff 안전 fix는 명시적 옵션/검토가 필요하다. 최종 gate는 --fix 없이 실행한다.

## 7.2 실행 단계

| check ID | 대상/입력 | 최대 시간 기본값 | 필수 여부 |
|---|---|---:|---|
| policy_guard | preimage/postimage/policy/permit | 30s | 항상 |
| inventory | source/config roots·.py/.pyi | 30s | 항상 |
| format | 승인된 Python 파일 전체 | 120s | Python 변경 |
| lint | 승인된 Python 검사 범위 전체 | 120s | Python 변경 |
| type | 승인된 src/test 범위 | 180s | Python 변경 |
| unit | work plan에 고정된 unit suite | 300s | 동작 변경/제품 코드 |
| integration | plan에 명시된 integration suite | 600s | 영향에 따라 |
| acceptance | acceptance IDs별 검증 recipe | 600s | plan 요구 |

시간은 제품 초기 기본값이며 저장소별 승인 정책으로 조절한다. 2초 서비스 조회 deadline과
600초 test timeout을 혼동하지 않는다. 전체 gate deadline도 별도로 두어 합계가 예산을 초과하지 않게 한다.
검사가 길어도 Hook 안에서 직접 전부 실행하지 않는다. synchronous verify tool/외부 runner가 담당한다.

## 7.3 argv 생성

이름을 PATH에서 찾지 않고 toolchain에 등록한 executable 절대 경로를 사용한다.
도구 executable/interpreter와 distribution version을 receipt에 기록한다.
trusted pyproject/config를 별도 policy directory에 렌더링하고 명시적으로 전달한다.

```text
BLACK:  <python> -I -m black --check --diff --config <trusted_pyproject> <paths...>
RUFF:   <ruff> check --output-format json --config <trusted_pyproject> <paths...>
MYPY:   <python> -I -m mypy --config-file <trusted_config> --output json <roots...>
PYRIGHT:<pyright> --project <trusted_pyright_config> --outputjson
PYTEST: <python> -m pytest -c <trusted_pytest_config> --junitxml=<runner_output> <suite...>
```

위 argv는 adapter 계약이다. 설치한 버전이 `--output json` 등을 지원하는지 capability probe로
확인한다. 미지원 버전의 텍스트를 임의 정규식으로 성공 처리하지 않는다. 공식 명령 지원 범위는
실제 pin과 fixture로 확정한다. [S02,S04,S05,S06]

Ruff의 명시적 config는 cwd/path 해석을 달리할 수 있으므로 `src`, per-file-ignores,
include/exclude를 봉인 root 기준 절대 경로 또는 검증된 상대 경로로 렌더링한다.
policy 원본 digest와 실제 실행용 렌더링 digest를 각각 기록한다.
Ruff CLI로 직접 전달한 파일과 exclusions의 관계도 test로 확인하고, 검사 대상 파일 누락을
inventory guard에서 차단한다. nested config를 실수로 추가 로드하지 않게 한다.

명령행 길이 한계를 넘으면 format/lint의 **명시적 파일 집합**만 batch한다. 모든 batch가 성공해야
check 성공이다. type/test를 임의 파일 batch로 나눠 import 의미나 test session을 바꾸지 않는다.
파일이 0개인데 Python 변경이 있으면 BLOCKED_EMPTY_SCOPE. Python과 무관한 문서만 바뀌면 계획
단계에서 Python check를 not applicable로 분류하며, 실행 실패와 구분한다.

## 7.4 subprocess 규약

`subprocess.Popen(argv, shell=False, cwd=sealed_root, env=approved_env, ...)`를 사용한다.
stdout/stderr를 동시에 drain해 deadlock을 막고, raw bytes를 streaming 저장/해시한다.
사용자 UI에는 초기 12개 진단과 제한된 excerpt를 전달하며, 전체 결과는 artifact reference로 접근한다.
프로세스 시간은 monotonic clock으로, event 시각은 timezone-aware UTC로 기록한다.

timeout에는 프로세스 그룹을 정상 종료하고 5초 grace 후 강제 종료한다. 살아남은 자식이 있으면
sandbox 전체를 종료한다. Windows Job Object 등의 equivalent가 검증되지 않으면 governed 지원을
차단한다. runner crash/연결 단절 때 lease가 만료되며 PASS는 발급되지 않는다.

최대 raw output은 stream당 10 MiB가 기본이다. 초과 시 제한적으로 보존한 뒤 실행을 중단하고
`ERROR_OUTPUT_LIMIT`을 기록한다. 파싱에 필요한 JSON을 잘라 놓고 진단 0개라며 성공시키지 않는다.
검증 JSON은 strict UTF-8로 읽으며 decode 오류는 ERROR다. 사람용 stderr excerpt만 replacement
문자를 사용할 수 있다. raw bytes digest와 redacted excerpt digest를 혼동하지 않는다.

## 7.5 도구 결과 해석

| 도구 | 정상 성공 | 코드 품질 실패 | 실행/설정 오류 |
|---|---|---|---|
| Black check | exit 0 | exit 1 | exit 123 또는 기타 비정상 |
| Ruff check | exit 0 + 유효한 빈 진단 | exit 1 + 유효 진단 | exit 2, 알 수 없는 code, invalid JSON |
| mypy | pin별 성공 code + 진단 계약 | pin별 type diagnostics | parser 불일치, 내부 오류, 지원 안 되는 CLI |
| Pyright | exit 0 + errorCount=0 | error diagnostics | 지원 안 되는 schema/version/비정상 실행 |
| pytest | exit 0 + 유효 수집/실행 증거 | exit 1/test failure | exit 2 interrupt, 3 internal, 4 usage, 5 no-tests |

pytest exit 5는 “테스트가 없으니 PASS”가 아니다. 테스트 변경 작업 또는 신규 제품 코드는
필수 suite가 비어 있으면 BLOCKED_NO_TESTS다. 사용자 취소로 인한 exit 2와 수집 중 중단은
controller cancellation 정보로 구분한다. 임의 KeyboardInterrupt를 사용자 취소로 위장하지 않는다. [S11]

JSON의 진단 개수·exit code가 모순이면 ERROR_TOOL_PROTOCOL. 성공 code만 믿지 않는다.
mypy JSON의 JSON-array/JSON-lines 형태는 실제 pinned version fixture로 고정한다.
단계가 실행되지 않았다면 exit_code=null이며, 실행된 exit_code=0으로 채우지 않는다.

## 7.6 테스트 결과 조건

기록할 필드: collected, executed, passed, failed, errors, skipped, xfailed, xpassed, deselected.
이들을 단순히 하나의 “pass 수”로 합치지 않는다. mandatory acceptance test가 skip/xfail이면
그 acceptance를 충족했다고 보지 않는다. 사전 승인된 플랫폼 not-applicable은 WorkPlan에 있어야 한다.

`pytest_collection_finish`/`pytest_runtest_logreport` 기반 고정 observer 또는 동일 수준의 runner
기록으로 node IDs와 phase 결과를 저장한다. JUnit은 원본 보조 증거다. collection 오류와 setup/
teardown 실패를 별도로 보존한다. `os._exit(0)`처럼 보고 파일 없이 종료하면 ERROR다.

candidate conftest와 plugin은 결과에 영향을 줄 수 있다. 코드 리뷰와 trusted acceptance suite를
분리하고 suite/config/plugin digest를 고정한다. observer JSON 하나가 악의적 Python 실행의
모든 의미를 검증한다는 주장을 하지 않는다.
