# memory: 현재 public source reference

현재 import `deepagents_code.cyrano.memory`. 소유 package는 `../deepagents_code/cyrano/memory`다. 목표 제품 확장은 해당 WP와 proposed notes에서 확인한다. 아래는 실제 존재하는 source의 서명이며 가정한 API가 아니다.

### selection.py

`class Memory`

`select_memories(records: list[Memory], scope: Scope, now: datetime, available_digests: frozenset[str], *, limit: int=10) -> list[Memory]`

Exact-scope, time-bounded selection; relevance never grants authority.
