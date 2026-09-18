# 13. 인수 테스트 명세

아래 테스트는 개발 계획의 필수 완료 기준이다. fixture/schema 통과와 제품 E2E 통과를 구분한다.
각 테스트는 before input, 실행, 기대 verdict/상태/증거를 assert해야 한다.

| ID | 입력/상황 | 기대 결과 |
|---|---|---|
| PY-T01 | 스페이스/빈 줄이 잘못된 .py | Black raw FAIL; format 후 재검사 필요 |
| PY-T02 | unused import | Ruff F401; 새 위반이면 FAIL |
| PY-T03 | 긴 문장 docstring | W505 발생; max-doc-length 누락 시 config contract FAIL |
| PY-T04 | 함수 badName, 클래스 bad_class | 선택한 N 규칙 진단 |
| PY-T05 | public 함수 docstring 없음 | 선택한 D 규칙 진단 |
| PY-T06 | mutable default list | B006; 자동 ignore 대신 수정 |
| PY-T07 | strict type mismatch | mypy/Pyright raw FAIL |
| PY-T08 | 실제 회귀 | pytest raw FAIL, COMPLETE 거부 |
| PY-T09 | 테스트 0개 | BLOCKED_NO_TESTS; exit 5를 성공으로 보지 않음 |
| PY-T10 | 모든 필수 acceptance skip | acceptance 미충족; COMPLETE 거부 |
| PY-T11 | mandatory setup/teardown 오류 | FAIL/ERROR를 보존, passed 수로 덮지 않음 |
| PY-T12 | Black/Ruff format 반복 | 안전 fix→Black을 두 번 실행한 diff가 동일 |
| PY-T13 | `.pyi`만 수정 | inventory 포함, type/lint 정책 적용 |
| PY-T14 | `.gitignore`로 변경 Python 숨김 | guard/inventory 실패 |
| PY-T15 | source_root 빈 디렉터리 | Python 작업인데 empty scope이면 BLOCKED |
| PY-T16 | symlink/../absolute path 탈출 | 실행 전 PATH_POLICY_VIOLATION |
| PY-T17 | 공백·한글·개행 파일명 | 지원 계약대로 정확히 처리하거나 명시적 blocker; 누락 PASS 금지 |
| PY-T18 | quality check 실행 중 source 변경 | STALE 또는 immutable snapshot 영향 없음; 현재 후보 완료 거부 |
| PY-T19 | 성공 후 source/test/resource 한 byte 수정 | 과거 receipt 재사용 거부 |
| PY-T20 | 같은 HEAD, dirty 내용만 변경 | 다른 snapshot digest |
| PY-T21 | 같은 파일 bytes, 다른 수정 시각 | 동일 snapshot 콘텐츠 digest |
| PY-T22 | rule disable, noqa/type-ignore 추가 | permit 없으면 POLICY_VIOLATION |
| PY-T23 | 문자열 내부의 '# noqa' 예제 | suppression으로 오탐하지 않음 |
| PY-T24 | 승인된 정확한 suppression | permit 범위/expiry 검사 후 허용 |
| PY-T25 | 만료 또는 광범위 예외 | 거부 |
| PY-T26 | 임의 generated PASS JSON | trusted report store 등록/완료 불가 |
| PY-T27 | local_advisory report를 governed로 제출 | trust validation 거부 |
| PY-T28 | 다른 attempt의 정상 PASS report | identity mismatch 거부 |
| PY-T29 | 필수 lint 결과 누락/중복 | BLOCKED 또는 contract error |
| PY-T30 | command exit 0 + malformed JSON | ERROR_TOOL_PROTOCOL |
| PY-T31 | Ruff exit 2 / Black exit 123 | 코드 위반이 아닌 tool ERROR |
| PY-T32 | timeout + 자식 프로세스 | process group/sandbox 정리, PASS 없음 |
| PY-T33 | stdout/stderr output cap 초과 | ERROR_OUTPUT_LIMIT; 잘린 JSON PASS 금지 |
| PY-T34 | verifier crash/lease 만료 | ERROR_RUNNER_LOST; 재개 시 허위 완료 없음 |
| PY-T35 | 동일 idempotency key/동일 payload | 동일 report 반환, 중복 완료 없음 |
| PY-T36 | 동일 key/다른 payload | CONFLICT |
| PY-T37 | 완료 transaction 중 workspace revision 변경 | CAS 거부, 성공 event 없음 |
| PY-T38 | baseline 진단 3개가 그대로, 파일 동일 | PASS_WITH_BASELINE, raw FAIL 보존 |
| PY-T39 | before 3개 제거하고 새 3개 | count 같아도 new violation FAIL |
| PY-T40 | baseline 파일에 한 줄 삽입 | changed file clean 규칙; 자동 baseline matching 금지 |
| PY-T41 | tool version/config 변경 후 baseline 재사용 | STALE_BASELINE |
| PY-T42 | 다른 파일 수정으로 미수정 파일 새 type error | 전체 type 검사로 회귀 검출 |
| PY-T43 | 기존 실패 테스트를 baseline에 넣음 | 지원하지 않음, BLOCKED |
| PY-T44 | 동일 오류 수정 3회, 정체 2회 | 예산/정체 규칙대로 중단 |
| PY-T45 | user cancel | children 종료, CANCELLED, 대화 종료 허용 |
| PY-T46 | no implementation, assistant says '완료' | COMPLETE 전이 없음 |
| PY-T47 | Stop Hook timeout/미설치/재작업 상한 | native 종료 가능, UDH COMPLETE는 불가 |
| PY-T48 | subagent prompt만 read-only | governed capability 미충족으로 탐지 |
| PY-T49 | Skill 중복 경로/본문 변경 | 실제 resolved path/digest 기록, release 혼합 금지 |
| PY-T50 | resume 후 다른 policy release | 기존 attempt pin 유지 또는 명시적 재시작 |
| PY-T51 | candidate가 gate.py를 always-0으로 변경 | trusted runner/guard가 차단 |
| PY-T52 | CI 필수 job skipped/cancelled | 최종 aggregate 실패 |
| PY-T53 | dependency install 중 lock 변경 필요 | --locked 실패; lock 자동 재작성 없음 |
| PY-T54 | PYTEST_ADDOPTS 또는 plugin 환경 주입 | sanitize/allowlist로 scope 우회 불가 |
| PY-T55 | 동작이 바뀐 Skill을 replay 점수만으로 승격 | 경로 B 규칙으로 거부 |
| PY-T56 | holdout family가 학습 데이터와 겹침 | 평가 manifest 검사 실패 |
| PY-T57 | 유료 평가 budget 0 | 실제 provider 호출 없음 |
| PY-T58 | lint 개선 but acceptance regression | 승격 거부 |
| PY-T59 | cache usage가 제공되지 않음 | null/unknown, 0%나 hit로 위조하지 않음 |
| PY-T60 | 새 policy/Skill 배포 후 회귀 | 이전 immutable release로 rollback, 기존 evidence 유지 |

## 13.1 테스트 분류

unit: policy resolver, path validator, digest, parser, reducer, baseline matcher, budget transition.
integration: real subprocess, filesystem permissions, mock controller, sqlite transactions, CLI.
contract: 실제 pin의 도구 출력 fixture, dcode extension/Hook/tool contract.
acceptance: 위 60개 중 코드 실행/상태 전이를 포함한 end-to-end 시나리오.
live: 실제 모델+native dcode 상호작용. 명시적 인증·비용 승인 후 별도 수행한다.

## 13.2 필수 negative tests 원칙

성공 사례 하나만 확인한 기능을 완료로 처리하지 않는다. parser/완료 서비스/보호 정책은 정상·누락·
잘못된 값·순서 변경·재전송·오류·취소 각각을 검사한다. 임의 bool true가 approval로 바뀌지 않아야 한다.
fixture의 expected 결과는 구현 코드로 자동 계산해서 덮어쓰지 않는다. 독립 기대값을 유지한다.

실제 tool output fixture에는 tool version과 실행 argv digest를 함께 둔다. 이번 문서 패키지의
synthetic reference fixture를 실제 Black/Ruff/dcode 실행 증거로 사용하지 않는다.
