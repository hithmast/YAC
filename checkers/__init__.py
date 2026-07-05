from .base import BaseChecker, LoginResult
from .http_checker import HttpChecker
from .browser_checker import BrowserChecker
from .smart_checker import SmartChecker

CHECKER_REGISTRY = {
    "requests": HttpChecker,
    "http": HttpChecker,
    "browser": BrowserChecker,
    "playwright": BrowserChecker,
    "smart": SmartChecker,
    "browser-use": SmartChecker,
}


def get_checker_class(mode: str):
    key = (mode or "requests").strip().lower()
    if key not in CHECKER_REGISTRY:
        raise ValueError(
            f"Unknown checker mode '{mode}'. Valid modes: {sorted(set(CHECKER_REGISTRY))}"
        )
    return CHECKER_REGISTRY[key]


__all__ = [
    "BaseChecker",
    "LoginResult",
    "HttpChecker",
    "BrowserChecker",
    "SmartChecker",
    "CHECKER_REGISTRY",
    "get_checker_class",
]
