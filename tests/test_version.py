from importlib.metadata import PackageNotFoundError

from labmcp import version


def test_get_version_returns_package_metadata(monkeypatch) -> None:
    monkeypatch.setattr(version, "version", lambda _name: "1.2.3")

    assert version.get_version() == "1.2.3"


def test_get_version_returns_unknown_when_package_is_not_installed(monkeypatch) -> None:
    def missing(_name: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr(version, "version", missing)

    assert version.get_version() == "unknown"
