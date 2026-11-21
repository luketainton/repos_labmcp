from ipaddress import IPv4Address
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from labmcp import healthcheck
from labmcp.config import Settings


def test_stdio_healthcheck_requires_a_running_labmcp_process(monkeypatch, tmp_path) -> None:
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "1").mkdir()
    (proc / "1" / "cmdline").write_bytes(b"docker-init\0")
    (proc / "2").mkdir()  # A process can exit before its command line is read.
    monkeypatch.setattr(healthcheck, "Path", lambda path: proc if path == "/proc" else Path(path))
    monkeypatch.setattr(healthcheck, "get_settings", lambda: Settings(mcp_transport="stdio"))

    assert healthcheck.main() == 1

    entrypoint = Path(healthcheck.sys.executable).with_name("labmcp")
    (proc / "3").mkdir()
    (proc / "3" / "cmdline").write_bytes(b"python\0" + os.fsencode(entrypoint) + b"\0")

    assert healthcheck.main() == 0


@pytest.mark.parametrize(
    ("bind_host", "probe_host", "status", "exit_code"),
    [
        (str(IPv4Address(0)), "127.0.0.1", 200, 0),
        ("::", "::1", 200, 0),
        ("127.0.0.1", "127.0.0.1", 503, 1),
        ("labmcp.local", "labmcp.local", 200, 0),
    ],
)
def test_network_healthcheck_uses_the_configured_listener(
    monkeypatch, bind_host: str, probe_host: str, status: int, exit_code: int
) -> None:
    settings = Settings(mcp_transport="http", mcp_host=bind_host, mcp_port=8765)
    connect = Mock()
    connection = connect.return_value
    connection.getresponse.return_value.status = status
    monkeypatch.setattr(healthcheck, "get_settings", lambda: settings)
    monkeypatch.setattr(healthcheck, "HTTPConnection", connect)

    assert healthcheck.main() == exit_code
    connect.assert_called_once_with(probe_host, 8765, timeout=2)
    connection.request.assert_called_once_with("GET", "/healthz")
    connection.close.assert_called_once_with()


def test_network_healthcheck_fails_when_the_listener_is_down(monkeypatch) -> None:
    connection = Mock()
    connection.request.side_effect = ConnectionRefusedError
    monkeypatch.setattr(healthcheck, "get_settings", lambda: Settings(mcp_transport="http"))
    monkeypatch.setattr(healthcheck, "HTTPConnection", Mock(return_value=connection))

    assert healthcheck.main() == 1
    connection.close.assert_called_once_with()
