# 4. AGENTS, Skill, 역할, 컨텍스트

## 4.1 AGENTS 파일

프로젝트에는 기존 AGENTS를 보존하며 Python 섹션만 추가한다. 이미 root `AGENTS.md`를 쓰면
그곳을 canonical로 둔다. `.deepagents/AGENTS.md`에는 필요할 경우 dcode 고유 안내만 둔다.
현행 dcode는 root와 `.deepagents/AGENTS.md`를 둘 다 읽어 결합하므로 동일 규칙을 복사하면
중복된다. Skill은 `.agents/skills`가 `.deepagents/skills`보다 우선한다. [S08]

항상 로드할 내용은 다음 정도로 제한한다. token 예산은 모델 tokenizer별 측정값이지 보편적 상수가 아니다.

```markdown
## Python engineering
- Python changes must follow the approved repository quality policy.
- Load the resolved python-engineering skill before Python implementation.
- Review the work plan before editing; stay inside its approved scope.
- Fix causes, not checks. Never weaken policy, tests, or exclusions to get PASS.
- Only the trusted completion service may mark a governed task complete.
- Report blocked, failed, cancelled, and baseline debt truthfully.
```

이 문장들은 행동 안내이지 OS 권한 경계가 아니다.

## 4.2 Skill 활성화 조건

description에 Python 코드 생성/수정/리팩터링/리뷰/테스트/pyproject 변경을 포함한다.
일반 설명 질문이나 Python 변경 없는 문서 오타 수정에는 자동 활성화가 불필요하다.
반면 `.pyi`, `conftest.py`, dependency/typing/lint 설정, 테스트 삭제, Python entry point를 건드리는
작업은 Python 작업으로 분류한다. prompt classifier가 놓쳐도 최종 inventory diff가 다시 확인한다.

Skill metadata 기반 발견은 모델의 본문 읽기를 보장하지 않는다. governed launcher는 Python
WorkUnit 시작 시 resolved absolute Skill path와 raw digest를 기록하고, 로드 receipt를 확보한다.
중복 이름은 실제 우선순위로 하나를 선택하고 충돌을 사용자에게 표시한다. 경로를 이름 조합으로 추측하지 않는다.
다른 작업 중 Python 변경이 새로 발견되면 범위를 재검토한 뒤 Skill과 계획을 갱신한다.

공식 Deep Agents Skills는 metadata를 먼저 제공하고 본문/보조 자료를 필요 시 읽는 방식이다.
이를 활용하되 필요한 정책을 안 읽게 하는 방식으로 토큰을 줄이지 않는다. [S09]

## 4.3 Skill workflow

1. Inspect: 실제 파일·설정·관련 테스트·기존 실패를 읽는다.
2. Plan: 요구/acceptance IDs, 수정 경로, 예상 동작, 검증 recipe를 고정한다.
3. Review plan: 독립 reviewer가 빠진 요구·범위·검증 가능성·권한을 검사한다.
4. Implement: 작은 변경과 회귀 테스트를 함께 작성한다.
5. Feedback: focused tests → 안전한 Ruff import fix → Black → lint/type 확인.
6. Verify: 봉인 snapshot에 최종 gate를 실행한다. local PASS를 governed PASS로 승격하지 않는다.
7. Repair: 새 실패를 근거로 수정하고 새 snapshot에서 필요한 검사를 다시 실행한다.
8. Code review: 전체 diff, 요구 충족, 예외·테스트 의미를 독립적으로 검토한다.
9. Complete request: 보고서 ID만 제시한다. 서비스가 identity/승인을 조회해 확정한다.
10. Learn proposal: 반복 실패가 있을 때만 좁은 개선 후보를 제안한다.

불필요한 전체 format/lint --fix를 실행하지 않는다. 자동 수정 대상은 변경 파일 집합이며,
Black이 파일 전체를 재배치하는 영향도 diff에 드러내고 계획 범위와 비교한다.
`ruff --unsafe-fixes`는 기본 금지다. 안전한 fix라 하더라도 검증을 건너뛸 수 없다.

## 4.4 역할 계약

| 역할 | 입력 | 출력 | 권한 |
|---|---|---|---|
| implementer | approved plan, scope, policy, selected Skill | patch, 설명, gate 요청 | candidate 범위 쓰기 |
| plan-reviewer | 원요구, 계획, repository facts | 구조화된 review | 읽기와 review 제출 |
| code-reviewer | 원요구, frozen diff, tests, 실제 gate 결과 | findings, disposition | 읽기와 review 제출 |
| verifier | frozen subject, trusted policy | receipts/report | 도구 실행; LLM 역할이 아님 |
| improvement-author | 비식별 실패 집계, 허가된 skill surface | candidate patch | 격리 후보 쓰기 |

reviewer의 독립성은 “다른 provider를 사용함”이 아니다. 다른 execution ID, 분리된 context,
원요구/실제 diff/검증 결과를 독립적으로 읽는 것으로 정의한다. implementer 요약만 주지 않는다.
같은 모델 사용은 허용하며 특정 모델명 하드코딩은 없다. 판단 일치가 독립성 보장도 아니다.

현재 dcode의 파일 기반 custom subagent는 도구 제한을 AGENTS frontmatter로 지정할 수 없고
main agent 도구를 상속한다. `tools: read_only` 같은 가짜 설정을 만들지 않는다. 파일 프롬프트의
“쓰기 금지”는 advisory다. governed reviewer는 별도 SDK 구성 또는 read-only sandbox에서 실행하고
backend capability test가 성공해야 한다. [S10]

## 4.5 Prompt caching과 context 배치

UDH가 소유한 context 블록 순서는 release 단위로 고정한다.
`고정 역할 → 고정 정책 요약 → 안정적으로 정렬된 Skill metadata → 작업별 tail`.
실패 로그, 현재 시각, attempt ID, 매번 바뀌는 통계는 stable block에 넣지 않는다.
긴 raw 로그는 artifact로 저장하고 모델에는 rule/path/range/원인 요약과 필요한 부분만 전달한다.
공급자의 실제 prompt 조립 순서까지 통제한다고 주장하지 않는다.

Skill 본문 변경, 도구 inventory 변경, memory release 변경은 context release 변경으로 기록한다.
작업 도중 활성 Skill을 덮어쓰지 않는다. 다음 세션/명시적 reload에서 적용하고 기존 승인된 실행과
혼합하지 않는다. 자동 memory 저장이 켜진 native dcode는 governed policy를 덮어쓰지 못하게 격리하고,
필요 시 별도 profile에서 `[memory] auto_save=false`를 설정한다. [S08]

권장 예산: AGENTS Python 섹션 300 tokens 이하, Skill body 1,500~2,500 tokens 수준에서 시작해
실제 tokenizer로 측정한다. 이 숫자는 개발 기본값이지 합격 기준 또는 캐시 hit 보장이 아니다.
cache_read_tokens가 제공되지 않으면 null/unknown을 기록한다. hit 비율은 공급자 usage 의미가
확인된 표본에만 계산한다. 더 빠른 응답을 cache hit의 증거로 사용하지 않는다.
