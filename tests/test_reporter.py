import csv
import json

from checkers.base import LoginResult
from utils import reporter


def sample_results():
    return [
        LoginResult("alice", "pw1", True, "Success", 0.12, "requests"),
        LoginResult("bob", "pw2", False, "Invalid password", 0.08, "requests"),
    ]


def test_write_csv_contains_rows_and_footer(tmp_path):
    output_file = tmp_path / "out.csv"
    reporter.write_csv(sample_results(), str(output_file))

    with open(output_file) as f:
        rows = list(csv.reader(f))

    header, alice_row, bob_row = rows[0], rows[1], rows[2]
    assert header == ["Username", "Password", "Valid Login", "Reason", "Mode", "Duration"]
    assert alice_row[:4] == ["alice", "pw1", "Yes", "Success"]
    assert bob_row[:4] == ["bob", "pw2", "No", "Invalid password"]
    assert "Total users: 2" in rows[-2][0]
    assert "Valid logins: 1" in rows[-1][0]


def test_write_csv_creates_parent_dirs(tmp_path):
    output_file = tmp_path / "nested" / "dir" / "out.csv"
    reporter.write_csv(sample_results(), str(output_file))
    assert output_file.exists()


def test_build_site_summary():
    summary = reporter.build_site_summary("MySite", "requests", sample_results())
    assert summary["website"] == "MySite"
    assert summary["mode"] == "requests"
    assert summary["total_attempts"] == 2
    assert summary["valid_logins"] == 1
    assert summary["valid_credentials"] == [{"username": "alice", "password": "pw1"}]
    assert summary["total_duration_seconds"] == 0.2


def test_write_json_summary_roundtrip(tmp_path):
    summary = reporter.build_site_summary("MySite", "requests", sample_results())
    output_file = tmp_path / "summary.json"
    reporter.write_json_summary([summary], str(output_file))

    with open(output_file) as f:
        data = json.load(f)

    assert data["sites"][0]["website"] == "MySite"


def test_print_console_summary_never_prints_password(capsys):
    summary = reporter.build_site_summary("MySite", "requests", sample_results())
    reporter.print_console_summary([summary])
    output = capsys.readouterr().out
    assert "pw1" not in output
    assert "alice" in output
