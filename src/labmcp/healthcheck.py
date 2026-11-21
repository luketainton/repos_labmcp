"""Container liveness probe for LabMCP's network and stdio transports."""

from http.client import HTTPConnection, HTTPException
from ipaddress import ip_address
import os
from pathlib import Path
import sys

from .auth import NETWORK_TRANSPORTS
from .config import get_settings


def _probe_host(host: str) -> str:
    try:
        address = ip_address(host)
    except ValueError:
        return host
    if address.is_unspecified:
        return "127.0.0.1" if address.version == 4 else "::1"
    return host


def _stdio_process_is_running() -> bool:
    entrypoint = os.fsencode(Path(sys.executable).with_name("labmcp"))
    # The console script follows its Python interpreter in Linux's process arguments.
    # Finding it also works when Docker runs a separate init process as PID 1.
    for cmdline in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            argv = cmdline.read_bytes().split(b"\0", maxsplit=2)
        except OSError:
            continue
        if argv[1:2] == [entrypoint]:
            return True
    return False


def main() -> int:
    settings = get_settings()
    if settings.mcp_transport not in NETWORK_TRANSPORTS:
        return 0 if _stdio_process_is_running() else 1

    connection = HTTPConnection(_probe_host(settings.mcp_host), settings.mcp_port, timeout=2)
    try:
        connection.request("GET", "/healthz")
        return 0 if connection.getresponse().status == 200 else 1
    except OSError, HTTPException:
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
