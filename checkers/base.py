"""Shared interface and result model for all login-checking backends."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger("yac")


@dataclass
class LoginResult:
    """Outcome of a single login attempt, regardless of which backend produced it."""

    username: str
    password: str
    success: bool
    reason: str
    duration: float = 0.0
    mode: str = "unknown"
    extra: Dict[str, Any] = field(default_factory=dict)

    def as_row(self) -> Dict[str, str]:
        return {
            "Username": self.username,
            "Password": self.password,
            "Valid Login": "Yes" if self.success else "No",
            "Reason": self.reason,
            "Mode": self.mode,
            "Duration": f"{self.duration:.2f}",
        }


class BaseChecker:
    """Common lifecycle for a website checker: setup once, attempt many, teardown once.

    Subclasses implement `attempt`. `setup`/`teardown` let backends that need
    a persistent resource (an HTTP session, a browser process) amortize that
    cost across every credential pair instead of paying it per attempt.
    """

    mode_name = "base"

    def __init__(self, website_name: str, website_info: Dict[str, Any]):
        self.website_name = website_name
        self.info = website_info
        self.website: Dict[str, Any] = website_info.get("website", {})
        self.headers: Dict[str, str] = website_info.get("headers", {})
        self.payload: Dict[str, str] = website_info.get("payload", {})

    async def setup(self) -> None:
        """Called once before any attempts are made."""

    async def teardown(self) -> None:
        """Called once after all attempts complete (success, failure, or interruption)."""

    async def attempt(self, username: str, password: str) -> LoginResult:
        raise NotImplementedError

    async def __aenter__(self) -> "BaseChecker":
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.teardown()

    def _get(self, key: str, default: Optional[Any] = None) -> Any:
        return self.website.get(key, default)

    def _get_bool(self, key: str, default: bool = False) -> bool:
        value = self.website.get(key)
        if value is None:
            return default
        return str(value).strip().lower() in ("1", "true", "yes", "on")

    def _get_float(self, key: str, default: float) -> float:
        value = self.website.get(key)
        if value is None or value == "":
            return default
        try:
            return float(value)
        except ValueError:
            return default

    def _get_int(self, key: str, default: int) -> int:
        value = self.website.get(key)
        if value is None or value == "":
            return default
        try:
            return int(value)
        except ValueError:
            return default
