"""YAC (Yes Another Checker) -- multi-site smart login checker.

Interchangeable backends, selected per-website via `mode` in
websites_config.ini:

  requests  - fast async HTTP POST checker for classic server-rendered forms
  browser   - real (Playwright) headless browser for JS-rendered forms
  smart     - browser-use AI agent for multi-step / highly dynamic modern SPAs
  o365      - protocol-aware Microsoft 365 / Azure AD checker (AADSTS codes)
  okta      - protocol-aware Okta checker (Authn API status codes)

Plus: lockout-aware pacing, password-spray strategy, bot/CAPTCHA detection,
and resumable runs. See README.md for the full config schema and an
authorized-use disclaimer.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Dict, List

from checkers import get_checker_class
from checkers.base import LoginResult
from utils import credentials as credentials_lib
from utils import parser as config_parser
from utils import reporter
from utils.checkpoint import CheckpointWriter, checkpoint_path, load_done
from utils.lockout_guard import LockoutGuard
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


def confirm_authorization(assume_yes: bool) -> bool:
    print(DISCLAIMER)
    if assume_yes:
        return True
    answer = input("Type 'yes' to confirm you are authorized to test the selected target(s): ")
    return answer.strip().lower() == "yes"


BLOCKED_ABORT_THRESHOLD = 3  # consecutive bot/CAPTCHA hits before giving up on a site


async def run_site(
    website_name: str,
    website_info: dict,
    mode_override: str = None,
    resume: bool = False,
    state_dir: str = ".yac_state",
) -> List[LoginResult]:
    website = website_info["website"]
    mode = mode_override or website.get("mode", "requests")
    checker_cls = get_checker_class(mode)

    try:
        credentials = credentials_lib.load_credentials(website)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Could not load credentials for %s: %s", website_name, exc)
        return []

    ckpt_file = checkpoint_path(state_dir, website_name)
    already_done = load_done(ckpt_file) if resume else set()
    if already_done:
        before = len(credentials)
        credentials = [
            row for row in credentials
            if (row.get("Username", ""), row.get("Password", "")) not in already_done
        ]
        logger.info(
            "Resume: skipping %d already-attempted pair(s) for %s.",
            before - len(credentials), website_name,
        )
    checkpoint_writer = CheckpointWriter(ckpt_file) if resume else None

    rate_limiter = RateLimiter.from_website_info(website)
    lockout_guard = LockoutGuard.from_website_info(website)
    results: List[LoginResult] = []
    blocked_count = 0
    abort_event = asyncio.Event()

    logger.info(
        "Starting %s check for '%s' (%d credential pairs, mode=%s, concurrency=%d)",
        mode, website_name, len(credentials), mode, rate_limiter.concurrency,
    )

    try:
        checker = checker_cls(website_name, website_info)
    except (ValueError, RuntimeError) as exc:
        logger.error("Could not initialize %s checker for %s: %s", mode, website_name, exc)
        if checkpoint_writer:
            checkpoint_writer.close()
        return []

    try:
        await checker.setup()
    except (ValueError, RuntimeError) as exc:
        logger.error("Could not start %s checker for %s: %s", mode, website_name, exc)
        if checkpoint_writer:
            checkpoint_writer.close()
        return []

    try:

        async def worker(row: Dict[str, str]) -> None:
            nonlocal blocked_count
            username, password = row.get("Username", ""), row.get("Password", "")

            if abort_event.is_set():
                return
            if lockout_guard.is_locked_out(username):
                results.append(LoginResult(
                    username, password, False,
                    "Skipped (account appears locked out from a prior attempt)", mode=mode,
                ))
                return

            await lockout_guard.wait_for_slot(username)
            async with rate_limiter.slot():
                if abort_event.is_set():
                    return
                # Re-check: a sibling attempt for this same username may have
                # completed (and tripped the lockout) while we were queued
                # behind wait_for_slot()/the concurrency semaphore above.
                if lockout_guard.is_locked_out(username):
                    results.append(LoginResult(
                        username, password, False,
                        "Skipped (account appears locked out from a prior attempt)", mode=mode,
                    ))
                    return
                await rate_limiter.throttle()
                try:
                    result = await checker.attempt(username, password)
                except Exception as exc:  # noqa: BLE001 - a single bad attempt must not kill the batch
                    # Log/report the exception class only, never str(exc) or a
                    # traceback: some client-library exceptions echo request
                    # details back in their message, which the submitted
                    # password must never be able to leak through.
                    exc_name = type(exc).__name__
                    logger.error("Unexpected error checking %s on %s: %s", username, website_name, exc_name)
                    result = LoginResult(username, password, False, f"Unhandled exception: {exc_name}", mode=mode)

                lockout_guard.observe(username, result)
                results.append(result)
                if checkpoint_writer:
                    checkpoint_writer.record(username, password)

                if result.extra.get("blocked"):
                    blocked_count += 1
                    if blocked_count >= BLOCKED_ABORT_THRESHOLD and not abort_event.is_set():
                        abort_event.set()
                        logger.warning(
                            "Bot/CAPTCHA protection detected %d times on '%s'; "
                            "aborting remaining attempts for this site.",
                            blocked_count, website_name,
                        )

                level = logging.INFO if result.success else logging.DEBUG
                # Deliberately excludes `password`: operational logs are not
                # the deliverable and often have broader/longer-lived access
                # than the results files. The valid password is recorded in
                # the per-site CSV and results/summary.json, which is where
                # it belongs.
                logger.log(
                    level,
                    "[%s] %s -> %s (%s)",
                    website_name, username,
                    "SUCCESS" if result.success else "failed", result.reason,
                )

        tasks = [asyncio.create_task(worker(row)) for row in credentials]
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            for t in tasks:
                t.cancel()
            raise
    finally:
        await checker.teardown()
        if checkpoint_writer:
            checkpoint_writer.close()

    return results


async def run_all(
    selected: Dict[str, dict],
    mode_override: str,
    output_dir: str,
    resume: bool = False,
    state_dir: str = ".yac_state",
) -> None:
    site_summaries = []
    for website_name, website_info in selected.items():
        results = await run_site(website_name, website_info, mode_override, resume, state_dir)
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
        "--mode", choices=["requests", "browser", "smart", "o365", "okta"],
        help="Override the mode= setting from config for every selected site.",
    )
    p.add_argument("--output-dir", default="results", help="Directory for the aggregate JSON summary.")
    p.add_argument("--yes", action="store_true", help="Skip the interactive authorization confirmation prompt.")
    p.add_argument("--validate-config", action="store_true", help="Parse and validate the config, then exit.")
    p.add_argument(
        "--resume", action="store_true",
        help="Skip credential pairs already attempted in a prior run and record new ones as they complete.",
    )
    p.add_argument(
        "--state-dir", default=".yac_state", help="Directory used to store --resume checkpoint files."
    )
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
        asyncio.run(run_all(selected, args.mode, args.output_dir, args.resume, args.state_dir))
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Partial results (if any) were already written per completed site.")


if __name__ == "__main__":
    main()
