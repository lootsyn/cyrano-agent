# contracts: 현재 public source reference

현재 import `deepagents_code.cyrano.contracts`. 소유 package는 `../deepagents_code/cyrano/contracts`다. 목표 제품 확장은 해당 WP와 proposed notes에서 확인한다. 아래는 실제 존재하는 source의 서명이며 가정한 API가 아니다.

### canonical.py

`canonical_bytes(value: object) -> bytes`

`digest(value: object) -> str`

`raw_digest(data: bytes) -> str`

Versioned canonical encoding for CYRANO artifacts, not provider wire requests.

### subjects.py

`binding_digest(schema_type: str, document: dict[str, object]) -> str`

Separate approval subjects from lifecycle and receipt envelopes.

Field ownership is fixed by contracts/v1/digest-projections.json. Validate the
complete transport document before calling this helper; it is not authority.

### types.py

`class CyranoError`

`class EvidenceLevel`

`class Scope`

`class Outcome`

`Outcome.complete(self)`

Shared value objects; parsing and authorization remain separate operations.

### validation.py

`validate_semantics(document: dict[str, object]) -> None`

Semantic consistency checks after JSON Schema validation.

These checks reject contradictory documents. They do not authenticate evidence,
verify signatures, query scope ACLs, or authorize state transitions.
