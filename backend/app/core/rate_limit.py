"""
Rate limiting + retry-with-backoff for providers with strict free-tier
quotas (Gemini's free tier is 15 RPM on flash models, for example).

Two independent mechanisms, used together:
1. RateLimiter - a simple sliding-window throttle that makes the app wait
   *before* sending a request if it would exceed the configured RPM, so
   we don't even attempt to burst past the quota.
2. retry_with_backoff - if a 429 slips through anyway (e.g. quota shared
   across multiple app instances), parses the provider's own suggested
   retryDelay out of the error body and waits exactly that long before
   retrying, instead of guessing.
"""
import asyncio
import re
import time
from collections import deque


class RateLimiter:
    """Sliding-window limiter: blocks until a call is safely within
    `max_per_minute` calls in the trailing 60 seconds."""

    def __init__(self, max_per_minute: int):
        self.max_per_minute = max_per_minute
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            window_start = now - 60
            while self._timestamps and self._timestamps[0] < window_start:
                self._timestamps.popleft()

            if len(self._timestamps) >= self.max_per_minute:
                wait_for = 60 - (now - self._timestamps[0])
                if wait_for > 0:
                    await asyncio.sleep(wait_for)

            self._timestamps.append(time.monotonic())


_RETRY_DELAY_PATTERN = re.compile(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"')
_ZERO_QUOTA_PATTERN = re.compile(r'"?limit"?\s*:\s*0\b')


def is_permanent_zero_quota(error_body: str) -> bool:
    """True if the error body shows a hard `limit: 0` for the relevant
    quota metric - this means the project/key has no free-tier access
    granted for that specific model at all. Retrying (even after
    waiting) can never succeed in this case, unlike a transient
    per-minute burst limit being hit."""
    return bool(_ZERO_QUOTA_PATTERN.search(error_body))


def parse_retry_delay_seconds(error_body: str, default: float = 5.0) -> float:
    """Extract Google's own suggested wait time from a 429 error body,
    e.g. `"retryDelay": "57s"`. Falls back to `default` if not present."""
    match = _RETRY_DELAY_PATTERN.search(error_body)
    if match:
        return float(match.group(1))
    return default


async def retry_with_backoff(
    fn, *, max_attempts: int = 3, is_rate_limit_error, get_error_body
):
    """Call `fn()` (an async callable with no args); on a rate-limit
    error, sleep for the provider-suggested delay and retry, up to
    `max_attempts` total tries."""
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return await fn()
        except Exception as e: 
            last_exc = e
            if not is_rate_limit_error(e):
                raise
            if attempt == max_attempts - 1:
                raise
            delay = parse_retry_delay_seconds(get_error_body(e))
            await asyncio.sleep(delay)
    raise last_exc  
