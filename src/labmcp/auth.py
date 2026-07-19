from collections.abc import Sequence
from typing import Any

from .config import Settings

NETWORK_TRANSPORTS = {"http", "sse", "streamable-http"}


def create_auth_provider(settings: Settings) -> Any | None:
    """Create a FastMCP auth provider from runtime settings."""
    if settings.mcp_auth_mode == "none":
        return None
    if settings.mcp_auth_mode == "jwt":
        return _create_jwt_auth_provider(settings)
    if settings.mcp_auth_mode == "oidc_proxy":
        return _create_oidc_proxy_auth_provider(settings)
    raise ValueError(f"Unsupported MCP_AUTH_MODE: {settings.mcp_auth_mode}")


def ensure_network_transport_is_authenticated(settings: Settings) -> None:
    """Prevent accidental unauthenticated HTTP/SSE exposure."""
    if settings.mcp_transport in NETWORK_TRANSPORTS and settings.mcp_auth_mode == "none":
        raise RuntimeError(
            "MCP_AUTH_MODE=jwt or oidc_proxy is required when MCP_TRANSPORT is http, "
            "sse, or streamable-http."
        )


def _create_jwt_auth_provider(settings: Settings) -> Any:
    issuer = _strip_trailing_slash(settings.mcp_auth_jwt_issuer or settings.pocket_id_url)
    if not issuer:
        raise RuntimeError("Set MCP_AUTH_JWT_ISSUER or POCKET_ID_URL when MCP_AUTH_MODE=jwt.")
    if not settings.mcp_auth_jwt_audience:
        raise RuntimeError("Set MCP_AUTH_JWT_AUDIENCE to the Pocket ID OIDC client ID.")

    jwks_uri = settings.mcp_auth_jwt_jwks_uri or f"{issuer}/.well-known/jwks.json"

    from fastmcp.server.auth.providers.jwt import JWTVerifier

    return JWTVerifier(
        jwks_uri=jwks_uri,
        issuer=issuer,
        audience=settings.mcp_auth_jwt_audience,
        required_scopes=_required_scopes(settings),
    )


def _create_oidc_proxy_auth_provider(settings: Settings) -> Any:
    base_url = _strip_trailing_slash(settings.mcp_auth_base_url)
    if not base_url:
        raise RuntimeError("Set MCP_AUTH_BASE_URL to the public HTTPS URL of this MCP server.")

    config_url = settings.mcp_auth_oidc_config_url or _default_oidc_config_url(settings)
    if not config_url:
        raise RuntimeError(
            "Set MCP_AUTH_OIDC_CONFIG_URL or POCKET_ID_URL when MCP_AUTH_MODE=oidc_proxy."
        )
    if not settings.mcp_auth_oidc_client_id:
        raise RuntimeError("Set MCP_AUTH_OIDC_CLIENT_ID to the Pocket ID OIDC client ID.")
    if not settings.mcp_auth_oidc_client_secret:
        raise RuntimeError("Set MCP_AUTH_OIDC_CLIENT_SECRET to the Pocket ID OIDC client secret.")

    from fastmcp.server.auth.oidc_proxy import OIDCProxy

    kwargs: dict[str, Any] = {
        "config_url": config_url,
        "client_id": settings.mcp_auth_oidc_client_id,
        "client_secret": settings.mcp_auth_oidc_client_secret.get_secret_value(),
        "base_url": base_url,
        "redirect_path": settings.mcp_auth_oidc_redirect_path,
        "required_scopes": _required_scopes(settings),
    }
    if settings.mcp_auth_jwt_audience:
        kwargs["audience"] = settings.mcp_auth_jwt_audience
    if settings.mcp_auth_oidc_jwt_signing_key:
        kwargs["jwt_signing_key"] = settings.mcp_auth_oidc_jwt_signing_key.get_secret_value()

    return OIDCProxy(**kwargs)


def _default_oidc_config_url(settings: Settings) -> str | None:
    issuer = _strip_trailing_slash(settings.pocket_id_url)
    if not issuer:
        return None
    return f"{issuer}/.well-known/openid-configuration"


def _strip_trailing_slash(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip().rstrip("/")
    return stripped or None


def _parse_scopes(value: str | None) -> Sequence[str] | None:
    if value is None:
        return None
    scopes = [scope.strip() for scope in value.split(",") if scope.strip()]
    return scopes or None


def _required_scopes(settings: Settings) -> Sequence[str] | None:
    return _parse_scopes(settings.mcp_auth_required_scopes or settings.mcp_auth_jwt_required_scopes)
