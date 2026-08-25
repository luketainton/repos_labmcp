import pytest

from labmcp.gitea_api import (
    GiteaOperationProvider,
    _get_operations,
    _tool_name,
    call_operation,
    parse_operations,
)


class FakeClient:
    base_url = "https://gitea.example"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    async def request(self, method: str, path: str, **kwargs: object) -> dict[str, bool]:
        self.calls.append((method, path, kwargs))
        return {"ok": True}


def test_parse_operations_includes_json_and_form_routes_but_not_binary_routes() -> None:
    operations = parse_operations(
        {
            "paths": {
                "/repos/{owner}/{repo}": {
                    "get": {"operationId": "repoGet"},
                    "post": {
                        "operationId": "repoForm",
                        "parameters": [{"in": "formData", "name": "title", "type": "string"}],
                    },
                },
                "/repos/{owner}/{repo}/assets": {
                    "post": {
                        "operationId": "assetUpload",
                        "parameters": [{"in": "formData", "name": "file", "type": "file"}],
                    }
                },
                "/repos/{owner}/{repo}/archive": {
                    "get": {"operationId": "archiveGet", "produces": ["application/zip"]}
                },
            }
        }
    )

    assert operations["repoGet"].path == "/api/v1/repos/{owner}/{repo}"
    assert operations["repoForm"].encoding == "form"
    assert "assetUpload" not in operations
    assert "archiveGet" not in operations


def test_parse_operations_rejects_invalid_or_duplicate_documents() -> None:
    with pytest.raises(ValueError, match="does not contain paths"):
        parse_operations({})

    with pytest.raises(ValueError, match="Duplicate"):
        parse_operations({"paths": {"/one": {"get": {"operationId": "same"}}, "/two": {"post": {"operationId": "same"}}}})

    with pytest.raises(ValueError, match="no supported operations"):
        parse_operations({"paths": {"/archive": {"get": {"operationId": "archive", "produces": ["application/zip"]}}}})


def test_parse_operations_ignores_invalid_routes_and_methods() -> None:
    operations = parse_operations({"paths": {
        1: {"get": {"operationId": "ignored"}},
        "/not-a-map": None,
        "/unsupported": {"head": {"operationId": "ignored"}},
        "/missing-id": {"get": {}},
        "/valid": {"get": {"operationId": "valid"}},
    }})

    assert set(operations) == {"valid"}


@pytest.mark.asyncio
async def test_call_operation_validates_and_encodes_path_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeClient()
    operations = parse_operations(
        {"paths": {"/repos/{owner}/{repo}": {"get": {"operationId": "repoGet"}}}}
    )

    async def get_operations(_client):
        return operations

    monkeypatch.setattr("labmcp.gitea_api._get_operations", get_operations)

    result = await call_operation(
        client,
        "repoGet",
        path_params={"owner": "alice", "repo": "notes/2026"},
    )

    assert result == {"ok": True}
    assert client.calls == [
        (
            "GET",
            "/api/v1/repos/alice/notes%2F2026",
            {"params": None, "json": None, "data": None},
        )
    ]


@pytest.mark.asyncio
async def test_call_operation_rejects_an_unknown_operation(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient()

    async def get_operations(_client):
        return {}

    monkeypatch.setattr("labmcp.gitea_api._get_operations", get_operations)

    with pytest.raises(ValueError, match="Unknown Gitea operation"):
        await call_operation(client, "unknown")


@pytest.mark.asyncio
async def test_call_operation_rejects_invalid_request_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient()
    operations = parse_operations({"paths": {"/repos/{owner}": {"post": {"operationId": "update"}}}})

    async def get_operations(_client):
        return operations

    monkeypatch.setattr("labmcp.gitea_api._get_operations", get_operations)

    with pytest.raises(ValueError, match="either body or form"):
        await call_operation(client, "update", path_params={"owner": "alice"}, body={}, form={})
    with pytest.raises(ValueError, match="requires path_params"):
        await call_operation(client, "update")


@pytest.mark.asyncio
async def test_call_operation_requires_form_data_for_form_operations(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient()
    operations = parse_operations({"paths": {"/repos": {"post": {"operationId": "create", "parameters": [{"in": "formData", "name": "title", "type": "string"}]}}}})

    async def get_operations(_client):
        return operations

    monkeypatch.setattr("labmcp.gitea_api._get_operations", get_operations)

    with pytest.raises(ValueError, match="requires form data"):
        await call_operation(client, "create", body={})


@pytest.mark.asyncio
async def test_get_operations_parses_and_caches_swagger_specification(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient()
    client.base_url = "https://gitea-cache.example"
    document = {"paths": {"/user/repos": {"get": {"operationId": "listRepos"}}}}

    async def request(method, path, **kwargs):
        client.calls.append((method, path, kwargs))
        return document

    monkeypatch.setattr(client, "request", request)
    monkeypatch.setattr("labmcp.gitea_api._OPERATIONS_CACHE", {})

    assert set(await _get_operations(client)) == {"listRepos"}
    assert set(await _get_operations(client)) == {"listRepos"}
    assert client.calls == [("GET", "/swagger.v1.json", {})]


@pytest.mark.asyncio
async def test_get_operations_refreshes_and_rejects_non_json_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient()
    client.base_url = "https://gitea-refresh.example"
    document = {"paths": {"/user/repos": {"get": {"operationId": "listRepos"}}}}
    monkeypatch.setattr("labmcp.gitea_api._OPERATIONS_CACHE", {})

    async def request(method, path, **kwargs):
        client.calls.append((method, path, kwargs))
        return document

    monkeypatch.setattr(client, "request", request)
    await _get_operations(client)
    await _get_operations(client, refresh=True)
    assert len(client.calls) == 2

    client.base_url = "https://gitea-invalid.example"

    async def invalid_request(method, path, **kwargs):
        return []

    monkeypatch.setattr(client, "request", invalid_request)
    with pytest.raises(ValueError, match="did not return a JSON object"):
        await _get_operations(client)


@pytest.mark.asyncio
async def test_operation_provider_exposes_a_tool_for_each_swagger_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeClient()
    operations = parse_operations(
        {
            "paths": {
                "/repos/{owner}/{repo}": {"get": {"operationId": "repoGet"}},
                "/user/repos": {"get": {"operationId": "repoListCurrentUser"}},
            }
        }
    )

    async def get_operations(_client):
        return operations

    monkeypatch.setattr("labmcp.gitea_api._get_operations", get_operations)
    provider = GiteaOperationProvider(lambda: client)

    assert {tool.name for tool in await provider.list_tools()} == {
        "gitea_repo_get",
        "gitea_repo_list_current_user",
    }


def test_tool_names_distinguish_acronyms() -> None:
    assert _tool_name("userGetOauth2Application") == "gitea_user_get_oauth2_application"
    assert _tool_name("userGetOAuth2Application") == "gitea_user_get_o_auth2_application"
