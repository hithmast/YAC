# YAC (Yes Another Checker)

YAC is a multi-site, multi-backend login checker. Give it a list of
credentials and a config describing one or more target login pages, and it
tells you which credentials are valid -- using whichever technique actually
works against the target:

- **`requests` mode** -- fast, async HTTP POST checker for classic
  server-rendered login forms. Supports CSRF token auto-discovery, retries
  with backoff, and proxying.
- **`browser` mode** -- drives a real (Playwright) headless Chromium
  instance, so JavaScript-rendered forms, client-side tokens, and
  client-side validation all just work like they would for a real user.
- **`smart` mode** -- hands the page to a [browser-use](https://github.com/browser-use/browser-use)
  AI agent. For modern single-page apps with multi-step logins (email
  screen, then password screen), shadow-DOM inputs, or cookie-consent
  interstitials, the agent figures out how to reach a submitted login form
  the way a human tester would, instead of relying on hand-picked CSS
  selectors.

> **Authorized use only.** Only run YAC against systems you own or have
> explicit written authorization to test (e.g. a signed penetration-test or
> bug-bounty scope). YAC shows a disclaimer and asks for confirmation before
> every run (skip with `--yes` once you've reviewed it). Built-in rate
> limiting (`concurrency`, `delay_min`/`delay_max` per site) exists to keep
> you a well-behaved client during an assessment, not to evade detection --
> there is no proxy-rotation or fingerprint-evasion feature, and there never
> will be.

## Features

- **Three pluggable backends** (`requests` / `browser` / `smart`), selected
  per website via `mode=` in the config -- mix and match across sites in a
  single run.
- **Async concurrency** with per-site rate limiting (bounded concurrency +
  randomized delay) to control load and avoid tripping lockouts/WAFs.
- **CSRF-aware** HTTP mode: auto-fetches and injects hidden CSRF tokens.
- **Redirect/URL-aware success detection** (`success_url_contains` /
  `failure_url_contains`) in addition to text-indicator matching, for SPA
  and OAuth-style post-login redirects.
- **Structured reporting**: per-site CSV (drop-in compatible with the
  original YAC format, plus `Mode`/`Duration` columns) and an aggregate
  `results/summary.json` across every site in the run.
- **Config validation** (`--validate-config` / `-c`) and clear errors for
  missing required fields.
- **Retries with backoff** and **proxy support** for HTTP mode.

## Requirements

- Python 3.9+
- Core: `aiohttp` (`pip install -r requirements.txt`)
- Optional, for `browser`/`smart` modes:
  `pip install -r requirements-browser.txt && playwright install chromium`
- `smart` mode additionally needs an LLM API key exported as an environment
  variable for whichever `llm_provider` you configure (e.g. `OPENAI_API_KEY`).

## Installation

```bash
git clone https://github.com/hithmast/YAC.git
cd YAC
pip install -r requirements.txt
# Only if you plan to use mode=browser or mode=smart:
pip install -r requirements-browser.txt
playwright install chromium
```

## Configuration

Websites are defined in `config/websites_config.ini`. Each `[SectionName]`
is one target. See the comment block at the top of
`config/websites_config.ini` for the full, per-mode key reference -- the
short version:

```ini
[MyTarget]
mode = requests                  ; requests | browser | smart
login_url = https://example.com/login
credentials_file = combo1.csv
output_file = results/mytarget-result.csv
success_indicators = Welcome, Dashboard
failure_indicators = Invalid username or password
concurrency = 5
delay_min = 0.5
delay_max = 1.5
```

Credentials CSV format (same for every mode):

```csv
Username,Password
user1,password1
user2,password2
```

## Usage

```bash
python main.py -c                      # list configured sites (and their mode)
python main.py -s 1                    # single check against site #1
python main.py -m 1,2,3                # multiple checks (comma or space separated)
python main.py --all                   # check every configured site
python main.py -m 1 2 --mode browser   # force browser mode for this run
python main.py --validate-config       # parse & validate config, then exit
python main.py -s 1 --yes              # skip the interactive authorization prompt
```

After a run, check:

- `results/<site>-result.csv` -- per-credential outcome for that site
- `results/summary.json` -- aggregate summary (valid credentials, timing) across all sites checked in that run
- `logs/<date>/output.log` -- full run log

## Logging

Logs are written daily to `logs/<YYYY-MM-DD>/output.log` and mirrored to the
console. Use `-v/--verbose` for debug-level logging.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request if you have suggestions or improvements.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
