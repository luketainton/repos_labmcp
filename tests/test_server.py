from types import SimpleNamespace

import pytest

from labmcp import server
from labmcp.config import Settings


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
async def test_service_catalogues_only_expose_their_own_tools() -> None:
    settings = Settings(mcp_transport="http", mcp_auth_mode="none")
    gitea = server.create_mcp(settings, "gitea")
    pocket_id = server.create_mcp(settings, "pocket_id")

    assert await gitea.get_tool("labmcp_get_version") is not None
    assert await gitea.get_tool("gitea_list_repositories") is not None
    assert await gitea.get_tool("pocket_id_health") is None
    assert await pocket_id.get_tool("labmcp_get_version") is not None
    assert await pocket_id.get_tool("pocket_id_health") is not None
    assert await pocket_id.get_tool("gitea_list_repositories") is None


def test_network_app_mounts_legacy_and_service_paths_with_path_audiences() -> None:
    settings = Settings(
        mcp_transport="http",
        mcp_auth_mode="none",
        mcp_auth_base_url="https://mcp.example.com/",
    )
    app = server.create_network_app(settings)

    assert [route.path for route in app.routes] == [
        "/mcp",
        "/gitea",
        "/pocketid",
        "/n8n",
        "/meraki",
        "/pangolin",
        "/shlink",
        "/action1",
        "/pushover",
    ]
    jwt_settings = Settings(
        mcp_transport="http",
        mcp_auth_mode="jwt",
        mcp_auth_base_url="https://mcp.example.com/",
    )
    gitea_settings = server._path_settings(jwt_settings, "gitea")
    assert gitea_settings.mcp_auth_base_url == "https://mcp.example.com/gitea/"
    assert gitea_settings.mcp_auth_jwt_audience == "https://mcp.example.com/gitea/"


def test_path_settings_preserves_oidc_proxy_upstream_audience() -> None:
    settings = Settings(
        mcp_transport="http",
        mcp_auth_mode="oidc_proxy",
        mcp_auth_base_url="https://mcp.example.com/",
        mcp_auth_jwt_audience="pocket-id-client-id",
    )

    gitea_settings = server._path_settings(settings, "gitea")

    assert gitea_settings.mcp_auth_base_url == "https://mcp.example.com/gitea/"
    assert gitea_settings.mcp_auth_jwt_audience == "pocket-id-client-id"


@pytest.mark.asyncio
async def test_network_app_starts_each_mounted_fastmcp_lifespan() -> None:
    app = server.create_network_app(Settings(mcp_transport="http", mcp_auth_mode="none"))

    async with app.router.lifespan_context(app):
        mounted_gitea = app.routes[1].app
        assert mounted_gitea.state.fastmcp_server is not None



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
