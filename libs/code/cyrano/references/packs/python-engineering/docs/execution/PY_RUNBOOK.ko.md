# 도입 및 실행 Runbook

## A. 도입 전

기존 저장소와 사용자 변경을 보존한다. `git status --short`, HEAD, Python/uv/tool version을 기록한다.
read-only inspect에서 현재 pyproject/lock/tests/AGENTS/Skills를 확인한다. 기존 실패는 before evidence로
보존한다. 이 설계 kit를 제품 root에 통째로 덮어쓰지 않는다.

새 `packages/quality/gate`를 workspace 멤버로 만들고, apps/cli와 공용 contracts의 의존성을 명시한다.
기존 `[project]` 및 workspace를 유지한다. 정책 도입 때문에 lock update가 필요하면 승인된 작업에서만
수행하고 검사 단계에서는 `--locked`를 사용한다.

## B. 구현 중 로컬 검사

runner 구현 전에도 실제 설치된 도구로 아래 단계별 검사를 수행할 수 있다.
명령의 roots는 inspect 결과로 확정한다. 일반 repo에 UDH roots를 그대로 사용하지 않는다.

```text
uv sync --locked --all-packages --group dev
uv run --locked black --check packages apps tests
uv run --locked ruff check packages apps tests
uv run --locked mypy <검증된 workspace src roots>
uv run --locked pytest
```

`<검증된 workspace src roots>`는 그대로 shell에 넣는 문자열이 아니라 discovery가 제공할 값이다.
배포 runner는 이 값을 manifest에서 생성한다. root 예시보다 검사 inventory의 실제 coverage가 우선이다.
의존성/network 미비로 명령이 못 돌면 unavailable로 보고하고 PASS라고 하지 않는다.

## C. product CLI 구현 후

`udh quality inspect --workspace PATH`로 effective policy와 capabilities를 확인한다.
`udh quality check --workspace PATH --mode local`로 개발 피드백을 얻는다.
실제 governed 작업은 UDH launcher가 만든 Attempt에서 `quality_verify` tool을 호출한다.
`udh quality report --report-id ID`로 검사별 raw/effective 상태를 확인한다.
이 명령들은 이 문서의 구현 대상이며 kit 전달 시점에 존재한다고 가정하지 않는다.

## D. 매 작업

원요구/InterviewOutcome → 계획·review·permit → 변경 → focused feedback → safe format →
봉인 snapshot → 최종 gate → 실패 시 제한 복구 → code review → completion request.
단순 style 작업이라도 기존 동작이 깨지지 않는 테스트를 유지한다. 임의 global reformat 금지.

## E. 실패 상황별 운영

formatter FAIL: 변경 파일 format, diff 확인, final gate 재실행.
lint FAIL: rule 원인 수정. rule disable/noqa로 즉시 덮지 않는다.
type FAIL: 타입 경계/None 처리/정확한 stub 확인. Any로 숨기지 않는다.
pytest FAIL: 기능 회귀/fixture/environment 분류. 테스트 삭제 금지.
ERROR: toolchain/protocol/log 확인, 승인된 환경 복구. tool 내부 오류를 코드 탓으로 치환하지 않는다.
BLOCKED: 필요한 승인/credential/실행 환경/기존 실패를 명시하고 멈춘다.
STALE: candidate 변경 확인 후 새 snapshot을 봉인하고 다시 검사한다.
PASS_WITH_BASELINE: 완료 가능 policy인지 controller 확인, 보고서에서 남은 debt를 밝힌다.

## F. 배포와 rollback

지원 pin/환경에서 인수 테스트를 수행하고 actual CI required check 설정을 확인한다.
new Skill은 immutable release로 배포하고 다음 세션/attempt에만 적용한다.
회귀 시 release pointer를 이전 승인 bundle로 전환하며 원인·범위·증거를 보존한다.
이 단계는 사용자 승인/운영 권한이 없으면 실행하지 않는다.

## G. 사용자에게 보여줄 결과 형식

```text
작업 상태: COMPLETE / COMPLETE_BASELINED / BLOCKED / FAILED / CANCELLED
검증 수준: governed / local_advisory
대상 snapshot: 실제 digest
계획/정책/toolchain: 실제 digest 및 버전
검사: Black, Ruff, typing, tests 각 raw status
기존 부채: 0 또는 실제 baseline-covered count
새 위반: 실제 count 또는 unknown
독립 리뷰: review ID와 미해결 blocker
실행하지 못한 검사: 이름과 이유
증거: report ID 및 허가된 artifact 위치
```

검증 결과를 얻지 못했으면 digest/count를 예제 값으로 채워 제출하지 않는다.
