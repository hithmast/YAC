"""Credential-list loading for both supported attack strategies.

strategy=pairs (default): read a Username,Password CSV of known/paired
credentials (credential stuffing / validation of a leaked combo list).

strategy=spray: build the cross product of a username list and a password
list, ordered *wide before deep* -- every username gets password #1 before
anyone gets password #2, and so on. That ordering is what actually keeps a
spray under a typical lockout threshold (N bad attempts per rolling window
per account); combined with LockoutGuard's per-username spacing it mirrors
how real password-spraying tools stay safe against production identity
providers.
"""

from __future__ import annotations

import csv
from typing import Dict, List


def _read_lines(path: str) -> List[str]:
    with open(path, "r") as f:
        return [line.strip() for line in f if line.strip()]


def load_pairs(credentials_file: str) -> List[Dict[str, str]]:
    with open(credentials_file, "r", newline="") as f:
        return list(csv.DictReader(f))


def load_spray(username_list: str, password_list: str) -> List[Dict[str, str]]:
    usernames = _read_lines(username_list)
    passwords = _read_lines(password_list)
    return [
        {"Username": username, "Password": password}
        for password in passwords
        for username in usernames
    ]


def load_credentials(website: dict) -> List[Dict[str, str]]:
    strategy = (website.get("strategy") or "pairs").strip().lower()
    if strategy == "spray":
        username_list = website.get("username_list")
        password_list = website.get("password_list")
        if not username_list or not password_list:
            raise ValueError(
                "strategy=spray requires both 'username_list' and 'password_list' to be set."
            )
        return load_spray(username_list, password_list)
    if strategy != "pairs":
        raise ValueError(f"Unknown strategy '{strategy}'. Valid values: pairs, spray.")
    return load_pairs(website["credentials_file"])
