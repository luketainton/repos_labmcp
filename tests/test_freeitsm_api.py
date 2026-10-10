import json
import logging
from types import SimpleNamespace

import pytest
from fastmcp.server.middleware import MiddlewareContext

from labmcp.clients import ServiceClient
from labmcp.freeitsm_api import (
    FreeITSMOperationProvider,
    FreeITSMOperation,
    _get_operations,
    _make_operation_tool,
    call_operation,
    parse_operations,
)
from labmcp.tool_logging import ToolCallLoggingMiddleware, logger


class FakeClient:
    base_url = "https://itsm.example"

    def __init__(self) -> None:
        self.calls = []

    async def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return {"data": {"ok": True}}


def test_parse_openapi_operations_uses_operation_ids_and_skips_unsupported_bodies() -> None:
    operations = parse_operations(
        {
            "paths": {
                "/tickets/{id}": {
                    "get": {"operationId": "get_tickets_id"},
                    "patch": {
                        "operationId": "patch_tickets_id",
                        "requestBody": {
                            "content": {"application/json": {"schema": {"type": "object"}}}
                        },
                    },
                },
                "/attachments": {
                    "post": {
                        "operationId": "post_attachments",
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

    assert operations["get_tickets_id"].path == "/api/v1/tickets/{id}"
    assert operations["patch_tickets_id"].encoding == "json"
    assert "post_attachments" not in operations


def test_parse_operations_rejects_invalid_duplicate_and_empty_documents() -> None:
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
                            "operationId": "post_upload",
                            "requestBody": {
                                "content": {
                                    "multipart/form-data": {
                                        "schema": {"type": "string", "format": "binary"}
                                    }
                                }
                            },
                        }
                    }
                }
            }
        )


@pytest.mark.asyncio
async def test_call_operation_encodes_paths_and_forwards_arguments() -> None:
    client = FakeClient()
    operations = parse_operations(
        {
            "paths": {
                "/tickets/{id}": {
                    "post": {
                        "operationId": "post_tickets_id",
                        "requestBody": {"content": {"application/json": {}}},
                    }
                }
            }
        }
    )

    result = await call_operation(
        client,
        "post_tickets_id",
        operations=operations,
        path_params={"id": "ticket/1"},
        query={"page": 2},
        body={"title": "Printer offline"},
    )

    assert result == {"data": {"ok": True}}
    assert client.calls == [
        (
            "POST",
            "/api/v1/tickets/ticket%2F1",
            {"params": {"page": 2}, "json": {"title": "Printer offline"}},
        )
    ]


@pytest.mark.asyncio
async def test_call_operation_rejects_unknown_and_invalid_parameters() -> None:
    client = FakeClient()
    operations = parse_operations(
        {
            "paths": {
                "/tickets/{id}": {
                    "post": {
                        "operationId": "post_tickets_id",
                        "requestBody": {"content": {"application/json": {}}},
                    }
                }
            }
        }
    )

    with pytest.raises(ValueError, match="Unknown FreeITSM operation"):
        await call_operation(client, "missing", operations=operations)
    with pytest.raises(ValueError, match="requires path_params"):
        await call_operation(client, "post_tickets_id", operations=operations)


@pytest.mark.asyncio
async def test_get_operations_loads_and_caches_the_openapi_document(monkeypatch) -> None:
    client = FakeClient()
    document = {"paths": {"/ping": {"get": {"operationId": "get_ping"}}}}

    async def request(method, path, **kwargs):
        client.calls.append((method, path, kwargs))
        return document

    monkeypatch.setattr(client, "request", request)
    monkeypatch.setattr("labmcp.freeitsm_api._OPERATIONS_CACHE", {})

    assert set(await _get_operations(client, "/api/v1")) == {"get_ping"}
    assert set(await _get_operations(client, "/api/v1")) == {"get_ping"}
    assert client.calls == [("GET", "/api/v1/openapi.json", {})]


@pytest.mark.asyncio
async def test_provider_exposes_one_prefixed_tool_per_operation(monkeypatch) -> None:
    client = FakeClient()
    operations = parse_operations({"paths": {"/ping": {"get": {"operationId": "get_ping"}}}})

    async def get_operations(_client, _api_path):
        return operations

    monkeypatch.setattr("labmcp.freeitsm_api._get_operations", get_operations)
    provider = FreeITSMOperationProvider(lambda: client)

    assert {tool.name for tool in await provider.list_tools()} == {"freeitsm_get_ping"}


def test_freeitsm_client_uses_bearer_api_key() -> None:
    from labmcp.clients import freeitsm_client

    settings = SimpleNamespace(
        freeitsm_url="https://itsm.example",
        freeitsm_api_key=SimpleNamespace(get_secret_value=lambda: "fitsm_secret"),
        http_timeout=10.0,
    )

    client = freeitsm_client(settings)

    assert (client.auth_header, client.auth_prefix, client.token) == (
        "Authorization",
        "Bearer",
        "fitsm_secret",
    )


def test_freeitsm_client_reports_missing_configuration() -> None:
    from labmcp.clients import freeitsm_client

    with pytest.raises(RuntimeError, match="Set FREEITSM_URL"):
        freeitsm_client(SimpleNamespace(freeitsm_url=None, freeitsm_api_key=None))
    with pytest.raises(RuntimeError, match="Set FREEITSM_API_KEY"):
        freeitsm_client(SimpleNamespace(freeitsm_url="https://itsm.example", freeitsm_api_key=None))


@pytest.mark.asyncio
async def test_freeitsm_request_sends_the_api_key_as_a_bearer_token(monkeypatch) -> None:
    import httpx

    from labmcp.clients import freeitsm_client

    class RecordingClient:
        calls = []

        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def request(self, method, url, **kwargs):
            self.calls.append((method, url, kwargs))
            return httpx.Response(
                200, request=httpx.Request(method, url), json={"data": {"ok": True}}
            )

    monkeypatch.setattr(httpx, "AsyncClient", RecordingClient)
    client = freeitsm_client(
        SimpleNamespace(
            freeitsm_url="https://itsm.example",
            freeitsm_api_key=SimpleNamespace(get_secret_value=lambda: "fitsm_secret"),
            http_timeout=10.0,
        )
    )

    assert await client.request("GET", "/api/v1/ping") == {"data": {"ok": True}}
    assert RecordingClient.calls[0][2]["headers"]["Authorization"] == "Bearer fitsm_secret"


@pytest.mark.asyncio
async def test_freeitsm_key_is_absent_from_tool_schema_and_call_logs(monkeypatch, caplog) -> None:
    secret = "fitsm_secret"
    operation = FreeITSMOperation("GET", "/api/v1/ping", "none")
    tool = _make_operation_tool(
        "get_ping",
        operation,
        {"get_ping": operation},
        lambda: ServiceClient("https://itsm.example", secret, 10.0),
        None,
    )
    assert secret not in json.dumps(tool.parameters)
    assert "api_key" not in tool.parameters["properties"]

    monkeypatch.setattr("labmcp.tool_logging.get_access_token", lambda: None)
    context = MiddlewareContext(
        message=SimpleNamespace(
            name=tool.name,
            arguments={"path_params": {}, "query": {}, "body": None},
        ),
        method="tools/call",
    )

    async def call_next(_context):
        return {"data": {"ok": True}}

    with caplog.at_level(logging.INFO, logger=logger.name):
        await ToolCallLoggingMiddleware().on_call_tool(context, call_next)

    assert secret not in caplog.text
