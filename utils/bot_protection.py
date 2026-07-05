"""Detection (never bypass) of CAPTCHA / bot-mitigation walls.

If a target starts serving a CAPTCHA or a bot-mitigation challenge page,
continuing to hammer it with more login attempts is pointless (the
response is no longer a genuine reflection of the credential's validity)
and can escalate an authorized test into something that looks like an
attack on the WAF/CDN vendor rather than the in-scope application. YAC's
job here stops at recognizing that state and reporting it -- solving or
evading the challenge is explicitly out of scope for this tool.
"""

from __future__ import annotations

from typing import Optional

BOT_PROTECTION_MARKERS = [
    "g-recaptcha",
    "recaptcha/api.js",
    "hcaptcha.com",
    "cf-turnstile",
    "cf-chl-bypass",
    "__cf_chl_",
    "attention required! | cloudflare",
    "checking your browser before accessing",
    "distil_r_captcha",
    "px-captcha",
    "please verify you are a human",
    "captcha-delivery.com",
    "akamai bot manager",
]


def detect_bot_protection(content: Optional[str]) -> Optional[str]:
    """Return the matched marker if `content` looks like a CAPTCHA/bot wall, else None."""
    if not content:
        return None
    lowered = content.lower()
    for marker in BOT_PROTECTION_MARKERS:
        if marker in lowered:
            return marker
    return None
