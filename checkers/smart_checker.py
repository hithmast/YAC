"""AI-agent login checker built on browser-use.

`browser`/Playwright mode still needs you to know (or guess at) CSS
selectors. Plenty of modern web apps don't cooperate with that: login is a
multi-step wizard (email screen, then a separate password screen), fields
are inside a shadow DOM, or a cookie-consent banner has to be dismissed
first. For those, mode='smart' hands the page to a browser-use `Agent`,
which drives a real browser and uses an LLM to figure out, screen by
screen, how to reach a submitted login form -- the same way a human tester
would.

This mode is deliberately the last resort: it is slower and costs LLM
tokens, so `requests` and `browser` should be preferred whenever their
selector/indicator-based approach works.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Optional

from .base import BaseChecker, LoginResult
from utils.urlutil import reverse_url_encoding

logger = logging.getLogger("yac")

DEFAULT_TASK_TEMPLATE = (
    "Go to {login_url}. Attempt to log in to this website using the exact "
    "credentials: username/email = \"{username}\", password = \"{password}\". "
    "Dismiss any cookie-consent or interstitial dialogs first if needed. "
    "If the site asks for username/email and password on separate screens, "
    "complete both steps. Do NOT try any credentials other than the ones given. "
    "Do NOT attempt to solve any CAPTCHA or bypass any security control -- if one "
    "blocks you, stop and report it. After submitting, determine whether the "
    "login succeeded (e.g. you reached a dashboard/account/home page, a logout "
    "control is visible, or a welcome message appears) or failed (e.g. an "
    "invalid-credentials error is shown, or you are still on the login form). "
    "Your final answer MUST be exactly one line formatted as either "
    "'RESULT: SUCCESS' or 'RESULT: FAILURE: <short reason>'."
)

_RESULT_RE = re.compile(r"RESULT:\s*(SUCCESS|FAILURE)\s*:?\s*(.*)", re.IGNORECASE)


class SmartChecker(BaseChecker):
    """browser-use powered checker: an LLM-driven agent performs the login."""

    mode_name = "smart"

    def __init__(self, website_name, website_info):
        super().__init__(website_name, website_info)
        self.headless = self._get_bool("headless", True)
        self.llm_provider = (self._get("llm_provider") or "openai").lower()
        self.llm_model = self._get("llm_model") or "gpt-4.1-mini"
        self.task_template = self._get("task_template") or DEFAULT_TASK_TEMPLATE
        self.max_steps = self._get_int("max_steps", 25)
        self._browser_session = None
        self._llm = None

    def _build_llm(self):
        try:
            from browser_use import llm as bu_llm
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "browser-use is required for mode='smart'. Install it with:\n"
                "  pip install browser-use && playwright install chromium"
            ) from exc

        provider_map = {
            "openai": "ChatOpenAI",
            "anthropic": "ChatAnthropic",
            "google": "ChatGoogle",
            "groq": "ChatGroq",
        }
        class_name = provider_map.get(self.llm_provider)
        if class_name is None or not hasattr(bu_llm, class_name):
            raise RuntimeError(
                f"Unsupported or unavailable llm_provider '{self.llm_provider}' for mode='smart'. "
                f"Supported: {sorted(provider_map)}"
            )
        llm_cls = getattr(bu_llm, class_name)
        return llm_cls(model=self.llm_model)

    async def setup(self) -> None:
        try:
            from browser_use import Browser
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "browser-use is required for mode='smart'. Install it with:\n"
                "  pip install browser-use && playwright install chromium"
            ) from exc

        self._llm = self._build_llm()
        self._browser_session = Browser(headless=self.headless)

    async def teardown(self) -> None:
        if self._browser_session is not None:
            try:
                await self._browser_session.close()
            except Exception:  # pragma: no cover - best-effort cleanup
                logger.debug("Ignoring error while closing browser-use session", exc_info=True)
            self._browser_session = None

    def _parse_result(self, text: str) -> Optional[tuple]:
        if not text:
            return None
        match = _RESULT_RE.search(text)
        if not match:
            return None
        verdict, reason = match.group(1).upper(), match.group(2).strip()
        return verdict == "SUCCESS", (reason or verdict.title())

    async def attempt(self, username: str, password: str) -> LoginResult:
        start = time.monotonic()
        from browser_use import Agent

        task = self.task_template.format(
            login_url=reverse_url_encoding(self.website.get("login_url", "")),
            username=username,
            password=password,
        )

        try:
            agent = Agent(task=task, llm=self._llm, browser=self._browser_session)
            history = await agent.run(max_steps=self.max_steps)

            final_text = ""
            if hasattr(history, "final_result"):
                final_text = history.final_result() or ""
            if not final_text:
                final_text = str(history)

            parsed = self._parse_result(final_text)
            if parsed is None:
                return LoginResult(
                    username, password, False,
                    f"Agent did not return a parseable RESULT line: {final_text[:200]!r}",
                    time.monotonic() - start, self.mode_name,
                )
            success, reason = parsed
            reason_lower = reason.lower()
            extra = {}
            if any(term in reason_lower for term in ("captcha", "bot detection", "bot check", "blocked")):
                extra["blocked"] = True
            if not success and "locked" in reason_lower:
                extra["locked_out"] = True
            return LoginResult(
                username, password, success, reason,
                time.monotonic() - start, self.mode_name, extra,
            )
        except Exception as exc:
            return LoginResult(
                username, password, False, f"Exception: {exc}",
                time.monotonic() - start, self.mode_name,
            )
