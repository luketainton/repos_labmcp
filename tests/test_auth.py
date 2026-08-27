import sys
import types
from types import SimpleNamespace

import pytest

from labmcp.auth import (
    _decode_jwt_claims,
    create_auth_provider,
    ensure_network_transport_is_authenticated,
)
from labmcp.config import Settings


def test_stdio_allows_no_auth() -> None:
    settings = Settings(mcp_transport="stdio", mcp_auth_mode="none")

    ensure_network_transport_is_authenticated(settings)


def test_network_transport_requires_auth() -> None:
    settings = Settings(mcp_transport="sse", mcp_auth_mode="none")

    with pytest.raises(RuntimeError, match="MCP_AUTH_MODE=jwt or oidc_proxy"):
        ensure_network_transport_is_authenticated(settings)


def test_jwt_auth_requires_audience() -> None:
    settings = Settings(
        pocket_id_url="https://id.example.com",
        mcp_auth_mode="jwt",
    )

    with pytest.raises(RuntimeError, match="MCP_AUTH_JWT_AUDIENCE"):
        create_auth_provider(settings)


def test_jwt_auth_requires_issuer_and_public_base_url() -> None:
    with pytest.raises(RuntimeError, match="MCP_AUTH_JWT_ISSUER or POCKET_ID_URL"):
        create_auth_provider(Settings(mcp_auth_mode="jwt"))

    with pytest.raises(RuntimeError, match="MCP_AUTH_BASE_URL"):
        create_auth_provider(
            Settings(
                pocket_id_url="https://id.example.com",
                mcp_auth_mode="jwt",
                mcp_auth_jwt_audience="https://labmcp.example.com/mcp",
            )
        )


def test_jwt_auth_derives_pocket_id_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeJWTVerifier:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeRemoteAuthProvider:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    jwt_module = types.ModuleType("fastmcp.server.auth.providers.jwt")
    jwt_module.JWTVerifier = FakeJWTVerifier
    monkeypatch.setitem(sys.modules, "fastmcp.server.auth.providers.jwt", jwt_module)
    auth_module = types.ModuleType("fastmcp.server.auth")
    auth_module.RemoteAuthProvider = FakeRemoteAuthProvider
    monkeypatch.setitem(sys.modules, "fastmcp.server.auth", auth_module)

    settings = Settings(
        pocket_id_url="https://id.example.com/",
        mcp_auth_mode="jwt",
        mcp_auth_base_url="https://labmcp.example.com/",
        mcp_auth_jwt_audience="https://labmcp.example.com/mcp",
        mcp_auth_required_scopes="openid, profile",
    )

    provider = create_auth_provider(settings)

    assert isinstance(provider, FakeRemoteAuthProvider)
    assert provider.kwargs["authorization_servers"] == ["https://id.example.com"]
    assert provider.kwargs["base_url"] == "https://labmcp.example.com"
    assert provider.kwargs["scopes_supported"] == ["openid", "profile"]
    token_verifier = provider.kwargs["token_verifier"]
    assert isinstance(token_verifier, FakeJWTVerifier)
    assert token_verifier.kwargs == {
        "jwks_uri": "https://id.example.com/.well-known/jwks.json",
        "issuer": "https://id.example.com",
        "audience": "https://labmcp.example.com/mcp",
        "required_scopes": ["openid", "profile"],
    }


@pytest.mark.asyncio
async def test_jwt_verifier_requires_a_subject_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeJWTVerifier:
        result = None

        def __init__(self, **kwargs: object) -> None:
            pass

        async def verify_token(self, token: str):
            return self.result

    class FakeRemoteAuthProvider:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    jwt_module = types.ModuleType("fastmcp.server.auth.providers.jwt")
    jwt_module.JWTVerifier = FakeJWTVerifier
    monkeypatch.setitem(sys.modules, "fastmcp.server.auth.providers.jwt", jwt_module)
    auth_module = types.ModuleType("fastmcp.server.auth")
    auth_module.RemoteAuthProvider = FakeRemoteAuthProvider
    monkeypatch.setitem(sys.modules, "fastmcp.server.auth", auth_module)
    provider = create_auth_provider(
        Settings(
            pocket_id_url="https://id.example.com",
            mcp_auth_mode="jwt",
            mcp_auth_base_url="https://labmcp.example.com",
            mcp_auth_jwt_audience="https://labmcp.example.com/mcp",
        )
    )
    verifier = provider.kwargs["token_verifier"]

    FakeJWTVerifier.result = SimpleNamespace(claims={})
    assert await verifier.verify_token("token") is None
    FakeJWTVerifier.result = SimpleNamespace(claims={"sub": "alice"})
    assert (await verifier.verify_token("token")).claims == {"sub": "alice"}


def test_jwt_auth_advertises_service_scopes(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeJWTVerifier:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeRemoteAuthProvider:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    jwt_module = types.ModuleType("fastmcp.server.auth.providers.jwt")
    jwt_module.JWTVerifier = FakeJWTVerifier
    monkeypatch.setitem(sys.modules, "fastmcp.server.auth.providers.jwt", jwt_module)
    auth_module = types.ModuleType("fastmcp.server.auth")
    auth_module.RemoteAuthProvider = FakeRemoteAuthProvider
    monkeypatch.setitem(sys.modules, "fastmcp.server.auth", auth_module)

    provider = create_auth_provider(
        Settings(
            pocket_id_url="https://id.example.com",
            mcp_auth_mode="jwt",
            mcp_auth_base_url="https://labmcp.example.com",
            mcp_auth_jwt_audience="https://labmcp.example.com/mcp",
            mcp_auth_required_scopes="labmcp:connect",
            mcp_service_scopes={
                "gitea": ["labmcp:gitea"],
                "pocket_id": ["labmcp:pocket-id", "labmcp:connect"],
            },
        )
    )

    assert provider.kwargs["scopes_supported"] == [
        "labmcp:connect",
        "labmcp:gitea",
        "labmcp:pocket-id",
    ]


def test_oidc_proxy_requires_public_base_url() -> None:
    settings = Settings(
        pocket_id_url="https://id.example.com",
        mcp_auth_mode="oidc_proxy",
        mcp_auth_oidc_client_id="labmcp",
        mcp_auth_oidc_client_secret="secret",
    )

    with pytest.raises(RuntimeError, match="MCP_AUTH_BASE_URL"):
        create_auth_provider(settings)


def test_oidc_proxy_requires_config_and_client_credentials() -> None:
    with pytest.raises(RuntimeError, match="MCP_AUTH_OIDC_CONFIG_URL or POCKET_ID_URL"):
        create_auth_provider(Settings(mcp_auth_mode="oidc_proxy", mcp_auth_base_url="https://labmcp.example.com"))

    with pytest.raises(RuntimeError, match="MCP_AUTH_OIDC_CLIENT_ID"):
        create_auth_provider(
            Settings(
                pocket_id_url="https://id.example.com",
                mcp_auth_mode="oidc_proxy",
                mcp_auth_base_url="https://labmcp.example.com",
            )
        )


def test_oidc_proxy_derives_pocket_id_config_url(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeOIDCProxy:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            self.advertised_scopes: list[str] | None = None

        def update_default_scopes(self, scopes: list[str]) -> None:
            self.advertised_scopes = scopes

        def _build_upstream_authorize_url(
            self, txn_id: str, transaction: dict[str, object]
        ) -> dict[str, object]:
            return transaction

    oidc_module = types.ModuleType("fastmcp.server.auth.oidc_proxy")
    oidc_module.OIDCProxy = FakeOIDCProxy
    monkeypatch.setitem(sys.modules, "fastmcp.server.auth.oidc_proxy", oidc_module)

    settings = Settings(
        pocket_id_url="https://id.example.com/",
        mcp_auth_mode="oidc_proxy",
        mcp_auth_base_url="https://labmcp.example.com/",
        mcp_auth_oidc_client_id="labmcp",
        mcp_auth_oidc_client_secret="secret",
        mcp_auth_oidc_jwt_signing_key="signing-key",
        mcp_auth_oidc_forward_resource=True,
        mcp_auth_jwt_audience="labmcp",
        mcp_auth_required_scopes="openid, profile",
    )

    provider = create_auth_provider(settings)

    assert isinstance(provider, FakeOIDCProxy)
    assert provider.kwargs == {
        "config_url": "https://id.example.com/.well-known/openid-configuration",
        "client_id": "labmcp",
        "client_secret": "secret",
        "base_url": "https://labmcp.example.com",
        "redirect_path": "/auth/callback",
        "required_scopes": ["openid", "profile"],
        "forward_resource": True,
        "enable_cimd": True,
        "audience": "labmcp",
        "jwt_signing_key": "signing-key",
    }

    assert provider._build_upstream_authorize_url(
        "transaction", {"scopes": ["openid", "profile"]}
    )["scopes"] == ["openid", "profile", "offline_access"]
    assert provider.advertised_scopes == ["openid", "profile", "offline_access"]


def test_oidc_proxy_supports_configured_extra_scopes(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeOIDCProxy:
        def __init__(self, **kwargs: object) -> None:
            pass

        def update_default_scopes(self, scopes: list[str]) -> None:
            pass

        def _build_upstream_authorize_url(
            self, txn_id: str, transaction: dict[str, object]
        ) -> dict[str, object]:
            return transaction

    oidc_module = types.ModuleType("fastmcp.server.auth.oidc_proxy")
    oidc_module.OIDCProxy = FakeOIDCProxy
    monkeypatch.setitem(sys.modules, "fastmcp.server.auth.oidc_proxy", oidc_module)

    settings = Settings(
        pocket_id_url="https://id.example.com",
        mcp_auth_mode="oidc_proxy",
        mcp_auth_base_url="https://labmcp.example.com",
        mcp_auth_oidc_client_id="labmcp",
        mcp_auth_oidc_client_secret="secret",
        mcp_auth_oidc_extra_scopes="offline_access,groups",
    )

    provider = create_auth_provider(settings)

    assert provider._build_upstream_authorize_url(
        "transaction", {"scopes": ["openid", "offline_access"]}
    )["scopes"] == ["openid", "offline_access", "groups"]


@pytest.mark.asyncio
async def test_oidc_proxy_extracts_group_claim_from_access_token(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeOIDCProxy:
        def __init__(self, **kwargs: object) -> None:
            pass

        def update_default_scopes(self, scopes: list[str]) -> None:
            pass

    oidc_module = types.ModuleType("fastmcp.server.auth.oidc_proxy")
    oidc_module.OIDCProxy = FakeOIDCProxy
    monkeypatch.setitem(sys.modules, "fastmcp.server.auth.oidc_proxy", oidc_module)
    provider = create_auth_provider(
        Settings(
            pocket_id_url="https://id.example.com",
            mcp_auth_mode="oidc_proxy",
            mcp_auth_base_url="https://labmcp.example.com",
            mcp_auth_oidc_client_id="labmcp",
            mcp_auth_oidc_client_secret="secret",
        )
    )

    token = "e30.eyJncm91cHMiOlsiYWRtaW4iXX0."
    assert await provider._extract_upstream_claims({"access_token": token}) == {"groups": ["admin"]}
    assert await provider._extract_upstream_claims({"access_token": "opaque"}) is None


def test_decode_jwt_claims_extracts_payload() -> None:
    token = "eyJhbGciOiJub25lIn0.eyJncm91cHMiOlsiZ29kbW9kZSJdfQ."

    assert _decode_jwt_claims(token) == {"groups": ["godmode"]}


def test_decode_jwt_claims_ignores_opaque_tokens() -> None:
    assert _decode_jwt_claims("opaque-access-token") == {}


@pytest.mark.parametrize("token", [None, "one.two", "a.not-base64.c", "e30.bnVsbA.c"])
def test_decode_jwt_claims_ignores_malformed_payloads(token: str | None) -> None:
    assert _decode_jwt_claims(token) == {}
