"""Versioned canonical encoding for CYRANO artifacts.

CYRANO-C14N-1 canonicalization covers contract documents, not
provider wire requests.
"""

import hashlib
import json
import unicodedata
from typing import TypeAlias

from deepagents_code.cyrano.contracts.types import CyranoError

JSON: TypeAlias = None | bool | int | str | list["JSON"] | dict[str, "JSON"]


def _normalize(value: object) -> JSON:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        if abs(value) > 2**53 - 1:
            raise CyranoError(
                "CANONICAL_RANGE",
                "integer exceeds interoperable range",
            )
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value.replace("\r\n", "\n"))
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        result: dict[str, JSON] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CyranoError(
                    "CANONICAL_KEY",
                    "JSON object keys must be strings",
                )
            normalized = unicodedata.normalize("NFC", key)
            if normalized in result:
                raise CyranoError(
                    "CANONICAL_COLLISION",
                    "normalized key collision",
                )
            result[normalized] = _normalize(item)
        return result
    raise CyranoError(
        "CANONICAL_TYPE",
        "use decimal strings, not float or custom objects",
    )


def canonical_bytes(value: object) -> bytes:
    """Encode CYRANO-C14N-1: NFC, ordered keys, stable arrays."""
    text = json.dumps(
        _normalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CyranoError(
            "CANONICAL_UNICODE", "invalid Unicode scalar value"
        ) from exc


def digest(value: object) -> str:
    """Return the version-qualified SHA-256 digest of canonical data."""
    data = b"CYRANO-C14N-1\0" + canonical_bytes(value)
    return "sha256:" + hashlib.sha256(data).hexdigest()


def raw_digest(data: bytes) -> str:
    """Hash exact bytes for source snapshots and rendered segments."""
    return "sha256:" + hashlib.sha256(data).hexdigest() + ""
