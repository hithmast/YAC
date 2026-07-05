"""Protocol-aware checker for Okta (mode=okta).

Okta's own Authentication API (`POST /api/v1/authn`) returns a structured
JSON `status` field instead of an HTML page to scrape, so, like the
Microsoft 365 plugin, this classifies outcomes far more precisely than a
generic text-indicator match: a "MFA_REQUIRED" status means the password
was correct even though the sign-in isn't complete, while a 401 with
errorCode E0000004 means the credentials themselves were wrong.

Reference: https://developer.okta.com/docs/reference/api/authn/
"""

from __future__ import annotations

import time
from typing import Optional

from ..base import BaseChecker, LoginResult

try:
    import aiohttp
except ImportError:  # pragma: no cover - optional dependency
    aiohttp = None

# status -> (success, label). success=True means the password was correct
# even though the primary-auth transaction didn't fully complete.
STATUS_MAP = {
    "SUCCESS": (True, "Valid credentials"),
    "MFA_REQUIRED": (True, "Valid credentials, MFA required"),
    "MFA_CHALLENGE": (True, "Valid credentials, MFA challenge required"),
    "MFA_ENROLL": (True, "Valid credentials, MFA enrollment required"),
    "MFA_ENROLL_ACTIVATE": (True, "Valid credentials, MFA enrollment activation required"),
    "PASSWORD_EXPIRED": (True, "Valid credentials, password expired"),
    "PASSWORD_WARN": (True, "Valid credentials, password expiring soon"),
    "LOCKED_OUT": (False, "Account locked out"),
    "PASSWORD_RESET": (True, "Valid credentials, password reset required"),
}

ERROR_CODE_MAP = {
    "E0000004": "Invalid username or password",
    "E0000047": "Rate limited by Okta API",
    "E0000006": "Insufficient permissions / access denied",
}


class OktaChecker(BaseChecker):
    """Okta Authentication API checker (mode=okta)."""

    mode_name = "okta"

    def __init__(self, website_name, website_info):
        super().__init__(website_name, website_info)
        domain = self._get("okta_domain")
        if not domain:
            raise ValueError(
                f"[{website_name}] mode=okta requires 'okta_domain' "
                "(e.g. okta_domain = yourorg.okta.com)"
            )
        self.okta_domain = domain.strip().rstrip("/")
        self.timeout = self._get_float("timeout", 15.0)
        self.proxy = self._get("proxy") or None
        # Overridable so tests (and non-standard deployments) can point this
        # at something other than a real https://<domain>/api/v1/authn.
        self.authn_url = self._get("authn_url") or f"https://{self.okta_domain}/api/v1/authn"
        self._session: Optional["aiohttp.ClientSession"] = None

    async def setup(self) -> None:
        if aiohttp is None:
            raise RuntimeError(
                "aiohttp is required for mode='okta'. Install it with:\n"
                "  pip install -r requirements.txt"
            )
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))

    async def teardown(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def attempt(self, username: str, password: str) -> LoginResult:
        start = time.monotonic()
        url = self.authn_url
        payload = {"username": username, "password": password, "options": {"warnBeforePasswordExpired": True}}
        headers = {"Accept": "application/json", "Content-Type": "application/json"}

        try:
            async with self._session.post(
                url, json=payload, headers=headers, proxy=self.proxy
            ) as response:
                body = await response.json(content_type=None)
        except Exception as exc:
            # Exception class name only, never str(exc) -- see http_checker.py.
            return LoginResult(
                username, password, False, f"Exception: {type(exc).__name__}",
                time.monotonic() - start, self.mode_name,
            )

        if response.status == 200:
            status = body.get("status", "UNKNOWN")
            success, label = STATUS_MAP.get(status, (False, f"Unknown status: {status}"))
            extra = {"okta_status": status}
            if status == "LOCKED_OUT":
                extra["locked_out"] = True
            return LoginResult(
                username, password, success, label,
                time.monotonic() - start, self.mode_name, extra,
            )

        error_code = body.get("errorCode", "")
        reason = ERROR_CODE_MAP.get(error_code, body.get("errorSummary") or f"HTTP {response.status}")
        return LoginResult(
            username, password, False, reason,
            time.monotonic() - start, self.mode_name, {"errorCode": error_code},
        )
