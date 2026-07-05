"""YAC (Yes Another Checker) -- multi-site smart login checker.

Three interchangeable backends, selected per-website via `mode` in
websites_config.ini:

  requests  - fast async HTTP POST checker for classic server-rendered forms
  browser   - real (Playwright) headless browser for JS-rendered forms
  smart     - browser-use AI agent for multi-step / highly dynamic modern SPAs

See README.md for the full config schema and an authorized-use disclaimer.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import os
import sys
from typing import Dict, List

from checkers import get_checker_class
from checkers.base import LoginResult
from utils import parser as config_parser
from utils import reporter
from utils.logger import setup_logging
from utils.rate_limiter import RateLimiter

logger = logging.getLogger("yac")

DISCLAIMER = """
================================================================================
 YAC only performs credential checks against systems you are explicitly
 authorized to test (e.g. your own application, or a target covered by a
 signed penetration-testing / bug-bounty engagement). Running this against
 systems you do not own or have written authorization for is illegal in
 most jurisdictions and against most sites' terms of service.
================================================================================
"""


def load_credentials(credentials_file: str) -> List[Dict[str, str]]:
    with open(credentials_file, "r", newline="") as f:
        return list(csv.DictReader(f))


def confirm_authorization(assume_yes: bool) -> bool:
    print(DISCLAIMER)
    if assume_yes:
        return True
    answer = input("Type 'yes' to confirm you are authorized to test the selected target(s): ")
    return answer.strip().lower() == "yes"


async def run_site(website_name: str, website_info: dict, mode_override: str = None) -> List[LoginResult]:
    website = website_info["website"]
    mode = mode_override or website.get("mode", "requests")
    checker_cls = get_checker_class(mode)

    credentials_file = website["credentials_file"]
    try:
        credentials = load_credentials(credentials_file)
    except FileNotFoundError:
        logger.error("Credentials file '%s' not found for %s.", credentials_file, website_name)
        return []

    rate_limiter = RateLimiter.from_website_info(website)
    results: List[LoginResult] = []

    logger.info(
        "Starting %s check for '%s' (%d credential pairs, mode=%s, concurrency=%d)",
        mode, website_name, len(credentials), mode, rate_limiter.concurrency,
    )

    async with checker_cls(website_name, website_info) as checker:

        async def worker(row: Dict[str, str]) -> None:
            username, password = row.get("Username", ""), row.get("Password", "")
            async with rate_limiter.slot():
                await rate_limiter.throttle()
                try:
                    result = await checker.attempt(username, password)
                except Exception as exc:  # noqa: BLE001 - a single bad attempt must not kill the batch
                    logger.exception("Unexpected error checking %s on %s", username, website_name)
                    result = LoginResult(username, password, False, f"Unhandled exception: {exc}", mode=mode)
                results.append(result)
                level = logging.INFO if result.success else logging.DEBUG
                logger.log(
                    level,
                    "[%s] %s : %s -> %s (%s)",
                    website_name, username, password,
                    "SUCCESS" if result.success else "failed", result.reason,
                )

        tasks = [asyncio.create_task(worker(row)) for row in credentials]
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            for t in tasks:
                t.cancel()
            raise

    return results


async def run_all(selected: Dict[str, dict], mode_override: str, output_dir: str) -> None:
    site_summaries = []
    for website_name, website_info in selected.items():
        results = await run_site(website_name, website_info, mode_override)
        if not results:
            continue
        output_file = website_info["website"].get("output_file") or os.path.join(
            "results", f"{website_name}-result.csv"
        )
        reporter.write_csv(results, output_file)
        mode = mode_override or website_info["website"].get("mode", "requests")
        site_summaries.append(reporter.build_site_summary(website_name, mode, results))

    if site_summaries:
        summary_path = os.path.join(output_dir, "summary.json")
        reporter.write_json_summary(site_summaries, summary_path)
        reporter.print_console_summary(site_summaries)


def select_sites(websites: dict, args: argparse.Namespace) -> Dict[str, dict]:
    names = list(websites.keys())

    if args.single is not None:
        idx = args.single - 1
        if idx < 0 or idx >= len(names):
            raise SystemExit(f"Invalid site number: {args.single}")
        return {names[idx]: websites[names[idx]]}

    if args.multiple:
        raw = " ".join(args.multiple).replace(",", " ")
        try:
            indices = [int(x) for x in raw.split()]
        except ValueError:
            raise SystemExit("Invalid site numbers passed to --multiple.")
        selected = {}
        for i in indices:
            idx = i - 1
            if idx < 0 or idx >= len(names):
                raise SystemExit(f"Invalid site number: {i}")
            selected[names[idx]] = websites[names[idx]]
        return selected

    if args.all:
        return websites

    return {}


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="YAC - multi-site smart login checker (requests / browser / smart modes)"
    )
    p.add_argument("-c", "--config", action="store_true", help="List configured websites and exit.")
    p.add_argument("-s", "--single", type=int, metavar="N", help="Run a single check against site N.")
    p.add_argument(
        "-m", "--multiple", nargs="+", metavar="N", help="Run checks against multiple sites (e.g. 1,2,3 or 1 2 3)."
    )
    p.add_argument("--all", action="store_true", help="Run checks against every configured site.")
    p.add_argument(
        "--config-file", default="config/websites_config.ini", help="Path to the websites config INI file."
    )
    p.add_argument(
        "--mode", choices=["requests", "browser", "smart"],
        help="Override the mode= setting from config for every selected site.",
    )
    p.add_argument("--output-dir", default="results", help="Directory for the aggregate JSON summary.")
    p.add_argument("--yes", action="store_true", help="Skip the interactive authorization confirmation prompt.")
    p.add_argument("--validate-config", action="store_true", help="Parse and validate the config, then exit.")
    p.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")
    return p


def main() -> None:
    args = build_arg_parser().parse_args()
    setup_logging(verbose=args.verbose)

    try:
        websites = config_parser.read_website_config(args.config_file)
    except config_parser.ConfigValidationError as exc:
        logger.error(str(exc))
        sys.exit(1)

    if args.config or args.validate_config:
        print("Configured websites:")
        for i, (name, info) in enumerate(websites.items(), start=1):
            mode = info["website"].get("mode", "requests")
            print(f"  {i}. {name}  (mode={mode}, login_url={info['website'].get('login_url', '')})")
        return

    selected = select_sites(websites, args)
    if not selected:
        print("No site selected. Use -s N, -m N N ..., or --all. Use -c to list sites.")
        return

    if not confirm_authorization(args.yes):
        logger.error("Authorization not confirmed. Aborting.")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    try:
        asyncio.run(run_all(selected, args.mode, args.output_dir))
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Partial results (if any) were already written per completed site.")


if __name__ == "__main__":
    main()
