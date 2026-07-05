"""Resume support for large campaigns.

A spray against a big username/password cross-product, or a huge stuffing
combo list, can run for hours; a crash or Ctrl+C shouldn't mean starting
over. When --resume is passed, main.py consults `load_done()` to skip
(username, password) pairs already recorded for this site, and streams
newly completed ones through a CheckpointWriter as it goes (flushed after
every write so a hard kill loses at most the in-flight attempt).
"""

from __future__ import annotations

import json
import os
from typing import Set, Tuple


def checkpoint_path(state_dir: str, website_name: str) -> str:
    safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in website_name)
    return os.path.join(state_dir, f"{safe_name}.jsonl")


def load_done(path: str) -> Set[Tuple[str, str]]:
    done: Set[Tuple[str, str]] = set()
    if not os.path.exists(path):
        return done
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                done.add((obj["username"], obj["password"]))
            except (json.JSONDecodeError, KeyError):
                continue
    return done


class CheckpointWriter:
    def __init__(self, path: str):
        self.path = path
        out_dir = os.path.dirname(path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        self._fh = open(path, "a")

    def record(self, username: str, password: str) -> None:
        self._fh.write(json.dumps({"username": username, "password": password}) + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()
