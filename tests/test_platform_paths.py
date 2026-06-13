import pytest

from aivault import platform_paths as pp


def test_native_scope_includes_current_home():
    homes = pp.home_dirs("native")
    paths = [str(h.path) for h in homes]
    assert str(pp.Path.home()) in paths
    assert all(h.os_context in ("native", "windows", "wsl") for h in homes)


def test_invalid_scope_raises():
    with pytest.raises(ValueError):
        pp.home_dirs("martian")


def test_all_adapters_accept_os_scope():
    # guards against an adapter shipping the old no-arg discover() signature
    from aivault.adapters.base import _build_registry

    for adapter in _build_registry().values():
        assert isinstance(adapter.discover("native"), list)


def test_all_scope_is_superset_of_native():
    native = {str(h.path) for h in pp.home_dirs("native")}
    allh = {str(h.path) for h in pp.home_dirs("all")}
    assert native <= allh


def test_infer_os_context():
    assert pp.infer_os_context("/mnt/c/Users/me/.codex/sessions/x.jsonl") == "windows"
    assert pp.infer_os_context(r"C:\Users\me\.codex\x.jsonl") == "windows"
    assert pp.infer_os_context(r"\\wsl.localhost\Ubuntu\home\me\x.jsonl") == "wsl"
    # a plain relative/local path falls back to the current OS context
    assert pp.infer_os_context("./tests/fixtures/x.jsonl") == pp.current_os_context()
