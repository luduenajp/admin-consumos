"""Lenient multipart/form-data parser used as a fallback for POST
/share-target (UC-054) when Starlette's standard parser finds zero parts.

Samsung Internet (confirmed via production logs) sends a well-formed
multipart body but inserts a stray byte (observed: a single NUL) between
the part's content and the closing boundary delimiter — e.g.
`...IEND\\xaeB\\x60\\x82\\r\\n\\x00------boundary------\\r\\n` instead of the
spec-correct `...\\x82\\r\\n------boundary------\\r\\n`. Standard parsers
require the boundary immediately after `\\r\\n` and silently give up,
yielding an empty form instead of raising. This parser locates parts by
splitting on the boundary delimiter directly (which works regardless of
what precedes it) rather than requiring exact adjacency.
"""
from __future__ import annotations

import re

_BOUNDARY_RE = re.compile(r'boundary="?([^";]+)"?', re.IGNORECASE)
_FIELD_NAME_RE = re.compile(r'name="([^"]*)"', re.IGNORECASE)
_FILENAME_RE = re.compile(r'filename="([^"]*)"', re.IGNORECASE)
_CONTENT_TYPE_RE = re.compile(r'^content-type:\s*(.+)$', re.IGNORECASE | re.MULTILINE)


def recover_file_part(body: bytes, content_type_header: str, field_name: str = "file") -> tuple[bytes, str, str] | None:
    """Best-effort extraction of a named file part from a malformed
    multipart body. Returns (content, filename, content_type) or None."""
    match = _BOUNDARY_RE.search(content_type_header)
    if not match:
        return None
    delimiter = b"--" + match.group(1).encode("latin-1", errors="ignore")

    parts = body.split(delimiter)
    for part in parts[1:-1]:  # skip preamble (before first) and epilogue (after last)
        part = part.lstrip(b"\r\n")
        header_block, sep, content = part.partition(b"\r\n\r\n")
        if not sep:
            continue
        headers = header_block.decode("latin-1", errors="replace")
        name_match = _FIELD_NAME_RE.search(headers)
        if not name_match or name_match.group(1) != field_name:
            continue
        filename_match = _FILENAME_RE.search(headers)
        if not filename_match or not filename_match.group(1):
            continue
        type_match = _CONTENT_TYPE_RE.search(headers)
        file_content = content.rstrip(b"\r\n\x00")
        if not file_content:
            continue
        return (
            file_content,
            filename_match.group(1),
            type_match.group(1).strip() if type_match else "application/octet-stream",
        )
    return None
