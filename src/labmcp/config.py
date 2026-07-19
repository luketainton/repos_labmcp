from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or a .env file."""

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    gitea_url: str | None = None
    gitea_token: SecretStr | None = None
    pocket_id_url: str | None = None
    pocket_id_token: SecretStr | None = None
    pocket_id_health_path: str = "/api/health"
    http_timeout: float = 20.0
    mcp_transport: str = "stdio"
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8000
    mcp_auth_mode: Literal["none", "jwt", "oidc_proxy"] = "none"
    mcp_auth_base_url: str | None = None
    mcp_auth_jwt_issuer: str | None = None
    mcp_auth_jwt_jwks_uri: str | None = None
    mcp_auth_jwt_audience: str | None = None
    mcp_auth_required_scopes: str | None = None
    mcp_auth_jwt_required_scopes: str | None = None
    mcp_auth_group_claim: str = "groups"
    mcp_service_groups: dict[str, list[str]] = Field(default_factory=dict)
    mcp_auth_oidc_config_url: str | None = None
    mcp_auth_oidc_client_id: str | None = None
    mcp_auth_oidc_client_secret: SecretStr | None = None
    mcp_auth_oidc_redirect_path: str = "/auth/callback"
    mcp_auth_oidc_jwt_signing_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
