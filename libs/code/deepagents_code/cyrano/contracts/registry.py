"""Explicit kind+schema_version registry; no default inference.

External documents are dispatched by their declared `kind` and
`schema_version` to a registered contract definition. Unknown kinds,
unknown fields, and unregistered versions are rejected. Structural
checks follow local ``$ref`` targets inside the owning schema file.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, TypeAlias, cast

from deepagents_code.cyrano.contracts.ingress import (
    JSON,
    parse_document,
)
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.contracts.validation import (
    validate_semantics,
)

JsonMap: TypeAlias = Mapping[str, JSON]

SCHEMA_FILES = (
    "v1/cyrano.schema.json",
    "v2/governance.schema.json",
)


@dataclass(frozen=True, slots=True)
class ContractType:
    """One registered document type from a contract schema file."""

    type_name: str
    kind: str
    schema_version: str
    required: frozenset[str]
    fields: frozenset[str]
    definition: JsonMap
    root: JsonMap


def _defs(schema: JsonMap) -> JsonMap:
    defs = schema.get("$defs") or schema.get("definitions")
    if isinstance(defs, dict):
        return cast(JsonMap, defs)
    return {}


def _const(node: JsonMap) -> str:
    value = node.get("const")
    return value if isinstance(value, str) else ""


def _resolve(node: JsonMap, root: JsonMap) -> JsonMap:
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        target = _defs(root).get(ref.removeprefix("#/$defs/"))
        if isinstance(target, dict):
            return cast(JsonMap, target)
    if isinstance(ref, str) and ref.startswith("#/definitions/"):
        target = _defs(root).get(ref.removeprefix("#/definitions/"))
        if isinstance(target, dict):
            return cast(JsonMap, target)
    return node


def _check(value: JSON, node: JsonMap, root: JsonMap, path: str) -> None:
    """Bounded structural check: required, fields, const, enum, type."""
    node = _resolve(node, root)
    kind = node.get("type")
    if kind == "object":
        if not isinstance(value, dict):
            raise CyranoError("SCHEMA_INVALID", f"{path}: expected object")
        required = node.get("required", [])
        if isinstance(required, list):
            for field in required:
                if isinstance(field, str) and field not in value:
                    raise CyranoError(
                        "SCHEMA_INVALID",
                        f"{path}.{field}: required field missing",
                    )
        raw_props = node.get("properties", {})
        props = cast(JsonMap, raw_props) if isinstance(raw_props, dict) else {}
        if node.get("additionalProperties") is False:
            extra = set(value) - set(props)
            if extra:
                raise CyranoError(
                    "SCHEMA_INVALID",
                    f"{path}: unknown field {sorted(extra)[0]!r}",
                )
        for key, item in value.items():
            sub = props.get(key)
            if isinstance(sub, dict):
                _check(item, cast(JsonMap, sub), root, f"{path}.{key}")
    elif kind == "array":
        if not isinstance(value, list):
            raise CyranoError("SCHEMA_INVALID", f"{path}: expected array")
        items = node.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(value):
                _check(
                    item,
                    cast(JsonMap, items),
                    root,
                    f"{path}[{index}]",
                )
    elif kind == "string" and not isinstance(value, str):
        raise CyranoError("SCHEMA_INVALID", f"{path}: expected string")
    elif kind == "integer" and type(value) is not int:
        raise CyranoError("SCHEMA_INVALID", f"{path}: expected integer")
    elif kind == "boolean" and type(value) is not bool:
        raise CyranoError("SCHEMA_INVALID", f"{path}: expected boolean")
    const = node.get("const")
    if const is not None and value != const:
        raise CyranoError(
            "SCHEMA_INVALID", f"{path}: expected const {const!r}"
        )
    enum = node.get("enum")
    if isinstance(enum, list) and enum and value not in enum:
        raise CyranoError("SCHEMA_INVALID", f"{path}: value not in enum")


class ContractRegistry:
    """Indexed contract types from explicit schema files."""

    def __init__(self, types: Mapping[tuple[str, str], ContractType]):
        """Store registered types keyed by (kind, version)."""
        self._types = dict(types)

    @classmethod
    def from_files(cls, files: Mapping[str, bytes]) -> "ContractRegistry":
        """Build the registry from raw contract schema bytes."""
        types: dict[tuple[str, str], ContractType] = {}
        for raw in files.values():
            schema = parse_document(raw)
            for type_name, node in _defs(schema).items():
                if not isinstance(node, dict):
                    continue
                node_map = cast(JsonMap, node)
                props = node_map.get("properties", {})
                if not isinstance(props, dict):
                    continue
                props_map = cast(JsonMap, props)
                kind = _const(
                    cast(
                        JsonMap,
                        props_map.get("kind")
                        if isinstance(props_map.get("kind"), dict)
                        else {},
                    )
                )
                raw_version = props_map.get("schema_version")
                version = _const(
                    cast(
                        JsonMap,
                        raw_version if isinstance(raw_version, dict) else {},
                    )
                )
                if not kind or not version:
                    continue
                required = node_map.get("required", [])
                ctype = ContractType(
                    type_name=type_name,
                    kind=kind,
                    schema_version=version,
                    required=frozenset(str(item) for item in required)
                    if isinstance(required, list)
                    else frozenset(),
                    fields=frozenset(str(k) for k in props_map),
                    definition=node_map,
                    root=schema,
                )
                types[(kind, version)] = ctype
        return cls(types)

    @classmethod
    def from_root(cls, contract_root: Path) -> "ContractRegistry":
        """Load the registry from a checkout's contracts directory."""
        files = {
            name: (contract_root / name).read_bytes() for name in SCHEMA_FILES
        }
        return cls.from_files(files)

    def lookup(self, kind: object, schema_version: object) -> ContractType:
        """Resolve a declared kind+version or reject explicitly."""
        if not isinstance(kind, str) or not kind:
            raise CyranoError("SCHEMA_INVALID", "document has no kind field")
        candidates = [t for (k, _), t in self._types.items() if k == kind]
        if not candidates:
            raise CyranoError("UNKNOWN_KIND", f"unregistered kind {kind!r}")
        for ctype in candidates:
            if ctype.schema_version == schema_version:
                return ctype
        raise CyranoError(
            "UNSUPPORTED_SCHEMA_VERSION",
            f"{kind!r} schema_version {schema_version!r} not supported",
        )

    def validate_document(
        self,
        data: bytes | str,
        *,
        semantic: bool = True,
    ) -> dict[str, JSON]:
        """Strict parse, dispatch, schema and semantic checks."""
        document = parse_document(data)
        ctype = self.lookup(
            document.get("kind"), document.get("schema_version")
        )
        _check(document, ctype.definition, ctype.root, "$")
        if semantic and ctype.schema_version == "1.0":
            validate_semantics(document)
        return document

    def type_name(self, kind: object, schema_version: object) -> str:
        """Return the PascalCase contract type for a document."""
        return self.lookup(kind, schema_version).type_name
