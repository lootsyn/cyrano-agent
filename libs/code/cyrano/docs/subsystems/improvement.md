# improvement: 현재 public source reference

현재 import `deepagents_code.cyrano.improvement`. 소유 package는 `../deepagents_code/cyrano/improvement`다. 목표 제품 확장은 해당 WP와 proposed notes에서 확인한다. 아래는 실제 존재하는 source의 서명이며 가정한 API가 아니다.

### classification.py

`class Impact`

`classify(paths: list[str], *, input_semantics_unchanged: bool, policy_ir_validated: bool) -> Impact`

Server-owned impact classification; filenames alone never prove replayability.

### replay.py

`class RecordedTransition`

`class Replay`

`Replay.view(self)`

`Replay.step(self, actions: dict[str, str], legal_ids: frozenset[str], *, worker_cap: int)`

Small atomic replay kernel; real worlds require a separately verified builder.
