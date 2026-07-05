import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from checkers.plugins.microsoft365_checker import Microsoft365Checker

# Each test smuggles the desired scenario name in as the POSTed "password"
# field, so a single tiny fake token endpoint can stand in for every
# AADSTS-shaped response without a real Azure AD tenant.
RESPONSES = {
    "success": {"access_token": "fake-token"},
    "bad_password": {"error_description": "AADSTS50126: Invalid username or password\r\n"},
    "mfa": {"error_description": "AADSTS50076: Due to a configuration change... MFA\r\n"},
    "locked": {"error_description": "AADSTS50053: account locked\r\n"},
    "no_such_user": {"error_description": "AADSTS50034: user does not exist\r\n"},
}


async def token_endpoint(request):
    data = await request.post()
    scenario = data.get("password")  # tests smuggle the desired scenario in as the "password"
    return web.json_response(RESPONSES[scenario])


def make_app():
    app = web.Application()
    app.router.add_post("/token", token_endpoint)
    return app


@pytest.fixture
async def server():
    srv = TestServer(make_app())
    await srv.start_server()
    yield srv
    await srv.close()


def make_checker(server):
    website = {
        "login_url": "https://login.microsoftonline.com/common/oauth2/token",
        "tenant": "common",
        "token_endpoint": str(server.make_url("/token")),
    }
    return Microsoft365Checker("O365Test", {"website": website, "headers": {}, "payload": {}})


async def run_attempt(checker, username, password):
    await checker.setup()
    try:
        return await checker.attempt(username, password)
    finally:
        await checker.teardown()


async def test_valid_credentials_returns_success(server):
    result = await run_attempt(make_checker(server), "user@example.com", "success")
    assert result.success is True
    assert "Valid credentials" in result.reason


async def test_invalid_password_aadsts50126(server):
    result = await run_attempt(make_checker(server), "user@example.com", "bad_password")
    assert result.success is False
    assert "AADSTS50126" in result.reason


async def test_mfa_required_is_valid_credentials(server):
    result = await run_attempt(make_checker(server), "user@example.com", "mfa")
    assert result.success is True
    assert "MFA" in result.reason


async def test_locked_out_sets_extra_flag(server):
    result = await run_attempt(make_checker(server), "user@example.com", "locked")
    assert result.success is False
    assert result.extra.get("locked_out") is True


async def test_unknown_user_aadsts50034(server):
    result = await run_attempt(make_checker(server), "ghost@example.com", "no_such_user")
    assert result.success is False
    assert "does not exist" in result.reason
