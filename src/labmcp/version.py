from importlib.metadata import PackageNotFoundError, version


def get_version() -> str:
    """Return the installed package version, or ``unknown`` from an editable checkout."""
    try:
        return version("labmcp")
    except PackageNotFoundError:
        return "unknown"
