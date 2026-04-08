"""Tests for wisdom/ingest.py — URL validation and HTML stripping (no network calls)."""
import pytest
from wisdom.ingest import _html_to_text, _utcnow


def test_html_to_text_strips_tags():
    html = "<p>Hello <b>world</b></p>"
    result = _html_to_text(html)
    assert "<p>" not in result
    assert "<b>" not in result
    assert "Hello" in result
    assert "world" in result


def test_html_to_text_strips_script():
    html = "<html><head><script>alert('xss')</script></head><body>Content</body></html>"
    result = _html_to_text(html)
    assert "alert" not in result
    assert "Content" in result


def test_html_to_text_strips_style():
    html = "<style>body { color: red }</style><p>Text</p>"
    result = _html_to_text(html)
    assert "color" not in result
    assert "Text" in result


def test_html_to_text_decodes_entities():
    html = "&amp; &lt;tag&gt; &nbsp; &#39;quote&#39;"
    result = _html_to_text(html)
    assert "&" in result
    assert "<tag>" in result
    assert "'" in result


def test_html_to_text_normalizes_whitespace():
    html = "   lots    of    spaces   "
    result = _html_to_text(html)
    assert "  " not in result


def test_utcnow_returns_iso_string():
    ts = _utcnow()
    assert "T" in ts
    assert ts.endswith("+00:00") or ts.endswith("Z") or "+" in ts
