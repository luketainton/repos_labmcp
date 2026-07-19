from types import SimpleNamespace

import pytest

from labmcp import server


class FakeClient:
    def __init__(self, result=None):
        self.result = result if result is not None else []
        self.calls = []

    async def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return self.result


def test_labmcp_version_is_read_from_package_metadata(monkeypatch):
    monkeypatch.setattr(server, "get_version", lambda: "9.9.9")

    assert server.labmcp_get_version() == "9.9.9"


@pytest.mark.asyncio
async def test_gitea_list_issues_maps_filters_and_pagination(monkeypatch):
    client = FakeClient([{"number": 1}])
    monkeypatch.setattr(server, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(server, "gitea_client", lambda settings: client)

    result = await server.gitea_list_issues("alice", "notes", state="all", page=2, limit=25)

    assert result == [{"number": 1}]
    assert client.calls == [
        (
            "GET",
            "/api/v1/repos/alice/notes/issues",
            {"params": {"state": "all", "page": 2, "limit": 25}},
        )
    ]


@pytest.mark.asyncio
async def test_gitea_create_issue_rejects_empty_title():
    with pytest.raises(ValueError, match="title must not be empty"):
        await server.gitea_create_issue("alice", "notes", "  ")


@pytest.mark.asyncio
async def test_gitea_list_repositories_rejects_invalid_pagination():
    with pytest.raises(ValueError, match="limit must be between"):
        await server.gitea_list_repositories(page=1, limit=101)
