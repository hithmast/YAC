from .base import BaseChecker, LoginResult
from .http_checker import HttpChecker
from .browser_checker import BrowserChecker
from .smart_checker import SmartChecker
from .plugins import Microsoft365Checker, OktaChecker

CHECKER_REGISTRY = {
    "requests": HttpChecker,
    "http": HttpChecker,
    "browser": BrowserChecker,
    "playwright": BrowserChecker,
    "smart": SmartChecker,
    "browser-use": SmartChecker,
    "o365": Microsoft365Checker,
    "microsoft365": Microsoft365Checker,
    "azuread": Microsoft365Checker,
    "okta": OktaChecker,
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
    "Microsoft365Checker",
    "OktaChecker",
    "CHECKER_REGISTRY",
    "get_checker_class",
]
