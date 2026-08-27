import pytest

from labmcp.pangolin_api import (
    PangolinOperationProvider,
    _get_operations,
    _tool_name,
    call_operation,
    parse_operations,
)


class FakeClient:
    base_url = "https://pangolin.example"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    async def request(self, method: str, path: str, **kwargs: object) -> dict[str, bool]:
        self.calls.append((method, path, kwargs))
        return {"ok": True}


def test_parse_operations_generates_names_without_openapi_operation_ids() -> None:
    operations = parse_operations(
        {
            "paths": {
                "/org/{orgId}/site/{niceId}": {"get": {}},
                "/resource/{resourceId}": {
                    "delete": {},
                    "post": {"requestBody": {"content": {"application/json": {}}}},
                },
                "/upload": {
                    "post": {
                        "requestBody": {
                            "content": {"multipart/form-data": {"schema": {"format": "binary"}}}
                        }
                    }
                },
            }
        }
    )

    assert operations["get:/org/{orgId}/site/{niceId}"].path == "/v1/org/{orgId}/site/{niceId}"
    assert _tool_name("get:/org/{orgId}/site/{niceId}") == (
        "pangolin_get_org_by_orgid_site_by_niceid"
    )
    assert "post:/upload" not in operations


def test_parse_operations_rejects_invalid_or_empty_documents() -> None:
    with pytest.raises(ValueError, match="does not contain paths"):
        parse_operations({})
    with pytest.raises(ValueError, match="no supported operations"):
        parse_operations({"paths": {"/upload": {"post": {"requestBody": {"content": {"multipart/form-data": {"schema": {"format": "binary"}}}}}}}})


@pytest.mark.asyncio
async def test_call_operation_validates_and_encodes_path_parameters() -> None:
    client = FakeClient()
    operations = parse_operations({"paths": {"/org/{orgId}": {"get": {}}}})

    result = await call_operation(
        client,
        "get:/org/{orgId}",
        operations=operations,
        path_params={"orgId": "org/a"},
        query={"page": 2},
    )

    assert result == {"ok": True}
    assert client.calls == [
        ("GET", "/v1/org/org%2Fa", {"params": {"page": 2}, "json": None, "data": None})
    ]


@pytest.mark.asyncio
async def test_call_operation_rejects_invalid_requests() -> None:
    client = FakeClient()
    operations = parse_operations({"paths": {"/org/{orgId}": {"post": {}}}})

    with pytest.raises(ValueError, match="Unknown Pangolin operation"):
        await call_operation(client, "get:/missing", operations=operations)
    with pytest.raises(ValueError, match="requires path_params"):
        await call_operation(client, "post:/org/{orgId}", operations=operations)
    with pytest.raises(ValueError, match="requires a JSON body"):
        await call_operation(
            client,
            "post:/org/{orgId}",
            operations=operations,
            path_params={"orgId": "org"},
            form={"unexpected": "value"},
        )


@pytest.mark.asyncio
async def test_get_operations_caches_live_openapi_document(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient()
    document = {"paths": {"/orgs": {"get": {}}}}

    async def request(method, path, **kwargs):
        client.calls.append((method, path, kwargs))
        return document

    monkeypatch.setattr(client, "request", request)
    monkeypatch.setattr("labmcp.pangolin_api._OPERATIONS_CACHE", {})

    assert set(await _get_operations(client, "/v1")) == {"get:/orgs"}
    assert set(await _get_operations(client, "/v1")) == {"get:/orgs"}
    assert client.calls == [("GET", "/v1/openapi.json", {})]


@pytest.mark.asyncio
async def test_operation_provider_exposes_one_tool_per_openapi_operation(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient()
    operations = parse_operations({"paths": {"/orgs": {"get": {}}, "/org/{orgId}": {"delete": {}}}})

    async def get_operations(_client, _api_path):
        return operations

    monkeypatch.setattr("labmcp.pangolin_api._get_operations", get_operations)
    provider = PangolinOperationProvider(lambda: client)

    assert {tool.name for tool in await provider.list_tools()} == {
        "pangolin_get_orgs",
        "pangolin_delete_org_by_orgid",
    }
