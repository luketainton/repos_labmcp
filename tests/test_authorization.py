from types import SimpleNamespace

from labmcp.authorization import require_service_access
from labmcp.config import Settings


def _context(claims: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(token=SimpleNamespace(claims=claims))


def test_empty_mapping_does_not_add_a_group_restriction() -> None:
    settings = Settings()

    assert require_service_access("pocket_id", settings) is None


def test_unmapped_service_is_denied_when_group_mapping_is_enabled() -> None:
    settings = Settings(mcp_service_groups={"gitea": ["mcp-gitea"]})
    check = require_service_access("pocket_id", settings)

    assert check is not None
    assert check(_context({"groups": ["mcp-pocket-id"]})) is False


def test_service_group_access_requires_an_allowed_group() -> None:
    settings = Settings(mcp_service_groups={"gitea": ["mcp-gitea", "mcp-admin"]})
    check = require_service_access("gitea", settings)

    assert check is not None
    assert check(_context({"groups": ["mcp-gitea"]})) is True
    assert check(_context({"groups": ["mcp-pocket-id"]})) is False
    assert check(SimpleNamespace(token=None)) is False


def test_service_group_access_supports_a_custom_role_claim() -> None:
    settings = Settings(
        mcp_auth_group_claim="roles",
        mcp_service_groups={"pocket_id": ["administrator"]},
    )
    check = require_service_access("pocket_id", settings)

    assert check is not None
    assert check(_context({"roles": "administrator"})) is True


def test_service_group_access_reads_fastmcp_upstream_claims() -> None:
    settings = Settings(mcp_service_groups={"gitea": ["godmode"]})
    check = require_service_access("gitea", settings)

    assert check is not None
    assert check(_context({"upstream_claims": {"groups": ["godmode"]}})) is True
