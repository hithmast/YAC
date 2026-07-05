"""Turns a list of LoginResult objects into the on-disk artifacts users see:
per-site CSV (compatible with the original YAC output format, plus new
Mode/Duration columns), a JSON summary for programmatic consumption, and a
plain-text console summary.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from typing import Iterable, List

logger = logging.getLogger("yac")

FIELDNAMES = ["Username", "Password", "Valid Login", "Reason", "Mode", "Duration"]


def write_csv(results: Iterable, output_file: str) -> None:
    results = list(results)
    out_dir = os.path.dirname(output_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    valid_logins = sum(1 for r in results if r.success)
    total_time = sum(r.duration for r in results)

    with open(output_file, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in results:
            writer.writerow(r.as_row())
        writer.writerow({"Username": f"Execution time: {total_time:.2f} seconds"})
        writer.writerow({"Username": f"Total users: {len(results)}"})
        writer.writerow({"Username": f"Valid logins: {valid_logins}"})

    logger.info("Results saved to %s", output_file)


def build_site_summary(website_name: str, mode: str, results: List) -> dict:
    valid = [r for r in results if r.success]
    return {
        "website": website_name,
        "mode": mode,
        "total_attempts": len(results),
        "valid_logins": len(valid),
        "valid_credentials": [{"username": r.username, "password": r.password} for r in valid],
        "total_duration_seconds": round(sum(r.duration for r in results), 2),
    }


def write_json_summary(site_summaries: List[dict], output_file: str) -> None:
    out_dir = os.path.dirname(output_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_file, "w") as f:
        json.dump({"sites": site_summaries}, f, indent=2)
    logger.info("Summary report saved to %s", output_file)


def _mask_password(password: str) -> str:
    """Shape-preserving mask for terminal/CI-log display.

    Console output (unlike the CSV/JSON results files) tends to end up in
    places with much broader or longer-lived visibility -- CI job logs,
    screen shares, terminal scrollback/history. The full plaintext password
    is already recorded in the results files this summary points at, so the
    console only needs to confirm *that* a credential is valid, not repeat
    the secret itself.
    """
    if len(password) <= 2:
        return "*" * len(password)
    return password[0] + "*" * (len(password) - 2) + password[-1]


def print_console_summary(site_summaries: List[dict]) -> None:
    print("\n" + "=" * 60)
    print("YAC RUN SUMMARY")
    print("=" * 60)
    for summary in site_summaries:
        print(
            f"[{summary['website']}] mode={summary['mode']} "
            f"attempts={summary['total_attempts']} "
            f"valid={summary['valid_logins']} "
            f"time={summary['total_duration_seconds']}s"
        )
        for cred in summary["valid_credentials"]:
            print(f"    -> VALID: {cred['username']} : {_mask_password(cred['password'])}")
    print("=" * 60 + "\n")
