"""Unit tests for github_client utility functions."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.ingestion.github_client import (
    _parse_link_header,
    extract_jira_keys,
)

# ---------------------------------------------------------------------------
# extract_jira_keys
# ---------------------------------------------------------------------------


def test_extract_jira_keys_standard():
    assert extract_jira_keys("Fix SCRUM-42: resolve null pointer") == ["SCRUM-42"]


def test_extract_jira_keys_multiple():
    keys = extract_jira_keys("Fix SCRUM-1 and SCRUM-2 related to DATA-7")
    assert set(keys) == {"SCRUM-1", "SCRUM-2", "DATA-7"}


def test_extract_jira_keys_in_pr_title():
    assert extract_jira_keys("[PROJ-99] Add feature") == ["PROJ-99"]


def test_extract_jira_keys_deduplicated():
    keys = extract_jira_keys("SCRUM-42 fixes SCRUM-42")
    assert keys == ["SCRUM-42"]


def test_extract_jira_keys_no_match():
    assert extract_jira_keys("chore: update dependencies") == []


def test_extract_jira_keys_empty_string():
    assert extract_jira_keys("") == []


def test_extract_jira_keys_none():
    assert extract_jira_keys(None) == []


def test_extract_jira_keys_version_not_matched():
    # "v1.2-3" should NOT match — it starts with lowercase v
    assert extract_jira_keys("bump version to v1.2-3") == []


def test_extract_jira_keys_two_letter_project():
    # Jira project keys require minimum 2 chars (e.g. "AB-1")
    assert extract_jira_keys("fix AB-1") == ["AB-1"]


def test_extract_jira_keys_single_letter_not_matched():
    # "A-1" (single-char project key) does NOT match — Jira requires 2+ chars
    assert extract_jira_keys("fix A-1") == []


def test_extract_jira_keys_mixed_case_not_matched():
    # "scrum-42" (lowercase) should NOT match
    assert extract_jira_keys("fixes scrum-42") == []


def test_extract_jira_keys_alphanumeric_project():
    assert extract_jira_keys("feature PROJ123-5") == ["PROJ123-5"]


def test_extract_jira_keys_body_truncation():
    # Only first 2000 chars of PR body should be scanned — simulate with long text
    key = "SCRUM-1"
    long_body = "x" * 2001 + f" {key}"
    # Key is past 2000 chars — should NOT be found if caller truncates
    text_to_scan = long_body[:2000]
    assert extract_jira_keys(text_to_scan) == []

    # Key within first 2000 chars — should be found
    short_body = f"Fix {key} " + "x" * 1990
    assert extract_jira_keys(short_body[:2000]) == [key]


# ---------------------------------------------------------------------------
# _parse_link_header
# ---------------------------------------------------------------------------


def test_parse_link_header_with_next():
    header = '<https://api.github.com/repos/org/repo/commits?page=2>; rel="next", <https://api.github.com/repos/org/repo/commits?page=5>; rel="last"'
    result = _parse_link_header(header)
    assert result == "https://api.github.com/repos/org/repo/commits?page=2"


def test_parse_link_header_no_next():
    header = '<https://api.github.com/repos/org/repo/commits?page=1>; rel="last"'
    assert _parse_link_header(header) is None


def test_parse_link_header_none():
    assert _parse_link_header(None) is None


def test_parse_link_header_empty():
    assert _parse_link_header("") is None


# ---------------------------------------------------------------------------
# list_prs pagination termination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_prs_stops_on_since():
    """list_prs() must stop pagination when updated_at < since."""
    since = datetime(2026, 5, 1, tzinfo=UTC)

    old_pr = {
        "number": 1,
        "title": "old PR",
        "body": None,
        "state": "closed",
        "user": {"login": "alice"},
        "head": {"ref": "feature"},
        "base": {"ref": "main"},
        "created_at": "2026-04-01T00:00:00Z",
        "closed_at": "2026-04-02T00:00:00Z",
        "merged_at": None,
        "html_url": None,
        "updated_at": "2026-04-30T00:00:00Z",  # before `since`
    }

    from src.ingestion.github_client import GitHubClient

    client = GitHubClient.__new__(GitHubClient)
    client._pat = "test"
    client._org = "testorg"
    client._base_url = "https://api.github.com"

    # Mock _get to return one page with a PR that is before `since`
    client._get = AsyncMock(return_value=([old_pr], {"link": None}))

    prs = await client.list_prs("testorg/repo", since=since)
    assert prs == []  # PR was before `since`, so stopped immediately
    client._get.assert_called_once()  # Only one page fetched
