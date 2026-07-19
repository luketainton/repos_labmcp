import sys
import types

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


def test_jwt_auth_derives_pocket_id_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeJWTVerifier:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    jwt_module = types.ModuleType("fastmcp.server.auth.providers.jwt")
    jwt_module.JWTVerifier = FakeJWTVerifier
    monkeypatch.setitem(sys.modules, "fastmcp.server.auth.providers.jwt", jwt_module)

    settings = Settings(
        pocket_id_url="https://id.example.com/",
        mcp_auth_mode="jwt",
        mcp_auth_jwt_audience="labmcp",
        mcp_auth_required_scopes="openid, profile",
    )

    provider = create_auth_provider(settings)

    assert isinstance(provider, FakeJWTVerifier)
    assert provider.kwargs == {
        "jwks_uri": "https://id.example.com/.well-known/jwks.json",
        "issuer": "https://id.example.com",
        "audience": "labmcp",
        "required_scopes": ["openid", "profile"],
    }


def test_oidc_proxy_requires_public_base_url() -> None:
    settings = Settings(
        pocket_id_url="https://id.example.com",
        mcp_auth_mode="oidc_proxy",
        mcp_auth_oidc_client_id="labmcp",
        mcp_auth_oidc_client_secret="secret",
    )

    with pytest.raises(RuntimeError, match="MCP_AUTH_BASE_URL"):
        create_auth_provider(settings)


def test_oidc_proxy_derives_pocket_id_config_url(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeOIDCProxy:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

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
        "audience": "labmcp",
        "jwt_signing_key": "signing-key",
    }

    assert provider._build_upstream_authorize_url(
        "transaction", {"scopes": ["openid", "profile"]}
    )["scopes"] == ["openid", "profile", "offline_access"]


def test_oidc_proxy_supports_configured_extra_scopes(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeOIDCProxy:
        def __init__(self, **kwargs: object) -> None:
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


def test_decode_jwt_claims_extracts_payload() -> None:
    token = "eyJhbGciOiJub25lIn0.eyJncm91cHMiOlsiZ29kbW9kZSJdfQ."

    assert _decode_jwt_claims(token) == {"groups": ["godmode"]}


def test_decode_jwt_claims_ignores_opaque_tokens() -> None:
    assert _decode_jwt_claims("opaque-access-token") == {}
