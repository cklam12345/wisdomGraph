"""Tests for wisdom/security.py"""
import pytest
from pathlib import Path
from wisdom.security import validate_url, sanitize_label, is_sensitive_path, validate_graph_path


def test_validate_url_http():
    assert validate_url("http://example.com/page") == "http://example.com/page"


def test_validate_url_https():
    assert validate_url("  https://arxiv.org/abs/1706.03762  ") == "https://arxiv.org/abs/1706.03762"


def test_validate_url_rejects_file():
    with pytest.raises(ValueError, match="file"):
        validate_url("file:///etc/passwd")


def test_validate_url_rejects_ftp():
    with pytest.raises(ValueError, match="ftp"):
        validate_url("ftp://example.com")


def test_validate_url_rejects_no_host():
    with pytest.raises(ValueError):
        validate_url("https://")


def test_sanitize_label_strips_control():
    assert "\x00" not in sanitize_label("hello\x00world")
    assert "\x1f" not in sanitize_label("foo\x1fbar")


def test_sanitize_label_caps_length():
    long = "a" * 500
    assert len(sanitize_label(long)) <= 256


def test_sanitize_label_html_escapes():
    result = sanitize_label('<script>alert("xss")</script>')
    assert "<script>" not in result
    assert "&lt;" in result


def test_is_sensitive_path_env():
    assert is_sensitive_path(Path(".env")) is True
    assert is_sensitive_path(Path(".envrc")) is True


def test_is_sensitive_path_key():
    assert is_sensitive_path(Path("id_rsa")) is True
    assert is_sensitive_path(Path("server.pem")) is True


def test_is_sensitive_path_normal():
    assert is_sensitive_path(Path("main.py")) is False
    assert is_sensitive_path(Path("README.md")) is False


def test_validate_graph_path_inside(tmp_path):
    out_dir = tmp_path / "wisdom-out"
    out_dir.mkdir()
    target = out_dir / "graph.json"
    target.touch()
    result = validate_graph_path(str(target), out_dir)
    assert result == target.resolve()


def test_validate_graph_path_traversal(tmp_path):
    out_dir = tmp_path / "wisdom-out"
    out_dir.mkdir()
    with pytest.raises(ValueError, match="escapes"):
        validate_graph_path(str(tmp_path / "etc" / "passwd"), out_dir)
