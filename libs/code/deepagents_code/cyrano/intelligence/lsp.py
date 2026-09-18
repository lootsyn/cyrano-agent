"""Read-only LSP protocol primitives.

Positions are UTF-16 code units per the protocol; byte and Python
character offsets must be converted explicitly. Mutating server
requests are classified and denied before dispatch. Framing has a
hard byte bound — an oversized message is an error, not a truncate.
"""

from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError

READ_METHODS = frozenset(
    {
        "textDocument/references",
        "textDocument/definition",
        "textDocument/hover",
        "textDocument/documentSymbol",
        "textDocument/completion",
    }
)
WRITE_METHODS = frozenset(
    {
        "workspace/applyEdit",
        "workspace/executeCommand",
        "textDocument/didChange",
        "textDocument/didOpen",
        "textDocument/didClose",
        "workspace/didChangeWatchedFiles",
    }
)


def classify_method(method: str) -> str:
    """Classify a method as ``read``, ``write`` or ``unknown``."""
    if method in READ_METHODS:
        return "read"
    if method in WRITE_METHODS:
        return "write"
    return "unknown"


def utf16_column(line_text: str, character_offset: int) -> int:
    """Convert a Python character offset to UTF-16 code units."""
    if character_offset < 0 or character_offset > len(line_text):
        raise CyranoError(
            "INPUT_INVALID",
            f"offset {character_offset} outside line",
        )
    return len(line_text[:character_offset].encode("utf-16-le")) // 2


def py_offset_from_utf16(line_text: str, utf16_col: int) -> int:
    """Convert a UTF-16 column back to a Python character offset."""
    units = 0
    for index, char in enumerate(line_text):
        units += 2 if ord(char) > 0xFFFF else 1
        if units > utf16_col:
            return index
        if units == utf16_col:
            return index + 1
    raise CyranoError(
        "INPUT_INVALID", f"utf16 column {utf16_col} outside line"
    )


@dataclass(frozen=True, slots=True)
class Position:
    """A protocol position in zero-based UTF-16 units."""

    line: int
    character: int


@dataclass(slots=True)
class FramingBuffer:
    """Content-Length framing with a hard per-message byte bound."""

    max_bytes: int = 4_194_304

    def frame(self, body: bytes) -> bytes:
        """Wrap a body in headers; oversize is an error."""
        if len(body) > self.max_bytes:
            raise CyranoError(
                "TOOL_ARGUMENT_LIMIT",
                f"message of {len(body)} bytes exceeds the bound",
            )
        return f"Content-Length: {len(body)}\r\n\r\n".encode() + body

    def unframe(self, header_bytes: int) -> bytes:
        """Validate a declared length before the body is read."""
        if header_bytes > self.max_bytes:
            raise CyranoError(
                "TOOL_ARGUMENT_LIMIT",
                f"declared length {header_bytes} exceeds the bound",
            )
        return b""
