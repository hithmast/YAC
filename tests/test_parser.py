import textwrap

import pytest

from utils.parser import ConfigValidationError, read_website_config
from utils.urlutil import reverse_url_encoding


def write_config(tmp_path, content):
    path = tmp_path / "websites_config.ini"
    path.write_text(textwrap.dedent(content))
    return str(path)


def test_reads_valid_pairs_config(tmp_path):
    config_file = write_config(
        tmp_path,
        """
        [Site1]
        login_url = https://example.com/login?x=1&y=2
        credentials_file = combo.csv
        output_file = results/site1.csv
        success_indicators = Welcome, Dashboard
        failure_indicators = Invalid
        h_user-agent = TestAgent/1.0
        p_extra = value
        """,
    )
    websites = read_website_config(config_file)
    assert list(websites.keys()) == ["Site1"]
    site = websites["Site1"]
    assert reverse_url_encoding(site["website"]["login_url"]) == "https://example.com/login?x=1&y=2"
    assert site["website"]["success_indicators"] == ["Welcome", "Dashboard"]
    assert site["website"]["failure_indicators"] == ["Invalid"]
    assert site["headers"] == {"user-agent": "TestAgent/1.0"}
    assert site["payload"] == {"extra": "value"}


def test_missing_config_file_raises(tmp_path):
    with pytest.raises(ConfigValidationError):
        read_website_config(str(tmp_path / "does-not-exist.ini"))


def test_missing_required_key_raises(tmp_path):
    config_file = write_config(
        tmp_path,
        """
        [Site1]
        credentials_file = combo.csv
        output_file = results/site1.csv
        """,
    )
    with pytest.raises(ConfigValidationError, match="login_url"):
        read_website_config(config_file)


def test_pairs_strategy_requires_credentials_file(tmp_path):
    config_file = write_config(
        tmp_path,
        """
        [Site1]
        login_url = https://example.com/login
        output_file = results/site1.csv
        """,
    )
    with pytest.raises(ConfigValidationError, match="credentials_file"):
        read_website_config(config_file)


def test_spray_strategy_requires_username_and_password_lists(tmp_path):
    config_file = write_config(
        tmp_path,
        """
        [Site1]
        strategy = spray
        login_url = https://example.com/login
        output_file = results/site1.csv
        """,
    )
    with pytest.raises(ConfigValidationError, match="username_list"):
        read_website_config(config_file)


def test_spray_strategy_valid_config(tmp_path):
    config_file = write_config(
        tmp_path,
        """
        [Site1]
        strategy = spray
        login_url = https://example.com/login
        output_file = results/site1.csv
        username_list = users.txt
        password_list = passwords.txt
        """,
    )
    websites = read_website_config(config_file)
    assert websites["Site1"]["website"]["strategy"] == "spray"


def test_unknown_strategy_raises(tmp_path):
    config_file = write_config(
        tmp_path,
        """
        [Site1]
        strategy = bogus
        login_url = https://example.com/login
        output_file = results/site1.csv
        credentials_file = combo.csv
        """,
    )
    with pytest.raises(ConfigValidationError, match="unknown strategy"):
        read_website_config(config_file)


def test_no_sections_raises(tmp_path):
    config_file = write_config(tmp_path, "")
    with pytest.raises(ConfigValidationError, match="No website sections"):
        read_website_config(config_file)
