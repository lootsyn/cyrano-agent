# kernel: 현재 public source reference

현재 import `deepagents_code.cyrano.kernel`. 소유 package는 `../deepagents_code/cyrano/kernel`다. 목표 제품 확장은 해당 WP와 proposed notes에서 확인한다. 아래는 실제 존재하는 source의 서명이며 가정한 API가 아니다.

### transitions.py

`transition(current: str, target: str, *, evidence_ready: bool=False) -> str`

Pure transition validation; caller supplies broker-verified prerequisites.
