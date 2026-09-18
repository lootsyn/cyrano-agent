# sqlite: 현재 public source reference

현재 import `deepagents_code.cyrano.sqlite`. 소유 package는 `../deepagents_code/cyrano/sqlite`다. 목표 제품 확장은 해당 WP와 proposed notes에서 확인한다. 아래는 실제 존재하는 source의 서명이며 가정한 API가 아니다.

### store.py

`class EventStore`

`EventStore.close(self)`

`EventStore.append(self, stream: str, expected_revision: int, key: str, payload: dict[str, object], *, enqueue: bool=False)`

`EventStore.events(self, stream: str)`

`EventStore.claim(self, owner: str, now: int, ttl: int)`

`EventStore.finish(self, key: str, owner: str, fence: int, now: int)`

Transactional event/outbox foundation; no model or network access.
