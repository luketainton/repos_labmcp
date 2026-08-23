import logging
from types import SimpleNamespace

import pytest
from fastmcp.server.middleware import MiddlewareContext

from labmcp.tool_logging import ToolCallLoggingMiddleware, logger


def test_tool_call_logger_uses_fastmcp_logging_hierarchy():
    assert logger.name == "fastmcp.labmcp.tool_logging"


@pytest.mark.asyncio
async def test_tool_call_log_contains_user_tool_parameters_and_output(monkeypatch, caplog):
    token = SimpleNamespace(
        claims={"preferred_username": 'alice"example'}, client_id="client-id"
    )
    monkeypatch.setattr("labmcp.tool_logging.get_access_token", lambda: token)
    context = MiddlewareContext(
        message=SimpleNamespace(name="gitea_list_repositories", arguments={"page": 2}),
        method="tools/call",
    )

    async def call_next(_context):
        return {"repositories": ["notes"]}

    with caplog.at_level(logging.INFO, logger=logger.name):
        result = await ToolCallLoggingMiddleware().on_call_tool(context, call_next)

    assert result == {"repositories": ["notes"]}
    assert (
        caplog.messages[-1]
        == 'user="alice\\"example" tool="gitea_list_repositories" '
        'params="{\\"page\\":2}" output="{\\"repositories\\":[\\"notes\\"]}"'
    )


@pytest.mark.asyncio
async def test_tool_call_error_is_logged_as_output(monkeypatch, caplog):
    monkeypatch.setattr("labmcp.tool_logging.get_access_token", lambda: None)
    context = MiddlewareContext(
        message=SimpleNamespace(name="gitea_list_repositories", arguments=None),
        method="tools/call",
    )

    async def call_next(_context):
        raise ValueError("unavailable")

    with caplog.at_level(logging.INFO, logger=logger.name):
        with pytest.raises(ValueError, match="unavailable"):
            await ToolCallLoggingMiddleware().on_call_tool(context, call_next)

    assert (
        caplog.messages[-1]
        == 'user="anonymous" tool="gitea_list_repositories" params="{}" '
        'output="{\\"error\\":\\"unavailable\\"}"'
    )
