# 2. 아키텍처와 파일별 책임

## 2.1 요청 처리 경로

```text
사용자 요청 / 기존 InterviewOutcome
  → WorkPlan 작성 → 결정론적 구조 검사 → 별도 PlanReview
  → trusted PlanPermit 발급
  → dcode implementer: Skill 로드 → 코드·테스트 구현 → 로컬 피드백
  → trusted SnapshotService: 후보 바이트 봉인
  → QualityRunner: policy guard → Black → Ruff → typing → tests
  → 별도 CodeReview: 요구 충족·설계·검증 의미 검토
  → CompletionService: 증거·스냅샷·승인 원자적 검증
  → COMPLETE / COMPLETE_BASELINED / BLOCKED / FAILED / CANCELLED
  → 이벤트 집계 → 개선 후보 제안 → 평가·승인 → 다음 release
```

순환은 `검사 실패 → 원인 수정 → 새 snapshot → 재검사`다. `검사 실패 → 기준 완화 → 성공`이 아니다.
모든 에이전트가 별도 프로세스일 필요는 없다. 다만 implementer와 reviewer는 별도 실행/입력을 가지며,
검증 verdict는 LLM 호출이 아니라 순수 reducer와 trusted receipt로 계산한다.

## 2.2 제품 저장소에 추가할 경로

```text
udh-deepagent-code/
├── packages/
│   ├── core/contracts/src/udh_contracts/quality.py
│   ├── core/kernel/src/udh_kernel/quality_completion.py
│   ├── quality/gate/
│   │   ├── pyproject.toml
│   │   ├── src/udh_quality/
│   │   │   ├── __init__.py
│   │   │   ├── policy.py
│   │   │   ├── discovery.py
│   │   │   ├── snapshot.py
│   │   │   ├── guard.py
│   │   │   ├── runner.py
│   │   │   ├── adapters/{base,black,ruff,mypy,pyright,pytest}.py
│   │   │   ├── baseline.py
│   │   │   ├── suppression.py
│   │   │   ├── evidence.py
│   │   │   ├── reducer.py
│   │   │   ├── repair.py
│   │   │   └── service.py
│   ├── runtime/dcode/src/udh_dcode/quality_bridge.py
│   ├── storage/sqlite/src/udh_sqlite/quality_store.py
│   └── observability/events/src/udh_events/quality.py
├── apps/cli/src/udh_cli/quality.py
├── plugins/udh/skills/python-engineering/{SKILL.md,references/}
├── plugins/udh/agents/{python-plan-reviewer,python-code-reviewer}/AGENTS.md
├── .agents/skills/python-engineering/     # UDH 자체 개발용
├── configs/quality/{python.toml,exceptions.json,toolchain.lock.json}
├── contracts/v1/quality-*.schema.json
├── contracts/sql/quality.sql
├── scripts/quality_gate.py               # 개발 편의 thin wrapper만
├── tests/quality/{unit,integration,acceptance}/
├── docs/design/python-quality/
├── docs/development/python-quality-plan.md
└── docs/execution/python-quality-runbook.md
```

`packages/quality/gate`는 기존 `packages/*/*` 멤버 패턴과 맞는다. 기존 패키지 구조를 그대로 둔다.
공용 타입은 `udh_contracts`가 소유하고 quality package가 자체 복제 타입을 만들지 않는다.
프로젝트별 요구·acceptance 추적은 기존 `udh_workflow`, Attempt/이벤트 수명주기는 기존 kernel/store에
연결한다. 품질 전용 두 번째 workflow engine 또는 독립 승인 DB를 만들지 않는다. [U01]

## 2.3 모듈 구현 계약

| 모듈 | 입력 → 출력 | 반드시 할 일 | 금지 |
|---|---|---|---|
| policy.py | repo config + trusted release → ResolvedQualityPolicy | 승인된 설정 계층, canonical digest, 미지원 키 오류 | 모델 선택값으로 필수 검사 해제 |
| discovery.py | snapshot inventory + roots → PythonInventory | .py/.pyi 포함, empty scope 검증, 누락 탐지 | gitignore만 보고 대상 축소 |
| snapshot.py | frozen candidate → SourceSnapshot | raw bytes/파일 mode/경로 digest, 원자적 봉인 | Git HEAD만을 코드 identity로 사용 |
| guard.py | preimage/postimage/permit → GuardResult | 보호 표면·범위·예외·테스트 무력화 조사 | 정책 수정으로 실패 은폐 |
| runner.py | sealed snapshot/policy → ToolReceipts | shell=False, timeout, cleanup, 도구 identity | 모델의 임의 argv 실행 |
| adapters | ToolReceipt → NormalizedCheckResult | 버전별 파서, exit code·JSON 일치 확인 | 이해 못한 결과를 PASS로 처리 |
| baseline.py | before/after diagnostics → BaselineComparison | multiset·파일 digest·정책 동등성 비교 | 총 오류 개수만 비교 |
| suppression.py | tokenized Python + AST + diff → Finding[] | 신규 noqa/ignore/fmt/skip 탐지 | 문자열 내부의 예제까지 지시문으로 오탐 |
| evidence.py | result + controller receipt → stored artifact | atomic write, raw/normalized 구분 | candidate JSON을 trusted로 등록 |
| reducer.py | required checks + results → GateVerdict | 순수 함수, 전체 case 테스트 | provider/model API 호출 |
| repair.py | failure + budget → RepairDecision | 실패 분류·반복 제한·정체 탐지 | 무한 fix loop |
| service.py | trusted commands → domain events | idempotency·권한·상태 전이 | 임의 status setter |
| quality_bridge.py | dcode tool/hook input → service request | identity binding·버전 probe | prompt 내용만 보고 COMPLETE 처리 |

## 2.4 설정의 단일 원본

도구 설정: 대상 저장소의 승인된 `pyproject.toml` 및 명시적으로 열거한 nested config.
실행 정책: `configs/quality/python.toml`.
배포된 신뢰 원본: controller에 등록한 **이 두 설정의 immutable release bundle**.

“pyproject가 원본”과 “controller가 신뢰 원본”은 모순이 아니다. 저장소에서 리뷰한 설정을 배포할 때
바이트와 의미를 고정한 것이다. implementer가 작업 도중 바꾼 pyproject는 새 정책 후보일 뿐,
현재 검사를 바꾸는 권한이 없다. 사용자에게 변경 승인받은 dependency 변경도 tool config 수정과
별도 diff로 검토한다. 새로운 승인 시 policy/plan digest를 갱신하고 이전 PASS를 재사용하지 않는다.

동일 Skill을 `.deepagents/skills`와 `.agents/skills` 양쪽에 수작업으로 중복 보관하지 않는다.
제품 배포용과 UDH 자체 개발용은 템플릿으로 생성하고 내용/변수 치환 차이를 manifest로 검사한다.

이 추가 패키지의 테스트는 `tests/quality/`에 중앙 배치해 기존 pytest testpaths와 정합성을 유지한다.
