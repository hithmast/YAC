import pytest

from utils.credentials import load_credentials, load_pairs, load_spray


def test_load_pairs(tmp_path):
    combo = tmp_path / "combo.csv"
    combo.write_text("Username,Password\nalice,pw1\nbob,pw2\n")
    rows = load_pairs(str(combo))
    assert rows == [
        {"Username": "alice", "Password": "pw1"},
        {"Username": "bob", "Password": "pw2"},
    ]


def test_load_spray_is_wide_before_deep(tmp_path):
    users = tmp_path / "users.txt"
    users.write_text("alice\nbob\ncarol\n")
    passwords = tmp_path / "passwords.txt"
    passwords.write_text("pw1\npw2\n")

    rows = load_spray(str(users), str(passwords))

    assert [(r["Username"], r["Password"]) for r in rows] == [
        ("alice", "pw1"), ("bob", "pw1"), ("carol", "pw1"),
        ("alice", "pw2"), ("bob", "pw2"), ("carol", "pw2"),
    ]


def test_load_spray_skips_blank_lines(tmp_path):
    users = tmp_path / "users.txt"
    users.write_text("alice\n\nbob\n  \n")
    passwords = tmp_path / "passwords.txt"
    passwords.write_text("pw1\n\n")

    rows = load_spray(str(users), str(passwords))
    assert [(r["Username"], r["Password"]) for r in rows] == [("alice", "pw1"), ("bob", "pw1")]


def test_load_credentials_dispatches_to_pairs_by_default(tmp_path):
    combo = tmp_path / "combo.csv"
    combo.write_text("Username,Password\nalice,pw1\n")
    rows = load_credentials({"credentials_file": str(combo)})
    assert rows == [{"Username": "alice", "Password": "pw1"}]


def test_load_credentials_dispatches_to_spray(tmp_path):
    users = tmp_path / "users.txt"
    users.write_text("alice\n")
    passwords = tmp_path / "passwords.txt"
    passwords.write_text("pw1\n")
    rows = load_credentials(
        {"strategy": "spray", "username_list": str(users), "password_list": str(passwords)}
    )
    assert rows == [{"Username": "alice", "Password": "pw1"}]


def test_load_credentials_spray_missing_lists_raises():
    with pytest.raises(ValueError, match="username_list"):
        load_credentials({"strategy": "spray"})


def test_load_credentials_unknown_strategy_raises(tmp_path):
    combo = tmp_path / "combo.csv"
    combo.write_text("Username,Password\n")
    with pytest.raises(ValueError, match="Unknown strategy"):
        load_credentials({"strategy": "bogus", "credentials_file": str(combo)})
