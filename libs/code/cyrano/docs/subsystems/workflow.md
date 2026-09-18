# workflow: 현재 public source reference

현재 import `deepagents_code.cyrano.workflow`. 소유 package는 `../deepagents_code/cyrano/workflow`다. 목표 제품 확장은 해당 WP와 proposed notes에서 확인한다. 아래는 실제 존재하는 source의 서명이며 가정한 API가 아니다.

### plan.py

`class WorkUnit`

`order_plan(units: list[WorkUnit]) -> tuple[str, ...]`

Work-plan structural checks; semantic review is an additional requirement.
