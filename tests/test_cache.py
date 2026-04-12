"""Tests for wisdom/cache.py"""
import pytest
from pathlib import Path
from wisdom.cache import file_hash, load_cached, save_cached, check_cache, save_extractions


def test_file_hash_consistent(tmp_path):
    f = tmp_path / "test.py"
    f.write_text("hello world")
    h1 = file_hash(f)
    h2 = file_hash(f)
    assert h1 == h2


def test_file_hash_changes_on_content(tmp_path):
    f = tmp_path / "test.py"
    f.write_text("version 1")
    h1 = file_hash(f)
    f.write_text("version 2")
    h2 = file_hash(f)
    assert h1 != h2


def test_load_cached_miss(tmp_path):
    f = tmp_path / "test.py"
    f.write_text("hello")
    assert load_cached(f, root=tmp_path) is None


def test_save_and_load_cached(tmp_path):
    f = tmp_path / "test.py"
    f.write_text("def foo(): pass")
    data = {"nodes": [{"id": "foo", "label": "foo"}], "edges": []}
    save_cached(f, data, root=tmp_path)
    result = load_cached(f, root=tmp_path)
    assert result == data


def test_cache_invalidated_on_change(tmp_path):
    f = tmp_path / "test.py"
    f.write_text("original")
    data = {"nodes": [], "edges": []}
    save_cached(f, data, root=tmp_path)
    f.write_text("changed")
    assert load_cached(f, root=tmp_path) is None


def test_check_cache_splits(tmp_path):
    f1 = tmp_path / "cached.py"
    f1.write_text("x = 1")
    f2 = tmp_path / "uncached.py"
    f2.write_text("y = 2")

    data = {"nodes": [{"id": "x"}], "edges": [], "source_file": str(f1)}
    save_cached(f1, data, root=tmp_path)

    cached, uncached = check_cache([str(f1), str(f2)], root=tmp_path)
    assert len(cached) == 1
    assert str(f2) in uncached


def test_save_extractions(tmp_path):
    f = tmp_path / "src.py"
    f.write_text("code")
    ext = {"nodes": [{"id": "n1"}], "edges": [], "source_file": str(f)}
    count = save_extractions([ext], root=tmp_path)
    assert count == 1
    assert load_cached(f, root=tmp_path) is not None
