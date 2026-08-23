import pytest

from labmcp.shlink_api import ShlinkOperationProvider, call_operation


class FakeClient:
    base_url = "https://links.example"

    def __init__(self) -> None:
        self.calls = []

    async def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return {"ok": True}


@pytest.mark.asyncio
async def test_call_operation_uses_configured_version_and_encodes_path_parameters() -> None:
    client = FakeClient()

    result = await call_operation(
        client,
        "parse_short_code",
        api_version="3",
        path_params={"shortCode": "campaign/summer"},
        query={"domain": "links.example"},
    )

    assert result == {"ok": True}
    assert client.calls == [(
        "GET", "/rest/v3/short-urls/campaign%2Fsummer",
        {"params": {"domain": "links.example"}, "json": None},
    )]


@pytest.mark.asyncio
async def test_provider_exposes_documented_management_operations() -> None:
    provider = ShlinkOperationProvider(lambda: FakeClient())

    names = {tool.name for tool in await provider.list_tools()}

    assert {
        "shlink_create_short_url",
        "shlink_list_short_urls",
        "shlink_set_short_url_redirect_rules",
        "shlink_list_domains",
        "shlink_health",
    } <= names
