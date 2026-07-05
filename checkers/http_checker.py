"""Async HTTP form-login checker.

This is the successor to the original `requests`-based flow: it keeps the
"fast path" for classic server-rendered login forms but adds the things
that trip up real-world targets -- CSRF token auto-discovery, cookie/session
handling across the GET-then-POST dance, redirect-chain inspection, retries
with backoff, and proxy support.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Optional

from .base import BaseChecker, LoginResult
from utils.bot_protection import detect_bot_protection
from utils.urlutil import reverse_url_encoding

try:
    import aiohttp
except ImportError:  # pragma: no cover - optional dependency
    aiohttp = None

logger = logging.getLogger("yac")

_CSRF_INPUT_RE = re.compile(
    r'<input[^>]+name=["\'](?P<name>[^"\']*(?:csrf|token|authenticity)[^"\']*)["\'][^>]*value=["\'](?P<value>[^"\']*)["\']',
    re.IGNORECASE,
)
_CSRF_META_RE = re.compile(
    r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\'](?P<value>[^"\']*)["\']',
    re.IGNORECASE,
)


class HttpChecker(BaseChecker):
    """Plain requests/aiohttp based checker for classic HTML form logins."""

    mode_name = "requests"

    def __init__(self, website_name, website_info):
        super().__init__(website_name, website_info)
        self.timeout = self._get_float("timeout", 15.0)
        self.max_retries = self._get_int("max_retries", 2)
        self.retry_backoff = self._get_float("retry_backoff", 1.5)
        self.proxy = self._get("proxy") or None
        self.username_field = self._get("username_field", "username")
        self.password_field = self._get("password_field", "password")
        self.csrf_field = self._get("csrf_field")
        self.csrf_fetch_url = self._get("csrf_fetch_url") or self._get("login_url")
        self.success_url_contains = [
            s.strip() for s in (self._get("success_url_contains") or "").split(",") if s.strip()
        ]
        self.failure_url_contains = [
            s.strip() for s in (self._get("failure_url_contains") or "").split(",") if s.strip()
        ]
        self._session: Optional["aiohttp.ClientSession"] = None

    async def setup(self) -> None:
        if aiohttp is None:
            raise RuntimeError(
                "aiohttp is required for mode='requests'. Install it with:\n"
                "  pip install -r requirements.txt"
            )
        self._session = aiohttp.ClientSession(
            headers=self.headers or None,
            timeout=aiohttp.ClientTimeout(total=self.timeout),
        )

    async def teardown(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def _fetch_csrf_token(self) -> Optional[str]:
        if not self.csrf_field or not self.csrf_fetch_url:
            return None
        try:
            async with self._session.get(
                reverse_url_encoding(self.csrf_fetch_url), proxy=self.proxy
            ) as resp:
                body = await resp.text()
        except Exception as exc:  # pragma: no cover - network dependent
            logger.debug("CSRF pre-fetch failed for %s: %s", self.website_name, exc)
            return None

        match = _CSRF_INPUT_RE.search(body) or _CSRF_META_RE.search(body)
        if match:
            return match.group("value")
        return None

    async def _post_once(self, username: str, password: str):
        payload = {self.username_field: username, self.password_field: password}
        payload.update(self.payload)

        if self.csrf_field:
            token = await self._fetch_csrf_token()
            if token:
                payload[self.csrf_field] = token

        login_url = reverse_url_encoding(self.website["login_url"])
        return await self._session.post(
            login_url,
            data=payload,
            proxy=self.proxy,
            allow_redirects=True,
        )

    async def attempt(self, username: str, password: str) -> LoginResult:
        start = time.monotonic()
        success_indicators = self.website.get("success_indicators", [])
        failure_indicators = self.website.get("failure_indicators", [])
        lockout_indicators = [
            i.strip() for i in (self._get("lockout_indicators") or "").split(",") if i.strip()
        ]

        last_exc: Optional[Exception] = None
        for retry in range(self.max_retries + 1):
            try:
                async with await self._post_once(username, password) as response:
                    body = await response.text()
                    final_url = str(response.url)

                    marker = detect_bot_protection(body)
                    if marker:
                        return LoginResult(
                            username, password, False,
                            f"Blocked by bot/CAPTCHA protection ({marker})",
                            time.monotonic() - start, self.mode_name,
                            {"status": response.status, "url": final_url, "blocked": True},
                        )

                    for indicator in lockout_indicators:
                        if indicator in body:
                            return LoginResult(
                                username, password, False,
                                f"Account locked out ({indicator})",
                                time.monotonic() - start, self.mode_name,
                                {"status": response.status, "url": final_url, "locked_out": True},
                            )

                    for indicator in self.success_url_contains:
                        if indicator in final_url:
                            return LoginResult(
                                username, password, True, "Success (redirect URL match)",
                                time.monotonic() - start, self.mode_name,
                                {"status": response.status, "url": final_url},
                            )
                    for indicator in self.failure_url_contains:
                        if indicator in final_url:
                            return LoginResult(
                                username, password, False, f"Failure (redirect URL: {indicator})",
                                time.monotonic() - start, self.mode_name,
                                {"status": response.status, "url": final_url},
                            )

                    for indicator in success_indicators:
                        indicator = indicator.strip()
                        if indicator and indicator in body:
                            return LoginResult(
                                username, password, True, "Success",
                                time.monotonic() - start, self.mode_name,
                                {"status": response.status, "url": final_url},
                            )
                    for indicator in failure_indicators:
                        indicator = indicator.strip()
                        if indicator and indicator in body:
                            return LoginResult(
                                username, password, False, indicator,
                                time.monotonic() - start, self.mode_name,
                                {"status": response.status, "url": final_url},
                            )

                    if response.status >= 500 and retry < self.max_retries:
                        await asyncio.sleep(self.retry_backoff * (retry + 1))
                        continue

                    return LoginResult(
                        username, password, False,
                        f"Unknown (status {response.status}, no indicator matched)",
                        time.monotonic() - start, self.mode_name,
                        {"status": response.status, "url": final_url},
                    )
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_exc = exc
                if retry < self.max_retries:
                    await asyncio.sleep(self.retry_backoff * (retry + 1))
                    continue

        return LoginResult(
            # Exception class name only, never str(last_exc): some HTTP client
            # exceptions echo request details (URL, headers) back in their
            # message, which is a route the submitted credentials must never
            # leak through into logs/results.
            username, password, False, f"Exception: {type(last_exc).__name__}",
            time.monotonic() - start, self.mode_name,
        )
