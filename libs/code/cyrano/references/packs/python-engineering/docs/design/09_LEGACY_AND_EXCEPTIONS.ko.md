# 9. Legacy baseline과 예외

## 9.1 단순 count 비교 금지

before F401 10개, after F401 10개여도 기존 10개를 없애고 다른 위치에 10개가 생겼다면 회귀다.
총량만으로 “새 위반 0”이라고 할 수 없다. 본 버전은 정확한 진단 multiset과 원본 파일 digest로 비교한다.

신규 프로젝트(clean): 전체 mandatory 검사 위반 0. baseline 없음.
기존 프로젝트(legacy): 전체 원본 진단은 보존하고, **변경 파일은 전체 파일 clean**, 변경하지 않은
파일에 대해서만 사전에 승인된 동일 진단을 허용한다. 변경 라인만 검사해서 같은 파일의 숨은 영향을
놓치는 방식을 기본으로 하지 않는다.

legacy 파일 전체 정리가 범위를 너무 키우면 그 사실을 plan review에서 명시하고 작업을 분리하거나
정확한 예외를 사람 승인받는다. model이 “기존 오류”라고 선언해서 자동 면제받을 수 없다.

## 9.2 baseline 생성

1. 승인된 base snapshot과 현재 toolchain/policy/suite를 고정한다.
2. full lint/type/format 진단을 수집한다. 파서/환경 오류를 debt로 넣지 않는다.
3. 각 진단에 아래 fingerprint와 multiplicity를 기록한다.
4. baseline의 scope, 만료/재검토 시점, owner, 생성 report를 별도 리뷰한다.
5. controller가 BaselinePermit을 발급하고 immutable baseline digest를 등록한다.

`fingerprint = SHA256(canonical_json({tool, tool_version, rule, repo_path,
source_file_digest, start_line, start_col, end_line, end_col, normalized_message}))`.
normalized_message는 root absolute path를 `<workspace>`로 치환하는 등 명세된 최소 normalization만 한다.
변수명, 타입명, 숫자, 오류의 구별에 중요한 문구를 지우지 않는다. source_file_digest를 포함하므로
행 삽입/삭제가 있는 파일은 동일 진단이어도 v1 baseline 대상이 아니다.

진단은 set이 아니라 multiset이다. identical fingerprint가 두 개면 multiplicity=2로 유지한다.
policy/toolchain이 달라지면 baseline은 STALE이며 별도 migration 작업으로 재생성·승인해야 한다.

## 9.3 비교 알고리즘

- postimage 전체 검사 결과를 먼저 확보한다.
- baseline/after의 policy, toolchain, diagnostic schema가 같은지 검증한다.
- 변경되지 않은 파일의 exact fingerprint만 baseline multiplicity 내에서 차감한다.
- 남은 진단은 new violations다. 검사되지 않은 범위는 unchanged가 아니라 unknown이다.
- 변경 파일의 baseline-covered 수는 반드시 0이다.
- 결과에 raw_total, covered_total, new_total, fixed_total, comparison_digest를 기록한다.
- new_total>0이면 FAIL. covered_total>0만 남으면 PASS_WITH_BASELINE.

위 count는 정확한 매칭 이후의 요약이다. count 자체를 매칭의 증거로 사용하지 않는다.
BaselineComparison이 FAIL/ERROR이면 모델은 이를 성공으로 바꿀 수 없다.

## 9.4 도구별 제한

Ruff: 규칙/범위/메시지/파일 digest exact matching.
mypy/Pyright: 전체 승인 분석 범위를 실행한다. 수정 파일의 영향으로 미수정 파일에 새 타입 오류가
생기면 새 진단으로 FAIL한다. parse format 또는 tool 버전이 다르면 자동 이월 금지.
Black: legacy에서 파일별 check 결과와 원본 digest 및 고정 formatter/config를 기록한다.
미수정 파일의 승인된 포맷 부채만 허용한다. 파일 mapping을 못 얻는 adapter면 legacy format 지원을
표시하지 않고 BLOCKED_UNSUPPORTED_BASELINE으로 처리한다.
pytest: **v1에서는 실패 테스트 baseline을 허용하지 않는다.** 기존 필수 테스트가 실패하면
BLOCKED_EXISTING_TEST_FAILURE로 구분하고 수정 또는 별도 격리 정책을 승인받는다.
테스트 삭제/skip으로 문제를 숨기지 않는다.

## 9.5 예외는 좁고 만료 가능해야 한다

ExceptionRecord: exception_id, scope(exact path/rule/source anchor), reason,
owner, created_at, expires_at, permit_id, evidence_refs, policy_digest.
승인 없는 신규 exception/blanket noqa는 POLICY_VIOLATION이다.

테스트 decorator `@pytest.mark.skip` 또는 `xfail` 추가는 acceptance 실행 누락을 초래할 수 있다.
기존 테스트 ID·수집 집합·수행 결과를 비교하고 사유를 code reviewer가 판단한다.
전체 skip 수를 유지했다고 합격시키지 않는다.

예외는 자동으로 상속하거나 LLM 판단만으로 scope를 확대하지 않는다. 만료된 예외가 있는 mandatory
위반은 FAIL/EXCEPTION_EXPIRED다. baseline/exception을 자동 수정하는 옵션은 일반 verify CLI에 없다.
