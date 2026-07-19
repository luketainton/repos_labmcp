import pytest

from labmcp.pocket_id_api import call_operation, list_operations


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    async def request(self, method: str, path: str, **kwargs: object) -> dict[str, bool]:
        self.calls.append((method, path, kwargs))
        return {"ok": True}


def test_operation_inventory_covers_core_pocket_id_resources() -> None:
    names = {operation["operation"] for operation in list_operations()}

    assert {"list_users", "list_user_groups", "list_oidc_clients", "list_api_keys"} <= names
    assert "update_client_logo" not in names


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
