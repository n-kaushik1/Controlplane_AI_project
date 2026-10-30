"""
Optional API protection for ControlPlane.ai.

Both controls are opt-in and read the live ``settings`` object on every
call, so they stay disabled (and the dashboard keeps working unchanged)
unless ``API_KEY`` / ``RATE_LIMIT_PER_MINUTE`` are configured.
"""

import hmac
import re
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

from fastapi import Header, HTTPException, Request

from app.core.config import settings


# =========================================================
# API KEY AUTHENTICATION
# =========================================================

def require_api_key(
    x_api_key: Optional[str] = Header(default=None),
) -> None:
    """
    FastAPI dependency enforcing the ``X-API-Key`` header.

    No-op when ``settings.API_KEY`` is not configured.
    Uses a constant-time comparison to avoid timing leaks.
    """

    expected = settings.API_KEY

    if not expected:
        return

    if not x_api_key or not hmac.compare_digest(
        x_api_key.encode("utf-8"),
        expected.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )


# =========================================================
# RATE LIMITING
# =========================================================

class SlidingWindowRateLimiter:
    """
    In-memory sliding-window limiter keyed by client identifier.

    Suitable for a single-process deployment; a multi-instance
    deployment would need a shared store such as Redis.
    """

    WINDOW_SECONDS = 60.0

    def __init__(self) -> None:

        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

        self._lock = threading.Lock()

    def check(
        self,
        key: str,
        limit: int,
        now: Optional[float] = None,
    ) -> Optional[int]:
        """
        Record a hit for ``key``.

        Returns ``None`` when the request is allowed, otherwise
        the number of seconds until the client may retry.
        """

        now = time.monotonic() if now is None else now

        cutoff = now - self.WINDOW_SECONDS

        with self._lock:

            hits = self._hits[key]

            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= limit:
                return max(
                    1,
                    int(hits[0] + self.WINDOW_SECONDS - now) + 1,
                )

            hits.append(now)

            # Drop idle clients so memory stays bounded.
            if len(self._hits) > 10_000:
                self._evict_idle(cutoff)

            return None

    def _evict_idle(self, cutoff: float) -> None:

        for key in [
            k for k, v in self._hits.items()
            if not v or v[-1] <= cutoff
        ]:
            del self._hits[key]

    def reset(self) -> None:

        with self._lock:
            self._hits.clear()


rate_limiter = SlidingWindowRateLimiter()


def enforce_rate_limit(request: Request) -> None:
    """
    FastAPI dependency applying ``RATE_LIMIT_PER_MINUTE`` per client IP.

    No-op when the limit is 0.
    """

    limit = settings.RATE_LIMIT_PER_MINUTE

    if limit <= 0:
        return

    client = request.client.host if request.client else "unknown"

    retry_after = rate_limiter.check(client, limit)

    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )


# =========================================================
# REQUEST ID SANITISATION
# =========================================================

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._\-]{1,64}$")


def sanitize_request_id(value: Optional[str]) -> Optional[str]:
    """
    Accept a caller-supplied request ID only if it is short and
    contains log-safe characters; otherwise discard it.
    """

    if value and _REQUEST_ID_RE.match(value):
        return value

    return None
