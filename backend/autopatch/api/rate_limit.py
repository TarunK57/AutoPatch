"""Rate limiting middleware and dependency enforcing request volume limits per user and IP."""

from __future__ import annotations

import time
from typing import Dict, List
from fastapi import HTTPException, Request, status


class InMemoryRateLimiter:
    """Sliding-window rate limiter tracking requests per key (user ID or client IP)."""

    def __init__(self, max_requests: int = 120, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests_by_key: Dict[str, List[float]] = {}

    def check_rate_limit(self, key: str) -> None:
        now = time.time()
        timestamps = self._requests_by_key.setdefault(key, [])

        # Evict timestamps outside current window
        cutoff = now - self.window_seconds
        self._requests_by_key[key] = [t for t in timestamps if t > cutoff]

        if len(self._requests_by_key[key]) >= self.max_requests:
            retry_after = int(self.window_seconds - (now - self._requests_by_key[key][0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: max {self.max_requests} requests per {self.window_seconds}s.",
                headers={"Retry-After": str(max(1, retry_after))},
            )

        self._requests_by_key[key].append(now)

    def reset(self) -> None:
        self._requests_by_key.clear()


# Default singleton instance for the API
default_rate_limiter = InMemoryRateLimiter()


def rate_limit_dependency(request: Request) -> None:
    """FastAPI dependency checking rate limits based on client host or user header."""
    key = request.client.host if request.client else "unknown_client"
    auth_header = request.headers.get("authorization") or request.headers.get("x-api-key")
    if auth_header:
        key = auth_header[:32]
    default_rate_limiter.check_rate_limit(key)
