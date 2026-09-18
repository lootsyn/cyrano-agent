"""Strict JSON boundary parsing for external CYRANO artifacts.

External input must be rejected before coercion: duplicate keys,
floats, excessive depth, surrogate code points, oversized payloads
and out-of-range integers never reach semantic validation. This
parser performs no last-wins, numeric coercion, or key repair.
"""

import json
from typing import TypeAlias

from deepagents_code.cyrano.contracts.types import CyranoError

JSON: TypeAlias = None | bool | int | str | list["JSON"] | dict[str, "JSON"]

DEFAULT_MAX_BYTES = 1 << 20
DEFAULT_MAX_DEPTH = 32


def _reject_float(value: str) -> None:
    """Reject every JSON float token; decimals stay strings."""
    raise CyranoError(
        "STRICT_NUMBER", f"float token {value!r} is not a contract number"
    )


def _reject_constant(value: str) -> None:
    """Reject NaN and Infinity literals outright."""
    raise CyranoError(
        "STRICT_NUMBER", f"non-finite literal {value!r} is rejected"
    )


def _reject_int(value: str) -> int:
    """Reject integers outside the interoperable 2^53 range."""
    parsed = int(value)
    if abs(parsed) > 2**53 - 1:
        raise CyranoError(
            "STRICT_RANGE", "integer exceeds interoperable range"
        )
    return parsed


def _pairs(pairs: list[tuple[str, JSON]]) -> dict[str, JSON]:
    """Reject duplicate object keys instead of last-wins parsing."""
    result: dict[str, JSON] = {}
    for key, item in pairs:
        if key in result:
            raise CyranoError("STRICT_DUPLICATE_KEY", f"duplicate key {key!r}")
        result[key] = item
    return result


def _scalars(value: JSON, depth: int, max_depth: int) -> None:
    """Enforce the nesting limit and reject surrogate code points."""
    if depth > max_depth:
        raise CyranoError(
            "STRICT_DEPTH", f"document exceeds depth {max_depth}"
        )
    if isinstance(value, str):
        for char in value:
            if 0xD800 <= ord(char) <= 0xDFFF:
                raise CyranoError(
                    "STRICT_UNICODE", "surrogate code point rejected"
                )
    elif isinstance(value, list):
        for item in value:
            _scalars(item, depth + 1, max_depth)
    elif isinstance(value, dict):
        for key, item in value.items():
            _scalars(key, depth + 1, max_depth)
            _scalars(item, depth + 1, max_depth)


def parse_json(
    data: bytes | str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> JSON:
    """Parse external JSON with strict contract-boundary rules."""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    if len(raw) > max_bytes:
        raise CyranoError("STRICT_SIZE", f"payload exceeds {max_bytes} bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CyranoError(
            "STRICT_UNICODE", "payload is not valid UTF-8"
        ) from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_float=_reject_float,
            parse_int=_reject_int,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise CyranoError(
            "STRICT_SYNTAX", f"invalid JSON at {exc.lineno}:{exc.colno}"
        ) from exc
    _scalars(value, 0, max_depth)
    return value


def parse_document(
    data: bytes | str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> dict[str, JSON]:
    """Parse external JSON and require a top-level object."""
    value = parse_json(data, max_bytes=max_bytes, max_depth=max_depth)
    if not isinstance(value, dict):
        raise CyranoError("SCHEMA_INVALID", "document must be a JSON object")
    return value
