import time

from checkers.base import LoginResult
from utils.lockout_guard import LockoutGuard


def test_observe_flags_via_extra_locked_out():
    guard = LockoutGuard()
    result = LoginResult("alice", "pw", False, "some message", extra={"locked_out": True})
    assert guard.observe("alice", result) is True
    assert guard.is_locked_out("alice")


def test_observe_flags_via_text_indicator_fallback():
    guard = LockoutGuard(lockout_indicators=["Account locked"])
    result = LoginResult("bob", "pw", False, "Account locked (too many attempts)")
    assert guard.observe("bob", result) is True
    assert guard.is_locked_out("bob")


def test_observe_does_not_flag_normal_failure():
    guard = LockoutGuard(lockout_indicators=["Account locked"])
    result = LoginResult("carol", "pw", False, "Invalid password")
    assert guard.observe("carol", result) is False
    assert not guard.is_locked_out("carol")


def test_lockout_is_per_username():
    guard = LockoutGuard()
    guard.observe("alice", LoginResult("alice", "pw", False, "x", extra={"locked_out": True}))
    assert guard.is_locked_out("alice")
    assert not guard.is_locked_out("bob")


async def test_wait_for_slot_enforces_minimum_interval():
    guard = LockoutGuard(min_interval=0.1)
    start = time.monotonic()
    await guard.wait_for_slot("alice")
    await guard.wait_for_slot("alice")
    elapsed = time.monotonic() - start
    assert elapsed >= 0.09


async def test_wait_for_slot_independent_per_username():
    guard = LockoutGuard(min_interval=0.2)
    start = time.monotonic()
    await guard.wait_for_slot("alice")
    await guard.wait_for_slot("bob")
    elapsed = time.monotonic() - start
    assert elapsed < 0.1


def test_from_website_info_parses_indicators_and_interval():
    guard = LockoutGuard.from_website_info(
        {"lockout_interval": "5", "lockout_indicators": "Account locked, Too many attempts"}
    )
    assert guard.min_interval == 5.0
    assert guard.lockout_indicators == ["Account locked", "Too many attempts"]
