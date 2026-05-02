"""Unit tests for JiraClient using respx to mock httpx."""

import pytest
import respx
from httpx import Response

from src.ingestion.jira_client import JiraClient, JiraComment, JiraIssue, JiraSprint


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ISSUE_PAYLOAD = {
    "key": "PROJ-1",
    "fields": {
        "summary": "Test issue",
        "description": "A description",
        "status": {"name": "In Progress"},
        "assignee": {"emailAddress": "alice@example.com", "displayName": "Alice", "accountId": "alice"},
        "priority": {"name": "High"},
        "labels": [],
        "issuelinks": [],
        "created": "2026-01-01T10:00:00.000+0000",
        "updated": "2026-01-02T10:00:00.000+0000",
        "duedate": None,
        "flagged": False,
        "sprint": None,
        "customfield_10016": 3.0,
    },
}

SPRINT_PAYLOAD = {
    "id": 42,
    "name": "Sprint 1",
    "state": "active",
    "originBoardId": 10,
    "startDate": "2026-01-01",
    "endDate": "2026-01-14",
}

COMMENT_PAYLOAD = {
    "id": "100",
    "author": {"displayName": "Bob", "emailAddress": "bob@example.com"},
    "body": "Looks good",
    "created": "2026-01-03T09:00:00.000+0000",
}


# ---------------------------------------------------------------------------
# US1: Auth & retry behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_client_enters_and_exits_cleanly(respx_mock):
    async with JiraClient() as client:
        assert client._client is not None
    assert client._client is None


@pytest.mark.asyncio
@respx.mock
async def test_401_raises_runtime_error_without_retry(respx_mock):
    respx_mock.get("http://localhost/rest/api/3/issue/PROJ-1").mock(return_value=Response(401))
    client = JiraClient.__new__(JiraClient)
    client._base_url = "http://localhost"
    import httpx
    client._auth = httpx.BasicAuth("user", "token")
    async with client:
        with pytest.raises(RuntimeError, match="authentication failed"):
            await client._call("GET", "/rest/api/3/issue/PROJ-1")


@pytest.mark.asyncio
@respx.mock
async def test_429_is_retried_up_to_max(respx_mock):
    route = respx_mock.get("http://localhost/rest/api/3/search/jql").mock(return_value=Response(429))
    client = JiraClient.__new__(JiraClient)
    client._base_url = "http://localhost"
    import httpx
    client._auth = httpx.BasicAuth("user", "token")
    async with client:
        with pytest.raises(RuntimeError, match="failed after"):
            await client._call("GET", "/rest/api/3/search/jql", params={"jql": "project=X", "startAt": 0, "maxResults": 1})
    assert route.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_500_is_retried_up_to_max(respx_mock):
    route = respx_mock.get("http://localhost/rest/api/3/search/jql").mock(return_value=Response(500))
    client = JiraClient.__new__(JiraClient)
    client._base_url = "http://localhost"
    import httpx
    client._auth = httpx.BasicAuth("user", "token")
    async with client:
        with pytest.raises(RuntimeError, match="failed after"):
            await client._call("GET", "/rest/api/3/search/jql", params={"jql": "project=X", "startAt": 0, "maxResults": 1})
    assert route.call_count == 3


# ---------------------------------------------------------------------------
# US2: list_issues (pagination)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_list_issues_single_page(respx_mock):
    respx_mock.get("http://localhost/rest/api/3/search/jql").mock(
        return_value=Response(200, json={"issues": [ISSUE_PAYLOAD], "startAt": 0, "maxResults": 100, "total": 1})
    )
    client = JiraClient.__new__(JiraClient)
    client._base_url = "http://localhost"
    import httpx
    client._auth = httpx.BasicAuth("user", "token")
    async with client:
        issues = await client.list_issues("PROJ")
    assert len(issues) == 1
    assert isinstance(issues[0], JiraIssue)
    assert issues[0].jira_id == "PROJ-1"
    assert issues[0].summary == "Test issue"


@pytest.mark.asyncio
@respx.mock
async def test_list_issues_multi_page(respx_mock):
    page1 = {"issues": [ISSUE_PAYLOAD], "startAt": 0, "maxResults": 1, "total": 2}
    page2_issue = {**ISSUE_PAYLOAD, "key": "PROJ-2"}
    page2 = {"issues": [page2_issue], "startAt": 1, "maxResults": 1, "total": 2}
    respx_mock.get("http://localhost/rest/api/3/search/jql").mock(
        side_effect=[Response(200, json=page1), Response(200, json=page2)]
    )
    client = JiraClient.__new__(JiraClient)
    client._base_url = "http://localhost"
    import httpx
    client._auth = httpx.BasicAuth("user", "token")
    async with client:
        issues = await client.list_issues("PROJ")
    assert len(issues) == 2
    assert issues[1].jira_id == "PROJ-2"


@pytest.mark.asyncio
@respx.mock
async def test_list_issues_empty_project(respx_mock):
    respx_mock.get("http://localhost/rest/api/3/search/jql").mock(
        return_value=Response(200, json={"issues": [], "startAt": 0, "maxResults": 100, "total": 0})
    )
    client = JiraClient.__new__(JiraClient)
    client._base_url = "http://localhost"
    import httpx
    client._auth = httpx.BasicAuth("user", "token")
    async with client:
        issues = await client.list_issues("EMPTY")
    assert issues == []


# ---------------------------------------------------------------------------
# US2: get_issue, list_sprints, get_comments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_issue_returns_none_on_404(respx_mock):
    respx_mock.get("http://localhost/rest/api/3/issue/PROJ-999").mock(return_value=Response(404))
    client = JiraClient.__new__(JiraClient)
    client._base_url = "http://localhost"
    import httpx
    client._auth = httpx.BasicAuth("user", "token")
    async with client:
        result = await client.get_issue("PROJ-999")
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_list_sprints_parsed_correctly(respx_mock):
    respx_mock.get("http://localhost/rest/agile/1.0/board/10/sprint").mock(
        return_value=Response(200, json={"values": [SPRINT_PAYLOAD]})
    )
    client = JiraClient.__new__(JiraClient)
    client._base_url = "http://localhost"
    import httpx
    client._auth = httpx.BasicAuth("user", "token")
    async with client:
        sprints = await client.list_sprints("10")
    assert len(sprints) == 1
    assert isinstance(sprints[0], JiraSprint)
    assert sprints[0].jira_sprint_id == "42"
    assert sprints[0].state == "active"


@pytest.mark.asyncio
@respx.mock
async def test_get_comments_with_correct_issue_id(respx_mock):
    respx_mock.get("http://localhost/rest/api/3/issue/PROJ-1/comment").mock(
        return_value=Response(200, json={"comments": [COMMENT_PAYLOAD]})
    )
    client = JiraClient.__new__(JiraClient)
    client._base_url = "http://localhost"
    import httpx
    client._auth = httpx.BasicAuth("user", "token")
    async with client:
        comments = await client.get_comments("PROJ-1")
    assert len(comments) == 1
    assert isinstance(comments[0], JiraComment)
    assert comments[0].issue_jira_id == "PROJ-1"
    assert comments[0].body == "Looks good"


# ---------------------------------------------------------------------------
# US3: update_issue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_update_issue_returns_true_on_success(respx_mock):
    respx_mock.put("http://localhost/rest/api/3/issue/PROJ-1").mock(return_value=Response(204))
    client = JiraClient.__new__(JiraClient)
    client._base_url = "http://localhost"
    import httpx
    client._auth = httpx.BasicAuth("user", "token")
    async with client:
        result = await client.update_issue("PROJ-1", {"status": {"name": "Done"}})
    assert result is True


@pytest.mark.asyncio
@respx.mock
async def test_update_issue_returns_false_on_403(respx_mock):
    respx_mock.put("http://localhost/rest/api/3/issue/PROJ-1").mock(return_value=Response(403))
    client = JiraClient.__new__(JiraClient)
    client._base_url = "http://localhost"
    import httpx
    client._auth = httpx.BasicAuth("user", "token")
    async with client:
        result = await client.update_issue("PROJ-1", {"status": {"name": "Done"}})
    assert result is False
