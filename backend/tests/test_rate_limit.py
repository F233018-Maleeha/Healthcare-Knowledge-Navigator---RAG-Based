import time

import pytest

from app.core.rate_limit import RateLimiter, is_permanent_zero_quota, parse_retry_delay_seconds, retry_with_backoff


@pytest.mark.asyncio
async def test_rate_limiter_allows_calls_under_the_limit_without_delay():
    limiter = RateLimiter(max_per_minute=5)
    start = time.monotonic()
    for _ in range(5):
        await limiter.acquire()
    elapsed = time.monotonic() - start
    assert elapsed < 1.0  # should not have had to wait at all


@pytest.mark.asyncio
async def test_rate_limiter_blocks_the_6th_call_within_the_window():
    limiter = RateLimiter(max_per_minute=2)
    # Manually seed two recent timestamps to simulate calls already made.
    limiter._timestamps.append(time.monotonic())
    limiter._timestamps.append(time.monotonic())

    start = time.monotonic()

    async def timed_acquire():
        await limiter.acquire()

    # Patch sleep duration expectation indirectly: we just check it *tries*
    # to wait (i.e. does not return instantly) rather than sleeping a full
    # minute in the test.
    import asyncio
    task = asyncio.wait_for(timed_acquire(), timeout=0.05)
    with pytest.raises(asyncio.TimeoutError):
        await task


def test_parse_retry_delay_extracts_seconds():
    body = '{"error": {"details": [{"retryDelay": "57s"}]}}'
    assert parse_retry_delay_seconds(body) == 57.0


def test_parse_retry_delay_falls_back_to_default_when_absent():
    assert parse_retry_delay_seconds("no delay info here", default=3.0) == 3.0


def test_zero_quota_detected_from_real_gemini_error_shape():
    body = (
        '{"error": {"code": 429, "message": "quota exceeded", '
        '"details": [{"@type": "type.googleapis.com/google.rpc.QuotaFailure", '
        '"violations": [{"quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests", '
        '"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}}'
        '\n* Quota exceeded for metric: ..., limit: 0, model: gemini-2.0-flash'
    )
    assert is_permanent_zero_quota(body) is True


def test_zero_quota_not_falsely_detected_on_a_real_nonzero_limit():
    body = '"limit": 15, "remaining": 0'
    assert is_permanent_zero_quota(body) is False


@pytest.mark.asyncio
async def test_retry_with_backoff_retries_then_succeeds():
    attempts = {"count": 0}

    async def flaky():
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise RuntimeError('{"retryDelay": "0.01s"}')
        return "ok"

    result = await retry_with_backoff(
        flaky, max_attempts=3,
        is_rate_limit_error=lambda e: True,
        get_error_body=lambda e: str(e),
    )
    assert result == "ok"
    assert attempts["count"] == 2


@pytest.mark.asyncio
async def test_retry_with_backoff_reraises_non_rate_limit_errors_immediately():
    async def always_fails():
        raise ValueError("not a rate limit issue")

    with pytest.raises(ValueError):
        await retry_with_backoff(
            always_fails, max_attempts=3,
            is_rate_limit_error=lambda e: False,
            get_error_body=lambda e: str(e),
        )
