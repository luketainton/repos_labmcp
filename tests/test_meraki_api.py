import httpx
import pytest

from labmcp.meraki_api import (
    MerakiOperationProvider,
    _get_operations,
    call_operation,
    parse_operations,
)


class FakeClient:
    base_url = "https://api.meraki.example"

    def __init__(self) -> None:
        self.calls = []

    async def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return {"ok": True}


def test_parse_openapi_operations_uses_operation_ids_and_skips_binary_uploads() -> None:
    operations = parse_operations(
        {
            "paths": {
                "/organizations/{organizationId}": {
                    "get": {"operationId": "getOrganization"},
                    "put": {
                        "operationId": "updateOrganization",
                        "requestBody": {
                            "content": {"application/json": {"schema": {"type": "object"}}}
                        },
                    },
                },
                "/upload": {
                    "post": {
                        "operationId": "uploadCertificate",
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

    assert operations["getOrganization"].path == "/api/v1/organizations/{organizationId}"
    assert operations["updateOrganization"].encoding == "json"
    assert "uploadCertificate" not in operations


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
        {"paths": {"/organizations/{organizationId}": {"get": {"operationId": "getOrganization"}}}}
    )

    result = await call_operation(
        client,
        "getOrganization",
        operations=operations,
        path_params={"organizationId": "org/1"},
        query={"perPage": 10},
    )

    assert result == {"ok": True}
    assert client.calls == [
        (
            "GET",
            "/api/v1/organizations/org%2F1",
            {"params": {"perPage": 10}, "json": None, "data": None},
        )
    ]


@pytest.mark.asyncio
async def test_call_operation_rejects_invalid_request_shapes() -> None:
    client = FakeClient()
    operations = parse_operations(
        {
            "paths": {
                "/organizations/{organizationId}": {
                    "post": {
                        "operationId": "create",
                        "requestBody": {"content": {"application/json": {}}},
                    }
                }
            }
        }
    )

    with pytest.raises(ValueError, match="Unknown Meraki operation"):
        await call_operation(client, "unknown", operations=operations)
    with pytest.raises(ValueError, match="either body or form"):
        await call_operation(
            client,
            "create",
            operations=operations,
            path_params={"organizationId": "1"},
            body={},
            form={},
        )
    with pytest.raises(ValueError, match="requires a JSON body"):
        await call_operation(
            client, "create", operations=operations, path_params={"organizationId": "1"}, form={}
        )
    with pytest.raises(ValueError, match="requires path_params"):
        await call_operation(client, "create", operations=operations)


@pytest.mark.asyncio
async def test_get_operations_downloads_and_caches_the_upstream_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class OpenAPIResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"paths": {"/organizations": {"get": {"operationId": "getOrganizations"}}}}

    class OpenAPIClient:
        calls = []

        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return OpenAPIResponse()

    monkeypatch.setattr(httpx, "AsyncClient", OpenAPIClient)
    monkeypatch.setattr("labmcp.meraki_api._OPERATIONS_CACHE", {})

    assert set(await _get_operations("https://spec.example/openapi.json", "/api/v1", 5.0)) == {
        "getOrganizations"
    }
    assert set(await _get_operations("https://spec.example/openapi.json", "/api/v1", 5.0)) == {
        "getOrganizations"
    }
    assert OpenAPIClient.calls == [
        ("https://spec.example/openapi.json", {"headers": {"Accept": "application/json"}})
    ]


@pytest.mark.asyncio
async def test_provider_exposes_one_tool_for_each_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeClient()
    provider = MerakiOperationProvider(lambda: client)

    async def get_operations(_url, _api_path, _timeout):
        return parse_operations(
            {"paths": {"/organizations": {"get": {"operationId": "getOrganizations"}}}}
        )

    monkeypatch.setattr("labmcp.meraki_api._get_operations", get_operations)
    assert {tool.name for tool in await provider.list_tools()} == {"meraki_get_organizations"}
