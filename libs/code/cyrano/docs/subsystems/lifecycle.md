# lifecycle: 현재 public source reference

현재 import `deepagents_code.cyrano.plugins`. 소유 package는 `../deepagents_code/cyrano/plugins`다. 목표 제품 확장은 해당 WP와 proposed notes에서 확인한다. 아래는 실제 존재하는 source의 서명이며 가정한 API가 아니다.

### registry.py

`class Plugin`

`Plugin.setup(self, register: Callable[[str, object], None])`

`class Registry`

`Registry.load(self, plugin_id: str, plugin: Plugin)`

`Registry.unload(self, plugin_id: str)`

`Registry.close(self)`

Explicit plugin contributions with rollback and reverse-order teardown.
