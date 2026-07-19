import pytest

from labmcp.n8n_api import N8NOperationProvider, call_operation, parse_operations


class FakeClient:
    base_url = "https://n8n.example"

    def __init__(self) -> None:
        self.calls = []

    async def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return {"ok": True}


def test_parse_openapi_operations_and_skip_binary_uploads() -> None:
    operations = parse_operations({
        "paths": {
            "/workflows/{id}": {
                "get": {"operationId": "getWorkflow"},
                "post": {"operationId": "updateWorkflow", "requestBody": {
                    "content": {"application/json": {"schema": {"type": "object"}}}
                }},
            },
            "/import": {"post": {"operationId": "importWorkflow", "requestBody": {
                "content": {"multipart/form-data": {"schema": {"type": "string", "format": "binary"}}}
            }}},
        }
    })

    assert operations["getWorkflow"].path == "/api/v1/workflows/{id}"
    assert operations["updateWorkflow"].encoding == "json"
    assert "importWorkflow" not in operations


@pytest.mark.asyncio
async def test_call_operation_encodes_paths_and_forwards_arguments() -> None:
    client = FakeClient()
    operations = parse_operations({"paths": {"/workflows/{id}": {
        "get": {"operationId": "getWorkflow"}
    }}})

    result = await call_operation(
        client, "getWorkflow", operations=operations,
        path_params={"id": "workflow/1"}, query={"include": "tags"},
    )

    assert result == {"ok": True}
    assert client.calls == [("GET", "/api/v1/workflows/workflow%2F1", {
        "params": {"include": "tags"}, "json": None, "data": None
    })]


@pytest.mark.asyncio
async def test_provider_exposes_each_operation(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient()
    provider = N8NOperationProvider(lambda: client)

    async def get_operations(_client, _api_path):
        return parse_operations({"paths": {"/users": {
            "get": {"x-eov-operation-id": "listUsers"}
        }}})

    monkeypatch.setattr("labmcp.n8n_api._get_operations", get_operations)
    assert {tool.name for tool in await provider.list_tools()} == {"n8n_list_users"}
