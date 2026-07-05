import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from checkers.plugins.okta_checker import OktaChecker

# Scenario name -> (http status, json body) for the fake Okta authn endpoint.
RESPONSES = {
    "success": (200, {"status": "SUCCESS"}),
    "mfa": (200, {"status": "MFA_REQUIRED"}),
    "locked": (200, {"status": "LOCKED_OUT"}),
    "bad_creds": (401, {"errorCode": "E0000004", "errorSummary": "Authentication failed"}),
}


async def authn_endpoint(request):
    data = await request.json()
    status, body = RESPONSES[data["password"]]  # tests smuggle the scenario in as the "password"
    return web.json_response(body, status=status)


def make_app():
    app = web.Application()
    app.router.add_post("/authn", authn_endpoint)
    return app


@pytest.fixture
async def server():
    srv = TestServer(make_app())
    await srv.start_server()
    yield srv
    await srv.close()


def make_checker(server):
    website = {
        "login_url": "https://example.okta.com/login",
        "okta_domain": "example.okta.com",
        "authn_url": str(server.make_url("/authn")),
    }
    return OktaChecker("OktaTest", {"website": website, "headers": {}, "payload": {}})


async def run_attempt(checker, username, password):
    await checker.setup()
    try:
        return await checker.attempt(username, password)
    finally:
        await checker.teardown()


def test_missing_okta_domain_raises():
    website = {"login_url": "https://example.okta.com/login"}
    with pytest.raises(ValueError, match="okta_domain"):
        OktaChecker("OktaTest", {"website": website, "headers": {}, "payload": {}})


async def test_success_status(server):
    result = await run_attempt(make_checker(server), "alice", "success")
    assert result.success is True
    assert result.reason == "Valid credentials"


async def test_mfa_required_is_valid_credentials(server):
    result = await run_attempt(make_checker(server), "alice", "mfa")
    assert result.success is True
    assert "MFA" in result.reason


async def test_locked_out_status_sets_extra_flag(server):
    result = await run_attempt(make_checker(server), "alice", "locked")
    assert result.success is False
    assert result.extra.get("locked_out") is True


async def test_invalid_credentials_401(server):
    result = await run_attempt(make_checker(server), "alice", "bad_creds")
    assert result.success is False
    assert result.reason == "Invalid username or password"
