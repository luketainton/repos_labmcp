import pytest

from labmcp.n8n_api import N8NOperationProvider, _get_operations, call_operation, parse_operations


class FakeClient:
    base_url = "https://n8n.example"

    def __init__(self) -> None:
        self.calls = []

    async def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return {"ok": True}


def test_parse_openapi_operations_and_skip_binary_uploads() -> None:
    operations = parse_operations(
        {
            "paths": {
                "/workflows/{id}": {
                    "get": {"operationId": "getWorkflow"},
                    "post": {
                        "operationId": "updateWorkflow",
                        "requestBody": {
                            "content": {"application/json": {"schema": {"type": "object"}}}
                        },
                    },
                },
                "/import": {
                    "post": {
                        "operationId": "importWorkflow",
                        "requestBody": {
                            "content": {
                                "multipart/form-data": {
                                    "schema": {"type": "string", "format": "binary"}
                                }
                            }
                        },
                    }
                },
            }
        }
    )

    assert operations["getWorkflow"].path == "/api/v1/workflows/{id}"
    assert operations["updateWorkflow"].encoding == "json"
    assert "importWorkflow" not in operations


def test_parse_operations_rejects_invalid_or_duplicate_documents() -> None:
    with pytest.raises(ValueError, match="does not contain paths"):
        parse_operations({})

    with pytest.raises(ValueError, match="Duplicate"):
        parse_operations(
            {
                "paths": {
                    "/one": {"get": {"operationId": "same"}},
                    "/two": {"post": {"operationId": "same"}},
                }
            }
        )

    with pytest.raises(ValueError, match="no supported operations"):
        parse_operations(
            {
                "paths": {
                    "/upload": {
                        "post": {
                            "operationId": "upload",
                            "requestBody": {
                                "content": {"multipart/form-data": {"schema": {"type": "binary"}}}
                            },
                        }
                    }
                }
            }
        )


def test_parse_operations_ignores_invalid_routes_and_methods() -> None:
    operations = parse_operations(
        {
            "paths": {
                1: {"get": {"operationId": "ignored"}},
                "/not-a-map": None,
                "/unsupported": {"head": {"operationId": "ignored"}},
                "/missing-id": {"get": {}},
                "/valid": {"get": {"operationId": "valid"}},
            }
        }
    )

    assert set(operations) == {"valid"}


@pytest.mark.asyncio
async def test_call_operation_encodes_paths_and_forwards_arguments() -> None:
    client = FakeClient()
    operations = parse_operations(
        {"paths": {"/workflows/{id}": {"get": {"operationId": "getWorkflow"}}}}
    )

    result = await call_operation(
        client,
        "getWorkflow",
        operations=operations,
        path_params={"id": "workflow/1"},
        query={"include": "tags"},
    )

    assert result == {"ok": True}
    assert client.calls == [
        (
            "GET",
            "/api/v1/workflows/workflow%2F1",
            {"params": {"include": "tags"}, "json": None, "data": None},
        )
    ]


@pytest.mark.asyncio
async def test_call_operation_rejects_invalid_request_shapes() -> None:
    client = FakeClient()
    operations = parse_operations(
        {
            "paths": {
                "/workflows/{id}": {
                    "post": {
                        "operationId": "update",
                        "requestBody": {"content": {"application/json": {}}},
                    }
                }
            }
        }
    )

    with pytest.raises(ValueError, match="Unknown n8n operation"):
        await call_operation(client, "unknown", operations=operations)
    with pytest.raises(ValueError, match="either body or form"):
        await call_operation(
            client, "update", operations=operations, path_params={"id": "1"}, body={}, form={}
        )
    with pytest.raises(ValueError, match="requires a JSON body"):
        await call_operation(
            client, "update", operations=operations, path_params={"id": "1"}, form={}
        )
    with pytest.raises(ValueError, match="requires path_params"):
        await call_operation(client, "update", operations=operations)


@pytest.mark.asyncio
async def test_call_operation_requires_form_data_for_form_operations() -> None:
    client = FakeClient()
    operations = parse_operations(
        {
            "paths": {
                "/import": {
                    "post": {
                        "operationId": "import",
                        "requestBody": {"content": {"application/x-www-form-urlencoded": {}}},
                    }
                }
            }
        }
    )

    with pytest.raises(ValueError, match="requires form data"):
        await call_operation(client, "import", operations=operations, body={})


@pytest.mark.asyncio
async def test_get_operations_parses_and_caches_yaml_specification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeClient()
    client.base_url = "https://n8n-cache.example"
    document = "paths:\n  /users:\n    get:\n      operationId: listUsers\n"

    async def request(method, path, **kwargs):
        client.calls.append((method, path, kwargs))
        return {"text": document}

    monkeypatch.setattr(client, "request", request)
    monkeypatch.setattr("labmcp.n8n_api._OPERATIONS_CACHE", {})

    assert set(await _get_operations(client, "/api/v1")) == {"listUsers"}
    assert set(await _get_operations(client, "/api/v1")) == {"listUsers"}
    assert client.calls == [("GET", "/api/v1/openapi.yml", {})]


@pytest.mark.asyncio
async def test_get_operations_accepts_string_and_rejects_invalid_documents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeClient()
    client.base_url = "https://n8n-string.example"
    monkeypatch.setattr("labmcp.n8n_api._OPERATIONS_CACHE", {})

    async def yaml_request(method, path, **kwargs):
        return "paths:\n  /users:\n    get:\n      operationId: listUsers\n"

    monkeypatch.setattr(client, "request", yaml_request)
    assert set(await _get_operations(client, "/api/v1")) == {"listUsers"}

    async def invalid_request(method, path, **kwargs):
        return []

    client.base_url = "https://n8n-invalid.example"
    monkeypatch.setattr(client, "request", invalid_request)
    with pytest.raises(ValueError, match="unsupported response"):
        await _get_operations(client, "/api/v1")


@pytest.mark.asyncio
async def test_provider_exposes_each_operation(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient()
    provider = N8NOperationProvider(lambda: client)

    async def get_operations(_client, _api_path):
        return parse_operations({"paths": {"/users": {"get": {"x-eov-operation-id": "listUsers"}}}})

    monkeypatch.setattr("labmcp.n8n_api._get_operations", get_operations)
    assert {tool.name for tool in await provider.list_tools()} == {"n8n_list_users"}
