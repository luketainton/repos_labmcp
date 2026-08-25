from types import SimpleNamespace

import pytest

from labmcp.pushover_api import PushoverClient, PushoverOperationProvider, pushover_client


class FakeClient:
    def __init__(self) -> None:
        self.payloads = []

    async def send_notification(self, payload):
        self.payloads.append(payload)
        return {"status": 1}


@pytest.mark.asyncio
async def test_send_notification_uses_only_non_empty_optional_values() -> None:
    client = FakeClient()
    provider = PushoverOperationProvider(lambda: client)
    tool = (await provider.list_tools())[0]

    result = await tool.fn(message="Backup complete", title="Lab", html=True, priority=1)

    assert result == {"status": 1}
    assert client.payloads == [
        {"message": "Backup complete", "title": "Lab", "html": 1, "priority": 1}
    ]
    assert tool.annotations.model_dump(exclude_none=True) == {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    }


@pytest.mark.asyncio
async def test_send_notification_rejects_empty_message() -> None:
    provider = PushoverOperationProvider(lambda: FakeClient())
    tool = (await provider.list_tools())[0]

    with pytest.raises(ValueError, match="message must not be empty"):
        await tool.fn(message="  ")


@pytest.mark.asyncio
async def test_emergency_priority_requires_valid_retry_and_expiry() -> None:
    provider = PushoverOperationProvider(lambda: FakeClient())
    tool = (await provider.list_tools())[0]

    with pytest.raises(ValueError, match="requires retry and expire"):
        await tool.fn(message="Urgent", priority=2)

    with pytest.raises(ValueError, match="at least 30"):
        await tool.fn(message="Urgent", priority=2, retry=29, expire=60)

    with pytest.raises(ValueError, match="between 1 and 10800"):
        await tool.fn(message="Urgent", priority=2, retry=30, expire=10801)


@pytest.mark.asyncio
async def test_send_notification_validates_priority_and_ttl() -> None:
    provider = PushoverOperationProvider(lambda: FakeClient())
    tool = (await provider.list_tools())[0]

    with pytest.raises(ValueError, match="priority must be"):
        await tool.fn(message="Status", priority=3)

    with pytest.raises(ValueError, match="ttl must be positive"):
        await tool.fn(message="Status", ttl=0)


@pytest.mark.asyncio
async def test_client_adds_credentials_only_to_form_data(monkeypatch) -> None:
    settings = SimpleNamespace(
        pushover_api_url="https://api.pushover.net",
        http_timeout=20.0,
        pushover_app_token=SimpleNamespace(get_secret_value=lambda: "app-token"),
        pushover_user_key=SimpleNamespace(get_secret_value=lambda: "user-key"),
    )
    client = PushoverClient(settings)
    calls = []

    async def request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {"status": 1}

    monkeypatch.setattr(client, "request", request)

    assert await client.send_notification({"message": "hello"}) == {"status": 1}
    assert calls == [
        (
            "POST",
            "/1/messages.json",
            {"data": {"token": "app-token", "user": "user-key", "message": "hello"}},
        )
    ]


@pytest.mark.asyncio
async def test_client_requires_both_server_side_credentials() -> None:
    settings = SimpleNamespace(
        pushover_api_url="https://api.pushover.net",
        http_timeout=20.0,
        pushover_app_token=None,
        pushover_user_key=None,
    )

    with pytest.raises(RuntimeError, match="PUSHOVER_APP_TOKEN and PUSHOVER_USER_KEY"):
        await PushoverClient(settings).send_notification({"message": "hello"})


def test_client_factory_creates_a_pushover_client() -> None:
    settings = SimpleNamespace(
        pushover_api_url="https://api.pushover.net",
        http_timeout=20.0,
        pushover_app_token=None,
        pushover_user_key=None,
    )

    assert isinstance(pushover_client(settings), PushoverClient)
