# compiler: 현재 public source reference

현재 import `deepagents_code.cyrano.context`. 소유 package는 `../deepagents_code/cyrano/context`다. 목표 제품 확장은 해당 WP와 proposed notes에서 확인한다. 아래는 실제 존재하는 source의 서명이며 가정한 API가 아니다.

### compiler.py

`class Block`

`class CompiledContext`

`compile_context(blocks: list[Block], dynamic: dict[str, object], *, max_bytes: int=65536) -> CompiledContext`

`cache_read_ratio(total_input: int | None, cache_read: int | None) -> float | None`

Deterministic CYRANO-owned prompt segments; not a provider cache implementation.
