import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from checkers.http_checker import HttpChecker

VALID_USER = "admin"
VALID_PASS = "correct-horse"


async def login_page(request):
    return web.Response(
        text=(
            "<html><body><form method='post' action='/login'>"
            "<input type='hidden' name='csrf_token' value='tok-12345'/>"
            "</form></body></html>"
        ),
        content_type="text/html",
    )


async def login_submit(request):
    data = await request.post()
    if data.get("csrf_token") != "tok-12345":
        return web.Response(text="Invalid CSRF token", status=403)
    username, password = data.get("username"), data.get("password")
    if username == "locked-user":
        return web.Response(text="Account locked due to too many attempts")
    if username == VALID_USER and password == VALID_PASS:
        return web.Response(text="Welcome back, admin! Dashboard loaded.")
    return web.Response(text="Invalid username/password")


async def bot_wall(request):
    return web.Response(text="<div class='g-recaptcha'></div>Please verify you are a human")


def make_app():
    app = web.Application()
    app.router.add_get("/login", login_page)
    app.router.add_post("/login", login_submit)
    app.router.add_get("/bot-login", bot_wall)
    app.router.add_post("/bot-login", bot_wall)
    return app


@pytest.fixture
async def server():
    srv = TestServer(make_app())
    await srv.start_server()
    yield srv
    await srv.close()


def website_info(login_url, **extra):
    website = {
        "login_url": login_url,
        "username_field": "username",
        "password_field": "password",
        "csrf_field": "csrf_token",
        "success_indicators": ["Welcome back", "Dashboard loaded"],
        "failure_indicators": ["Invalid username/password"],
    }
    website.update(extra)
    return {"website": website, "headers": {}, "payload": {}}


async def test_success_with_csrf_token(server):
    url = str(server.make_url("/login"))
    checker = HttpChecker("Test", website_info(url))
    await checker.setup()
    try:
        result = await checker.attempt(VALID_USER, VALID_PASS)
    finally:
        await checker.teardown()
    assert result.success is True
    assert result.reason == "Success"


async def test_failure_for_bad_password(server):
    url = str(server.make_url("/login"))
    checker = HttpChecker("Test", website_info(url))
    await checker.setup()
    try:
        result = await checker.attempt(VALID_USER, "wrong")
    finally:
        await checker.teardown()
    assert result.success is False
    assert result.reason == "Invalid username/password"


async def test_lockout_indicator_sets_extra_flag(server):
    url = str(server.make_url("/login"))
    checker = HttpChecker("Test", website_info(url, lockout_indicators="Account locked"))
    await checker.setup()
    try:
        result = await checker.attempt("locked-user", "whatever")
    finally:
        await checker.teardown()
    assert result.success is False
    assert result.extra.get("locked_out") is True
    assert "Account locked" in result.reason


async def test_bot_protection_detected(server):
    url = str(server.make_url("/bot-login"))
    checker = HttpChecker("Test", website_info(url))
    await checker.setup()
    try:
        result = await checker.attempt(VALID_USER, VALID_PASS)
    finally:
        await checker.teardown()
    assert result.success is False
    assert result.extra.get("blocked") is True
    assert "bot/CAPTCHA" in result.reason


async def test_missing_csrf_token_falls_through_to_forbidden(server):
    url = str(server.make_url("/login"))
    checker = HttpChecker("Test", website_info(url, csrf_field=""))
    await checker.setup()
    try:
        result = await checker.attempt(VALID_USER, VALID_PASS)
    finally:
        await checker.teardown()
    assert result.success is False
    assert "403" in result.reason or "Unknown" in result.reason
