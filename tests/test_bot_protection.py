from utils.bot_protection import detect_bot_protection


def test_detects_recaptcha():
    assert detect_bot_protection('<div class="g-recaptcha" data-sitekey="x"></div>') == "g-recaptcha"


def test_detects_cloudflare_challenge_case_insensitive():
    marker = detect_bot_protection("<title>Attention Required! | Cloudflare</title>")
    assert marker == "attention required! | cloudflare"


def test_returns_none_for_clean_page():
    assert detect_bot_protection("<html><body>Welcome back!</body></html>") is None


def test_returns_none_for_empty_content():
    assert detect_bot_protection("") is None
    assert detect_bot_protection(None) is None
