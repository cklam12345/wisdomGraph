"""Tests for wisdom/validate.py"""
import pytest
from wisdom.validate import validate_node, validate_edge, validate_extraction


# ── Node validation ───────────────────────────────────────────────────────────

def test_valid_node():
    validate_node({"id": "abc123", "label": "MyClass", "tier": "knowledge"})


def test_node_missing_id():
    with pytest.raises(ValueError, match="id"):
        validate_node({"label": "MyClass"})


def test_node_empty_id():
    with pytest.raises(ValueError, match="id"):
        validate_node({"id": "", "label": "MyClass"})


def test_node_missing_label():
    with pytest.raises(ValueError, match="label"):
        validate_node({"id": "abc"})


def test_node_invalid_tier():
    with pytest.raises(ValueError, match="tier"):
        validate_node({"id": "abc", "label": "X", "tier": "garbage"})


def test_node_all_valid_tiers():
    for tier in ("knowledge", "experience", "insight", "wisdom"):
        validate_node({"id": "x", "label": "X", "tier": tier})


# ── Edge validation ───────────────────────────────────────────────────────────

def test_valid_edge():
    validate_edge({"source": "a", "target": "b", "confidence_tag": "EXTRACTED"})


def test_edge_missing_source():
    with pytest.raises(ValueError, match="source"):
        validate_edge({"target": "b"})


def test_edge_missing_target():
    with pytest.raises(ValueError, match="target"):
        validate_edge({"source": "a"})


def test_edge_invalid_confidence_tag():
    with pytest.raises(ValueError, match="confidence_tag"):
        validate_edge({"source": "a", "target": "b", "confidence_tag": "WRONG"})


def test_edge_defaults_extracted():
    # Should not raise — confidence_tag defaults to EXTRACTED
    validate_edge({"source": "a", "target": "b"})


# ── Full extraction validation ────────────────────────────────────────────────

def test_valid_extraction():
    validate_extraction({
        "nodes": [{"id": "n1", "label": "Foo", "tier": "knowledge"}],
        "edges": [{"source": "n1", "target": "n1"}],
    })


def test_extraction_missing_nodes():
    with pytest.raises(ValueError, match="nodes"):
        validate_extraction({"edges": []})


def test_extraction_missing_edges():
    with pytest.raises(ValueError, match="edges"):
        validate_extraction({"nodes": []})


def test_extraction_invalid_node_propagates():
    with pytest.raises(ValueError, match="id"):
        validate_extraction({"nodes": [{"label": "X"}], "edges": []})
