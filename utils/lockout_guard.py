"""Account-lockout-aware pacing, shared by every checker backend.

The single biggest way an "advanced" login checker differs from a naive
combo-list loop is that it actively protects the accounts it's testing:
real identity providers lock an account out after N bad passwords in a
rolling window, and a naive tool will happily burn through that threshold
in the first few seconds, locking out a real user and generating a very
loud, very traceable incident for whatever team owns the target.

LockoutGuard enforces two things across a whole site run, regardless of
concurrency:
  1. A minimum spacing between any two attempts against the *same*
     username (independent of the general per-site delay, which paces
     attempts overall but not per-account).
  2. A permanent skip list: once a response for a username matches one of
     the configured `lockout_indicators`, every remaining queued attempt
     for that username is skipped instead of making the lockout worse.
"""

from __future__ import annotations

import asyncio
import time
from typing import Dict, Set


class LockoutGuard:
    def __init__(self, min_interval: float = 0.0, lockout_indicators=None):
        self.min_interval = max(0.0, min_interval)
        self.lockout_indicators = [i.strip() for i in (lockout_indicators or []) if i.strip()]
        self._last_attempt: Dict[str, float] = {}
        self._locked_out: Set[str] = set()
        self._lock = asyncio.Lock()

    def is_locked_out(self, username: str) -> bool:
        return username in self._locked_out

    async def wait_for_slot(self, username: str) -> None:
        """Block until it's safe to attempt `username` again, per min_interval."""
        while True:
            async with self._lock:
                last = self._last_attempt.get(username)
                now = time.monotonic()
                if last is None or (now - last) >= self.min_interval:
                    self._last_attempt[username] = now
                    return
                wait_time = self.min_interval - (now - last)
            await asyncio.sleep(wait_time)

    def observe(self, username: str, result) -> bool:
        """Record a LoginResult for `username`; returns True if it now looks locked out.

        Trusts `result.extra["locked_out"]` when a backend set it (every
        built-in checker classifies lockout explicitly against the raw
        response), falling back to a text search over `result.reason`
        against the configured indicators for anything else.
        """
        locked = bool(getattr(result, "extra", None) and result.extra.get("locked_out"))
        if not locked:
            reason = getattr(result, "reason", "") or ""
            locked = any(indicator.lower() in reason.lower() for indicator in self.lockout_indicators)
        if locked:
            self._locked_out.add(username)
        return locked

    @classmethod
    def from_website_info(cls, website: dict) -> "LockoutGuard":
        def _f(key, default):
            value = website.get(key)
            if value in (None, ""):
                return default
            try:
                return float(value)
            except ValueError:
                return default

        indicators = (website.get("lockout_indicators") or "").split(",")
        return cls(min_interval=_f("lockout_interval", 0.0), lockout_indicators=indicators)
