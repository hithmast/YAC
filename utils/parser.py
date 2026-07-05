"""Website config parsing.

Config sections stay a flat INI blob so the tool remains approachable, but
the schema now spans three checker backends (requests / browser / smart).
Unknown keys are passed straight through to `website[key]` so each checker
backend can read whatever options it needs without this parser having to
know about every backend-specific field.
"""

import configparser
from configparser import ExtendedInterpolation
from urllib.parse import quote

REQUIRED_KEYS = ("login_url", "credentials_file", "output_file")


class ConfigValidationError(ValueError):
    pass


def read_website_config(config_file: str) -> dict:
    config = configparser.ConfigParser(interpolation=ExtendedInterpolation())
    read_files = config.read(config_file)
    if not read_files:
        raise ConfigValidationError(f"Config file not found or unreadable: {config_file}")

    websites = {}

    for section in config.sections():
        website = {}
        headers = {}
        payload = {}

        for key, value in config.items(section):
            key = key.strip()
            if key == "login_url":
                # Percent-encode so the URL can round-trip safely through the
                # INI value; backends decode it again via utils.urlutil.
                website[key] = quote(value.strip(), safe=":/?=&%")
            elif key in ("success_indicators", "failure_indicators"):
                website[key] = [v.strip() for v in value.split(",") if v.strip()]
            elif key.startswith("h_"):
                headers[key[2:]] = value
            elif key.startswith("p_"):
                payload[key[2:]] = value
            else:
                website[key] = value.strip() if isinstance(value, str) else value

        missing = [k for k in REQUIRED_KEYS if k not in website]
        if missing:
            raise ConfigValidationError(
                f"Section [{section}] is missing required key(s): {', '.join(missing)}"
            )

        websites[section] = {
            "website": website,
            "headers": headers,
            "payload": payload,
        }

    if not websites:
        raise ConfigValidationError(f"No website sections found in {config_file}")

    return websites


def list_website_names(websites: dict) -> list:
    return list(websites.keys())
