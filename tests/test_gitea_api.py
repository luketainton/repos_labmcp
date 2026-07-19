import pytest

from labmcp.gitea_api import call_operation, parse_operations


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
