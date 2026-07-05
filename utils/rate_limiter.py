"""Concurrency and pacing controls shared by every checker backend.

Login checking is inherently adjacent to credential stuffing / password
spraying. This module exists so every backend throttles itself the same
way by default: a bounded number of in-flight attempts per site plus a
randomized delay between them. This is about being a good, predictable
client during an *authorized* assessment (avoiding self-inflicted lockouts
and WAF trip-wires) -- it is not, and must not become, an evasion feature
set (no proxy rotation, no fingerprint randomization to dodge detection).
"""

from __future__ import annotations

import asyncio
import random


class RateLimiter:
    def __init__(self, concurrency: int = 1, delay_min: float = 0.0, delay_max: float = 0.0):
        self.concurrency = max(1, concurrency)
        self.delay_min = max(0.0, delay_min)
        self.delay_max = max(self.delay_min, delay_max)
        self._semaphore = asyncio.Semaphore(self.concurrency)

    async def throttle(self) -> None:
        if self.delay_max > 0:
            await asyncio.sleep(random.uniform(self.delay_min, self.delay_max))

    def slot(self):
        return self._semaphore

    @classmethod
    def from_website_info(cls, website: dict) -> "RateLimiter":
        def _f(key, default):
            value = website.get(key)
            if value in (None, ""):
                return default
            try:
                return float(value)
            except ValueError:
                return default

        def _i(key, default):
            value = website.get(key)
            if value in (None, ""):
                return default
            try:
                return int(value)
            except ValueError:
                return default

        return cls(
            concurrency=_i("concurrency", 3),
            delay_min=_f("delay_min", 0.0),
            delay_max=_f("delay_max", 0.0),
        )
