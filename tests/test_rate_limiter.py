import asyncio
import time

from utils.rate_limiter import RateLimiter


async def test_concurrency_is_bounded():
    limiter = RateLimiter(concurrency=2, delay_min=0, delay_max=0)
    in_flight = 0
    max_in_flight = 0
    lock = asyncio.Lock()

    async def task():
        nonlocal in_flight, max_in_flight
        async with limiter.slot():
            async with lock:
                in_flight += 1
                max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0.05)
            async with lock:
                in_flight -= 1

    await asyncio.gather(*(task() for _ in range(6)))
    assert max_in_flight == 2


async def test_throttle_respects_delay_bounds():
    limiter = RateLimiter(concurrency=1, delay_min=0.05, delay_max=0.05)
    start = time.monotonic()
    await limiter.throttle()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.04


def test_from_website_info_defaults():
    limiter = RateLimiter.from_website_info({})
    assert limiter.concurrency == 3
    assert limiter.delay_min == 0.0
    assert limiter.delay_max == 0.0


def test_from_website_info_parses_values():
    limiter = RateLimiter.from_website_info({"concurrency": "10", "delay_min": "1", "delay_max": "2"})
    assert limiter.concurrency == 10
    assert limiter.delay_min == 1.0
    assert limiter.delay_max == 2.0


def test_concurrency_is_clamped_to_at_least_one():
    limiter = RateLimiter(concurrency=0)
    assert limiter.concurrency == 1
