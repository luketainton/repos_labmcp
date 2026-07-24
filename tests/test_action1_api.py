import pytest

from labmcp.action1_api import Action1OperationProvider, call_operation


class FakeClient:
    base_url = "https://app.action1.com/api/3.0"

    def __init__(self) -> None:
        self.calls = []

    async def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return {"ok": True}


@pytest.mark.asyncio
async def test_call_operation_encodes_paths_and_forwards_arguments() -> None:
    client = FakeClient()

    result = await call_operation(
        client,
        "get_endpoint",
        path_params={"orgId": "acme/eu", "endpointId": "endpoint/1"},
        query={"details": True},
    )

    assert result == {"ok": True}
    assert client.calls == [("GET", "/endpoints/managed/acme%2Feu/endpoint%2F1", {
        "params": {"details": True}, "json": None
    })]


@pytest.mark.asyncio
async def test_provider_exposes_individual_action1_tools() -> None:
    provider = Action1OperationProvider(FakeClient)

    names = {tool.name for tool in await provider.list_tools()}

    assert {"action1_list_endpoints", "action1_get_report", "action1_apply_automation"} <= names
