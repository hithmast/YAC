"""Real-browser login checker built on Playwright.

Modern web apps often render their login form client-side, mint CSRF/anti-bot
tokens via JavaScript, or gate the submit button on client-side validation.
A plain HTTP POST checker can't reproduce any of that. This backend drives
an actual (headless by default) Chromium instance so the page's own JS runs
exactly as it would for a real user.

Each credential pair gets a fresh, isolated browser context (its own cookie
jar/local storage) so attempts never leak session state into one another.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from .base import BaseChecker, LoginResult
from utils.bot_protection import detect_bot_protection
from utils.urlutil import reverse_url_encoding

logger = logging.getLogger("yac")

DEFAULT_USERNAME_SELECTORS = [
    "input[name='username']", "input[name='email']", "input[type='email']",
    "#username", "#email", "input[autocomplete='username']",
]
DEFAULT_PASSWORD_SELECTORS = [
    "input[name='password']", "input[type='password']", "#password",
    "input[autocomplete='current-password']",
]
DEFAULT_SUBMIT_SELECTORS = [
    "button[type='submit']", "input[type='submit']", "button:has-text('Log in')",
    "button:has-text('Sign in')",
]


class BrowserChecker(BaseChecker):
    """Playwright-driven checker for JavaScript-rendered login forms."""

    mode_name = "browser"

    def __init__(self, website_name, website_info):
        super().__init__(website_name, website_info)
        self.headless = self._get_bool("headless", True)
        self.nav_timeout_ms = self._get_float("timeout", 20.0) * 1000
        self.username_selector = self._get("username_selector")
        self.password_selector = self._get("password_selector")
        self.submit_selector = self._get("submit_selector")
        self.success_selector = self._get("success_selector")
        self.failure_selector = self._get("failure_selector")
        self.success_url_contains = [
            s.strip() for s in (self._get("success_url_contains") or "").split(",") if s.strip()
        ]
        self.failure_url_contains = [
            s.strip() for s in (self._get("failure_url_contains") or "").split(",") if s.strip()
        ]
        self.lockout_indicators = [
            s.strip() for s in (self._get("lockout_indicators") or "").split(",") if s.strip()
        ]
        self.proxy = self._get("proxy") or None
        self.user_agent = self.headers.get("user-agent") or self.headers.get("User-Agent")

        self._playwright = None
        self._browser = None

    async def setup(self) -> None:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover - depends on optional install
            raise RuntimeError(
                "Playwright is required for mode='browser'. Install it with:\n"
                "  pip install playwright && playwright install chromium"
            ) from exc

        self._playwright = await async_playwright().start()
        launch_kwargs = {"headless": self.headless}
        if self.proxy:
            launch_kwargs["proxy"] = {"server": self.proxy}
        self._browser = await self._playwright.chromium.launch(**launch_kwargs)

    async def teardown(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def _first_matching(self, page, selectors) -> Optional[str]:
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if await locator.count() > 0:
                    return selector
            except Exception:
                continue
        return None

    async def attempt(self, username: str, password: str) -> LoginResult:
        start = time.monotonic()
        context_kwargs = {}
        if self.user_agent:
            context_kwargs["user_agent"] = self.user_agent
        context = await self._browser.new_context(**context_kwargs)
        page = await context.new_page()
        page.set_default_timeout(self.nav_timeout_ms)

        try:
            login_url = reverse_url_encoding(self.website["login_url"])
            await page.goto(login_url, wait_until="domcontentloaded")

            user_selector = self.username_selector or await self._first_matching(
                page, DEFAULT_USERNAME_SELECTORS
            )
            pass_selector = self.password_selector or await self._first_matching(
                page, DEFAULT_PASSWORD_SELECTORS
            )
            if not user_selector or not pass_selector:
                return LoginResult(
                    username, password, False,
                    "Could not locate username/password fields (set username_selector / "
                    "password_selector in config, or try mode=smart)",
                    time.monotonic() - start, self.mode_name,
                )

            await page.fill(user_selector, username)
            await page.fill(pass_selector, password)

            submit_selector = self.submit_selector or await self._first_matching(
                page, DEFAULT_SUBMIT_SELECTORS
            )
            try:
                if submit_selector:
                    async with page.expect_navigation(wait_until="domcontentloaded", timeout=self.nav_timeout_ms):
                        await page.click(submit_selector)
                else:
                    async with page.expect_navigation(wait_until="domcontentloaded", timeout=self.nav_timeout_ms):
                        await page.press(pass_selector, "Enter")
            except Exception:
                # SPA logins frequently update the DOM without a full navigation.
                await page.wait_for_timeout(min(self.nav_timeout_ms, 3000))

            final_url = page.url
            content = await page.content()

            marker = detect_bot_protection(content)
            if marker:
                return LoginResult(
                    username, password, False,
                    f"Blocked by bot/CAPTCHA protection ({marker})",
                    time.monotonic() - start, self.mode_name, {"url": final_url, "blocked": True},
                )

            for indicator in self.lockout_indicators:
                if indicator in content:
                    return LoginResult(
                        username, password, False, f"Account locked out ({indicator})",
                        time.monotonic() - start, self.mode_name,
                        {"url": final_url, "locked_out": True},
                    )

            for indicator in self.success_url_contains:
                if indicator in final_url:
                    return LoginResult(
                        username, password, True, "Success (redirect URL match)",
                        time.monotonic() - start, self.mode_name, {"url": final_url},
                    )
            for indicator in self.failure_url_contains:
                if indicator in final_url:
                    return LoginResult(
                        username, password, False, f"Failure (redirect URL: {indicator})",
                        time.monotonic() - start, self.mode_name, {"url": final_url},
                    )

            if self.success_selector and await page.locator(self.success_selector).count() > 0:
                return LoginResult(
                    username, password, True, "Success (DOM element matched)",
                    time.monotonic() - start, self.mode_name, {"url": final_url},
                )
            if self.failure_selector and await page.locator(self.failure_selector).count() > 0:
                error_text = await page.locator(self.failure_selector).first.inner_text()
                return LoginResult(
                    username, password, False, error_text.strip() or "Failure (DOM element matched)",
                    time.monotonic() - start, self.mode_name, {"url": final_url},
                )

            for indicator in self.website.get("success_indicators", []):
                indicator = indicator.strip()
                if indicator and indicator in content:
                    return LoginResult(
                        username, password, True, "Success",
                        time.monotonic() - start, self.mode_name, {"url": final_url},
                    )
            for indicator in self.website.get("failure_indicators", []):
                indicator = indicator.strip()
                if indicator and indicator in content:
                    return LoginResult(
                        username, password, False, indicator,
                        time.monotonic() - start, self.mode_name, {"url": final_url},
                    )

            return LoginResult(
                username, password, False, "Unknown (no indicator matched after page load)",
                time.monotonic() - start, self.mode_name, {"url": final_url},
            )
        except Exception as exc:
            # Exception class name only, never str(exc) -- see http_checker.py.
            return LoginResult(
                username, password, False, f"Exception: {type(exc).__name__}",
                time.monotonic() - start, self.mode_name,
            )
        finally:
            await context.close()
