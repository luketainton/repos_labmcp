from types import SimpleNamespace

import httpx
import pytest
from fastmcp.exceptions import ToolError

from labmcp.clients import (
    Action1Client, ServiceClient, action1_client, gitea_client, n8n_client, pocket_id_client,
    shlink_client,
)


class RecordingAsyncClient:
    response_kwargs = {"json": {"ok": True}}
    requests: list[dict] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def request(self, method, url, **kwargs):
        self.requests.append({"method": method, "url": url, **kwargs})
        return httpx.Response(
            200,
            request=httpx.Request(method, url),
            **self.response_kwargs,
        )


@pytest.fixture(autouse=True)
def clear_recorded_requests():
    RecordingAsyncClient.requests.clear()


@pytest.mark.asyncio
async def test_service_client_builds_url_and_returns_json(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", RecordingAsyncClient)
    client = ServiceClient("https://service.example/", "secret", 5.0, auth_prefix="token")

    result = await client.request("GET", "/api/status", params={"page": 1})

    assert result == {"ok": True}
    assert RecordingAsyncClient.requests == [
        {
            "method": "GET",
            "url": "https://service.example/api/status",
            "params": {"page": 1},
            "json": None,
            "headers": {"Accept": "application/json", "Authorization": "token secret"},
        }
    ]


@pytest.mark.asyncio
async def test_service_client_returns_text_for_non_json_response(monkeypatch):
    class TextClient(RecordingAsyncClient):
        response_kwargs = {"text": "healthy"}

    monkeypatch.setattr(httpx, "AsyncClient", TextClient)

    result = await ServiceClient("https://service.example", None, 5.0).request("GET", "/health")

    assert result == {"status_code": 200, "text": "healthy"}


@pytest.mark.asyncio
async def test_service_client_sends_form_data_and_handles_empty_responses(monkeypatch):
    class EmptyResponseClient(RecordingAsyncClient):
        response_kwargs = {}

    monkeypatch.setattr(httpx, "AsyncClient", EmptyResponseClient)

    result = await ServiceClient("https://service.example", None, 5.0).request(
        "POST", "/messages", data={"message": "hello"}
    )

    assert result == {"status_code": 200}
    assert EmptyResponseClient.requests[0]["data"] == {"message": "hello"}


@pytest.mark.asyncio
async def test_service_client_surfaces_upstream_error_details_to_tools(monkeypatch):
    class ConflictClient(RecordingAsyncClient):
        async def request(self, method, url, **kwargs):
            self.requests.append({"method": method, "url": url, **kwargs})
            return httpx.Response(
                409,
                request=httpx.Request(method, url),
                json={"message": "pull request is not mergeable"},
            )

    monkeypatch.setattr(httpx, "AsyncClient", ConflictClient)

    with pytest.raises(
        ToolError,
        match=r"POST /api/v1/repos/alice/notes/pulls/7/merge failed with 409: .*not mergeable",
    ):
        await ServiceClient("https://service.example", None, 5.0).request(
            "POST", "/api/v1/repos/alice/notes/pulls/7/merge", json={"Do": "merge"}
        )


def test_service_clients_use_service_specific_auth_headers():
    settings = SimpleNamespace(
        gitea_url="https://gitea.example",
        gitea_token=SimpleNamespace(get_secret_value=lambda: "gitea-secret"),
        pocket_id_url="https://pocket.example",
        pocket_id_token=SimpleNamespace(get_secret_value=lambda: "pocket-secret"),
        shlink_url="https://links.example",
        shlink_api_key=SimpleNamespace(get_secret_value=lambda: "shlink-secret"),
        n8n_url="https://n8n.example",
        n8n_api_key=SimpleNamespace(get_secret_value=lambda: "n8n-secret"),
        http_timeout=10.0,
    )

    gitea = gitea_client(settings)
    pocket_id = pocket_id_client(settings)
    shlink = shlink_client(settings)
    n8n = n8n_client(settings)

    assert (gitea.auth_header, gitea.auth_prefix, gitea.token) == (
        "Authorization",
        "token",
        "gitea-secret",
    )
    assert (pocket_id.auth_header, pocket_id.auth_prefix, pocket_id.token) == (
        "X-API-KEY",
        "",
        "pocket-secret",
    )
    assert (shlink.auth_header, shlink.auth_prefix, shlink.token) == (
        "X-Api-Key",
        "",
        "shlink-secret",
    )
    assert (n8n.auth_header, n8n.auth_prefix, n8n.token) == (
        "X-N8N-API-KEY",
        "",
        "n8n-secret",
    )


@pytest.mark.asyncio
async def test_action1_client_exchanges_and_caches_client_credentials(monkeypatch):
    class Action1RecordingClient(RecordingAsyncClient):
        async def post(self, url, **kwargs):
            self.requests.append({"method": "POST", "url": url, **kwargs})
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={"access_token": "action1-token", "expires_in": 3600},
            )

    monkeypatch.setattr(httpx, "AsyncClient", Action1RecordingClient)
    settings = SimpleNamespace(
        action1_url="https://app.eu.action1.com/api/3.0",
        action1_client_id="client-id",
        action1_client_secret=SimpleNamespace(get_secret_value=lambda: "client-secret"),
        http_timeout=10.0,
    )
    client = action1_client(settings)

    await client.request("GET", "/me")
    await client.request("GET", "/me")

    assert isinstance(client, Action1Client)
    assert Action1RecordingClient.requests[0] == {
        "method": "POST",
        "url": "https://app.eu.action1.com/api/3.0/oauth2/token",
        "headers": {"Content-Type": "application/x-www-form-urlencoded"},
        "data": {"client_id": "client-id", "client_secret": "client-secret"},
    }
    assert [request["headers"]["Authorization"] for request in Action1RecordingClient.requests[1:]] == [
        "Bearer action1-token",
        "Bearer action1-token",
    ]


@pytest.mark.asyncio
async def test_action1_client_requires_credentials() -> None:
    client = Action1Client("https://app.action1.com/api/3.0", None, None, 10.0)

    with pytest.raises(RuntimeError, match="ACTION1_CLIENT_ID and ACTION1_CLIENT_SECRET"):
        await client._access_token()


@pytest.mark.asyncio
async def test_action1_client_rejects_failed_or_invalid_token_responses(monkeypatch) -> None:
    class InvalidTokenClient(RecordingAsyncClient):
        async def post(self, url, **kwargs):
            return httpx.Response(200, request=httpx.Request("POST", url), json={})

    monkeypatch.setattr(httpx, "AsyncClient", InvalidTokenClient)
    client = Action1Client("https://app.action1.com/api/3.0", "client", "secret", 10.0)

    with pytest.raises(ToolError, match="did not include access_token"):
        await client._access_token()

    class FailedTokenClient(RecordingAsyncClient):
        async def post(self, url, **kwargs):
            return httpx.Response(401, request=httpx.Request("POST", url), text="invalid credentials")

    monkeypatch.setattr(httpx, "AsyncClient", FailedTokenClient)
    client = Action1Client("https://app.action1.com/api/3.0", "client", "secret", 10.0)

    with pytest.raises(ToolError, match="OAuth token request failed with 401"):
        await client._access_token()


def test_service_client_requires_a_base_url():
    with pytest.raises(RuntimeError, match="not configured"):
        ServiceClient(None, None, 5.0)._url("/health")
