import pytest

from labmcp.action1_api import Action1OperationProvider
from labmcp.gitea_api import GiteaOperation, _make_operation_tool as make_gitea_tool
from labmcp.meraki_api import MerakiOperation, _make_operation_tool as make_meraki_tool
from labmcp.n8n_api import N8NOperation, _make_operation_tool as make_n8n_tool
from labmcp.pangolin_api import PangolinOperation, _make_operation_tool as make_pangolin_tool
from labmcp.pocket_id_api import PocketIDOperation, _make_operation_tool as make_pocket_id_tool
from labmcp.shlink_api import ShlinkOperation, _make_operation_tool as make_shlink_tool
from labmcp.tool_annotations import api_operation_annotations


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("GET", {"read_only_hint": True, "open_world_hint": True}),
        ("POST", {"read_only_hint": False, "open_world_hint": True}),
        ("PATCH", {"read_only_hint": False, "open_world_hint": True}),
        (
            "PUT",
            {"read_only_hint": False, "idempotent_hint": True, "open_world_hint": True},
        ),
        (
            "DELETE",
            {
                "read_only_hint": False,
                "destructive_hint": True,
                "idempotent_hint": True,
                "open_world_hint": True,
            },
        ),
    ],
)
def test_api_operation_annotations_describe_http_semantics(method, expected) -> None:
    annotations = api_operation_annotations(method)

    assert annotations.model_dump(exclude_none=True) == expected


@pytest.mark.asyncio
async def test_all_operation_providers_attach_http_annotations() -> None:
    async def request(*_args, **_kwargs):
        return {"ok": True}

    def client_factory():
        return type("Client", (), {"request": request})()

    gitea = make_gitea_tool("get", GiteaOperation("GET", "/users", "json"), client_factory, None)
    n8n = make_n8n_tool(
        "get",
        N8NOperation("GET", "/users", "json"),
        {"get": N8NOperation("GET", "/users", "json")},
        client_factory,
        None,
    )
    meraki = make_meraki_tool(
        "getOrganizations",
        MerakiOperation("GET", "/api/v1/organizations", "json"),
        {"getOrganizations": MerakiOperation("GET", "/api/v1/organizations", "json")},
        client_factory,
        None,
    )
    pocket_id = make_pocket_id_tool("get", PocketIDOperation("GET", "/users"), client_factory, None)
    pangolin = make_pangolin_tool(
        "get:/users",
        PangolinOperation("GET", "/v1/users", "json"),
        {"get:/users": PangolinOperation("GET", "/v1/users", "json")},
        client_factory,
        None,
    )
    shlink = make_shlink_tool("get", ShlinkOperation("GET", "/users"), client_factory, "3", None)
    action1 = Action1OperationProvider(client_factory)

    assert all(
        tool.annotations.read_only_hint is True and tool.annotations.open_world_hint is True
        for tool in (gitea, n8n, meraki, pocket_id, pangolin, shlink)
    )
    assert all(tool.annotations.open_world_hint is True for tool in await action1.list_tools())
