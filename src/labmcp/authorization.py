from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .config import Settings

AuthCheck = Callable[[Any], bool]


def require_service_access(service: str, settings: Settings) -> AuthCheck | None:
    """Create a per-service authorization check from the configured claim mapping.

    Without a mapping, every authenticated user may use every service. Once a mapping
    is configured, each service requires membership of at least one listed group.
    """
    if not settings.mcp_service_groups:
        return None
    allowed_groups = settings.mcp_service_groups.get(service, [])

    def check(context: Any) -> bool:
        token = context.token
        if token is None:
            return False
        user_groups = _claim_values(token.claims, settings.mcp_auth_group_claim)
        upstream_claims = token.claims.get("upstream_claims")
        if isinstance(upstream_claims, Mapping):
            user_groups.update(
                _claim_values(upstream_claims, settings.mcp_auth_group_claim)
            )
        return bool(user_groups.intersection(allowed_groups))

    return check


def _claim_values(claims: Mapping[str, Any], claim_name: str) -> set[str]:
    value = claims.get(claim_name)
    if isinstance(value, str):
        return {value}
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return {item for item in value if isinstance(item, str)}
    return set()
