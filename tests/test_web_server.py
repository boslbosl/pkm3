"""Regression tests for static-asset path resolution (the /static/* 404 bug)."""

from aivault.web.server import STATIC_DIR, resolve_static


def test_root_serves_index():
    assert resolve_static("/") == (STATIC_DIR / "index.html")


def test_static_prefix_is_not_doubled():
    # index.html links assets as /static/app.js; must map to STATIC_DIR/app.js
    target = resolve_static("/static/app.js")
    assert target == (STATIC_DIR / "app.js")
    assert target is not None and target.is_file()


def test_bare_asset_path_also_works():
    assert resolve_static("/style.css") == (STATIC_DIR / "style.css")


def test_path_traversal_rejected():
    assert resolve_static("/static/../../config.py") is None


def test_missing_file_returns_none():
    assert resolve_static("/static/nope.js") is None
