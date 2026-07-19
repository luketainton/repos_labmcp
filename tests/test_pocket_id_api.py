import pytest

from labmcp.pocket_id_api import OPERATIONS, PocketIDOperationProvider, call_operation


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    async def request(self, method: str, path: str, **kwargs: object) -> dict[str, bool]:
        self.calls.append((method, path, kwargs))
        return {"ok": True}


@pytest.mark.asyncio
async def test_operation_provider_exposes_one_tool_per_supported_operation() -> None:
    provider = PocketIDOperationProvider(lambda: FakeClient())
    names = {tool.name for tool in await provider.list_tools()}

    assert {
        "pocket_id_list_users",
        "pocket_id_list_user_groups",
        "pocket_id_list_oidc_clients",
        "pocket_id_list_api_keys",
    } <= names
    assert len(names) == len(OPERATIONS)


@pytest.mark.asyncio
async def test_call_operation_renders_and_encodes_path_parameters() -> None:
    client = FakeClient()

    result = await call_operation(
        client,
        "get_user_by_id",
        path_params={"id": "user/a"},
        query={"pagination[page]": 2},
    )

    assert result == {"ok": True}
    assert client.calls == [
        (
            "GET",
            "/api/users/user%2Fa",
            {"params": {"pagination[page]": 2}, "json": None, "data": None},
        )
    ]


@pytest.mark.asyncio
async def test_form_operation_uses_form_encoding() -> None:
    client = FakeClient()

    await call_operation(client, "introspect_oidc_tokens", form={"token": "token-value"})

    assert client.calls[0] == (
        "POST",
        "/api/oidc/introspect",
        {"params": None, "json": None, "data": {"token": "token-value"}},
    )


@pytest.mark.asyncio
async def test_call_operation_rejects_unknown_or_incomplete_routes() -> None:
    client = FakeClient()

    with pytest.raises(ValueError, match="Unknown Pocket ID operation"):
        await call_operation(client, "anything")
    with pytest.raises(ValueError, match="requires path_params"):
        await call_operation(client, "get_user_by_id")
