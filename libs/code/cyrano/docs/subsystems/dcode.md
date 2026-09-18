# dcode: 현재 public source reference

현재 import `deepagents_code.cyrano.dcode`. 소유 package는 `../deepagents_code/cyrano/dcode`다. 목표 제품 확장은 해당 WP와 proposed notes에서 확인한다. 아래는 실제 존재하는 source의 서명이며 가정한 API가 아니다.

### adapter.py

`class AttemptRequest`

`class DcodeAttemptPort`

`DcodeAttemptPort.run(self, request: AttemptRequest)`

`require_governed(report: dict[str, str]) -> None`

`runtime_status() -> dict[str, object]`

Runtime port and fail-closed compatibility checks; no substitute agent loop.
