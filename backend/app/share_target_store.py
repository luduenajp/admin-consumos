"""In-memory, one-shot storage for files received by the /share-target
backend fallback (UC-054), used when the service worker fails to intercept
the Web Share Target POST (e.g. cold app launch on Android).

A token is minted per stored file and consumed (popped) exactly once by
GET /api/share-target/pending/{token}. Entries expire after TTL_SECONDS so a
crashed/abandoned flow doesn't leak memory.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

TTL_SECONDS = 5 * 60


@dataclass
class PendingShare:
    content: bytes
    filename: str
    content_type: str
    expires_at: float


_store: dict[str, PendingShare] = {}


def _cleanup_expired() -> None:
    now = time.time()
    for token in [t for t, item in _store.items() if item.expires_at < now]:
        _store.pop(token, None)


def put(content: bytes, filename: str, content_type: str) -> str:
    _cleanup_expired()
    token = secrets.token_urlsafe(24)
    _store[token] = PendingShare(
        content=content,
        filename=filename,
        content_type=content_type,
        expires_at=time.time() + TTL_SECONDS,
    )
    return token


def pop(token: str) -> PendingShare | None:
    _cleanup_expired()
    return _store.pop(token, None)
