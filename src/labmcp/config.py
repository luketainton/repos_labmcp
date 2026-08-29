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
    n8n_url: str | None = None
    n8n_api_key: SecretStr | None = None
    n8n_api_path: str = "/api/v1"
    meraki_url: str | None = "https://api.meraki.com"
    meraki_dashboard_api_key: SecretStr | None = None
    meraki_api_path: str = "/api/v1"
    meraki_openapi_url: str = "https://raw.githubusercontent.com/meraki/openapi/master/openapi/spec3.json"
    pangolin_url: str | None = None
    pangolin_api_key: SecretStr | None = None
    pangolin_api_path: str = "/v1"
    shlink_url: str | None = None
    shlink_api_key: SecretStr | None = None
    shlink_api_version: str = "3"
    pushover_api_url: str = "https://api.pushover.net"
    pushover_app_token: SecretStr | None = None
    pushover_user_key: SecretStr | None = None
    action1_url: str | None = "https://app.action1.com/api/3.0"
    action1_client_id: str | None = None
    action1_client_secret: SecretStr | None = None
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
    mcp_service_scopes: dict[str, list[str]] = Field(default_factory=dict)
    mcp_auth_oidc_config_url: str | None = None
    mcp_auth_oidc_client_id: str | None = None
    mcp_auth_oidc_client_secret: SecretStr | None = None
    mcp_auth_oidc_redirect_path: str = "/auth/callback"
    mcp_auth_oidc_extra_scopes: str = "offline_access"
    mcp_auth_oidc_jwt_signing_key: SecretStr | None = None
    mcp_auth_oidc_forward_resource: bool = False
    mcp_auth_oidc_enable_cimd: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
