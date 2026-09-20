"""Tests for the lenient multipart parser (UC-054 backend recovery path).

Samsung Internet has been observed in production sending a well-formed
multipart body with a stray NUL byte between a part's content and the
closing boundary delimiter, which the standard multipart parser (used by
Starlette/python-multipart) fails to parse, yielding zero parts. These
tests build that exact malformed shape by hand and confirm the lenient
parser recovers the file anyway.
"""
from __future__ import annotations

from app.multipart_recovery import recover_file_part

BOUNDARY = "----MultipartBoundary--abc123----"
CONTENT_TYPE = f"multipart/form-data; boundary={BOUNDARY}"


def _build_body(content: bytes, *, stray_bytes: bytes = b"", filename: str = "comprobante.png") -> bytes:
    return (
        f"--{BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode("latin-1") + content + b"\r\n" + stray_bytes + f"--{BOUNDARY}--\r\n".encode("latin-1")


def test_recovers_file_with_stray_nul_before_closing_boundary():
    # Exact shape observed from Samsung Internet in production logs.
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50 + b"IEND\xaeB\x60\x82"
    body = _build_body(png_bytes, stray_bytes=b"\x00")

    result = recover_file_part(body, CONTENT_TYPE)

    assert result is not None
    content, filename, content_type = result
    assert content == png_bytes
    assert filename == "comprobante.png"
    assert content_type == "image/png"


def test_recovers_file_with_no_corruption():
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00fake"
    body = _build_body(png_bytes)

    result = recover_file_part(body, CONTENT_TYPE)

    assert result is not None
    content, _, _ = result
    assert content == png_bytes


def test_returns_none_when_boundary_missing_from_content_type():
    assert recover_file_part(b"whatever", "multipart/form-data") is None


def test_returns_none_when_no_file_part_present():
    body = (
        f"--{BOUNDARY}\r\n"
        'Content-Disposition: form-data; name="title"\r\n\r\n'
        "some text"
        f"\r\n--{BOUNDARY}--\r\n"
    ).encode("latin-1")

    assert recover_file_part(body, CONTENT_TYPE) is None


def test_returns_none_for_empty_body():
    assert recover_file_part(b"", CONTENT_TYPE) is None
