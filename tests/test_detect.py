"""Tests for wisdom/detect.py"""
import pytest
from pathlib import Path
from wisdom.detect import classify_file, detect, FileType, _looks_like_paper


def test_classify_python():
    assert classify_file(Path("main.py")) == FileType.CODE


def test_classify_typescript():
    assert classify_file(Path("app.tsx")) == FileType.CODE


def test_classify_markdown():
    assert classify_file(Path("README.md")) == FileType.DOCUMENT


def test_classify_pdf():
    assert classify_file(Path("paper.pdf")) == FileType.PAPER


def test_classify_image():
    assert classify_file(Path("diagram.png")) == FileType.IMAGE


def test_classify_unknown():
    assert classify_file(Path("file.xyz")) is None


def test_classify_docx():
    assert classify_file(Path("report.docx")) == FileType.DOCUMENT


def test_detect_finds_files(tmp_path):
    (tmp_path / "main.py").write_text("def foo(): pass")
    (tmp_path / "README.md").write_text("# Hello")
    (tmp_path / "diagram.png").write_bytes(b"\x89PNG\r\n")

    result = detect(tmp_path)
    assert result["total_files"] == 3
    assert len(result["files"]["code"]) == 1
    assert len(result["files"]["document"]) == 1
    assert len(result["files"]["image"]) == 1


def test_detect_skips_hidden_files(tmp_path):
    (tmp_path / ".env").write_text("SECRET=abc")
    (tmp_path / "main.py").write_text("x = 1")
    result = detect(tmp_path)
    # .env starts with '.' so it is skipped silently (not in skipped_sensitive)
    assert result["total_files"] == 1


def test_detect_skips_sensitive_non_hidden(tmp_path):
    # A non-hidden file with a sensitive name should appear in skipped_sensitive
    (tmp_path / "credentials.json").write_text('{"key": "secret"}')
    (tmp_path / "main.py").write_text("x = 1")
    result = detect(tmp_path)
    assert result["total_files"] == 1
    assert any("credentials" in s for s in result["skipped_sensitive"])


def test_detect_skips_node_modules(tmp_path):
    nm = tmp_path / "node_modules"
    nm.mkdir()
    (nm / "lib.js").write_text("module.exports = {}")
    (tmp_path / "app.js").write_text("const x = 1")
    result = detect(tmp_path)
    assert result["total_files"] == 1


def test_detect_wisdomignore(tmp_path):
    ignore = tmp_path / ".wisdomignore"
    ignore.write_text("vendor/\n")
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "lib.py").write_text("pass")
    (tmp_path / "main.py").write_text("pass")
    result = detect(tmp_path)
    assert result["total_files"] == 1


def test_looks_like_paper_positive(tmp_path):
    paper = tmp_path / "paper.md"
    paper.write_text(
        "Abstract: We propose a new method.\n"
        "See [1] for details. arXiv:1706.03762\n"
        "From the literature, we know that [2]\n"
        "This is a preprint submitted to proceedings.\n"
    )
    assert _looks_like_paper(paper) is True


def test_looks_like_paper_negative(tmp_path):
    normal = tmp_path / "notes.md"
    normal.write_text("# My notes\nTodo list for today.")
    assert _looks_like_paper(normal) is False
