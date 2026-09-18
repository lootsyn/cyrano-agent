# interview: 현재 public source reference

현재 import `deepagents_code.cyrano.interview`. 소유 package는 `../deepagents_code/cyrano/interview`다. 목표 제품 확장은 해당 WP와 proposed notes에서 확인한다. 아래는 실제 존재하는 source의 서명이며 가정한 API가 아니다.

### readiness.py

`class Obligation`

`class Readiness`

`assess(obligations: list[Obligation], *, target_stage: str, required_review_current: bool, important_assumptions: int, stale_evidence: int, unresolved_conflicts: int) -> Readiness`

`affected_closure(changed: set[str], dependencies: dict[str, set[str]]) -> set[str]`

Stage readiness is a blocker check, not an averaged LLM score.

### worker_adapter.py

`class WorkerBinding`

`validate_worker_binding(payload: dict[str, object], expected: WorkerBinding) -> None`

Validate original interview worker binding after boundary schema validation.
