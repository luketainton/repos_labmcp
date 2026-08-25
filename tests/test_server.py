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
async def test_static_tools_expose_mcp_behavior_annotations() -> None:
    version_tool = await server.mcp.get_tool("labmcp_get_version")
    list_repositories_tool = await server.mcp.get_tool("gitea_list_repositories")
    create_issue_tool = await server.mcp.get_tool("gitea_create_issue")

    assert version_tool is not None
    assert version_tool.annotations.model_dump(exclude_none=True) == {
        "readOnlyHint": True,
        "openWorldHint": False,
    }
    assert list_repositories_tool is not None
    assert list_repositories_tool.annotations.model_dump(exclude_none=True) == {
        "readOnlyHint": True,
        "openWorldHint": True,
    }
    assert create_issue_tool is not None
    assert create_issue_tool.annotations.model_dump(exclude_none=True) == {
        "readOnlyHint": False,
        "openWorldHint": True,
    }


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
async def test_server_wrappers_forward_gitea_and_pocket_id_requests(monkeypatch):
    gitea = FakeClient({"name": "notes"})
    pocket_id = FakeClient({"issuer": "https://id.example"})
    settings = SimpleNamespace(pocket_id_health_path="/healthz")
    monkeypatch.setattr(server, "get_settings", lambda: settings)
    monkeypatch.setattr(server, "gitea_client", lambda _settings: gitea)
    monkeypatch.setattr(server, "pocket_id_client", lambda _settings: pocket_id)

    assert await server.gitea_list_repositories(page=2, limit=10, private=True) == {"name": "notes"}
    assert await server.gitea_get_repository("alice", "notes") == {"name": "notes"}
    assert await server.gitea_create_issue("alice", "notes", "Title", "Body") == {"name": "notes"}
    assert await server.pocket_id_openid_configuration() == {"issuer": "https://id.example"}
    assert await server.pocket_id_health() == {"issuer": "https://id.example"}
    assert gitea.calls == [
        ("GET", "/api/v1/user/repos", {"params": {"page": 2, "limit": 10, "private": True}}),
        ("GET", "/api/v1/repos/alice/notes", {}),
        ("POST", "/api/v1/repos/alice/notes/issues", {"json": {"title": "Title", "body": "Body"}}),
    ]
    assert pocket_id.calls == [
        ("GET", "/.well-known/openid-configuration", {}),
        ("GET", "/healthz", {}),
    ]


@pytest.mark.asyncio
async def test_gitea_create_issue_rejects_empty_title():
    with pytest.raises(ValueError, match="title must not be empty"):
        await server.gitea_create_issue("alice", "notes", "  ")


@pytest.mark.asyncio
async def test_gitea_list_repositories_rejects_invalid_pagination():
    with pytest.raises(ValueError, match="limit must be between"):
        await server.gitea_list_repositories(page=1, limit=101)


@pytest.mark.asyncio
async def test_gitea_list_issues_rejects_invalid_state_and_pagination():
    with pytest.raises(ValueError, match="state must be"):
        await server.gitea_list_issues("alice", "notes", state="pending")
    with pytest.raises(ValueError, match="limit must be between"):
        await server.gitea_list_issues("alice", "notes", page=0)


def test_main_validates_transport_then_runs_server(monkeypatch):
    settings = SimpleNamespace(mcp_transport="stdio", mcp_host="127.0.0.1", mcp_port=8765)
    calls = []
    monkeypatch.setattr(server, "get_settings", lambda: settings)
    monkeypatch.setattr(server, "ensure_network_transport_is_authenticated", lambda value: calls.append(value))
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: calls.append(kwargs))

    server.main()

    assert calls == [settings, {"transport": "stdio", "host": "127.0.0.1", "port": 8765}]
