"""Schema validation for extraction dicts before Neo4j MERGE."""
from __future__ import annotations

VALID_TIERS = {"knowledge", "experience", "insight", "wisdom"}
VALID_CONFIDENCE_TAGS = {"EXTRACTED", "INFERRED", "AMBIGUOUS"}
VALID_RELATIONS = {
    "calls", "imports", "uses", "defines", "implements", "extends",
    "references", "depends_on", "semantically_similar_to",
    "conceptually_related_to", "contradicts", "grounds",
    "reveals", "crystallizes_into", "reinforces", "sourced_from",
    "rationale_for",
}


def validate_node(node: dict) -> None:
    """Raise ValueError if node dict is malformed."""
    if not isinstance(node.get("id"), str) or not node["id"]:
        raise ValueError(f"Node missing 'id': {node}")
    if not isinstance(node.get("label"), str) or not node["label"]:
        raise ValueError(f"Node missing 'label': {node}")
    tier = node.get("tier", "knowledge").lower()
    if tier not in VALID_TIERS:
        raise ValueError(f"Invalid tier '{tier}' in node {node['id']!r}")


def validate_edge(edge: dict) -> None:
    """Raise ValueError if edge dict is malformed."""
    if not isinstance(edge.get("source"), str) or not edge["source"]:
        raise ValueError(f"Edge missing 'source': {edge}")
    if not isinstance(edge.get("target"), str) or not edge["target"]:
        raise ValueError(f"Edge missing 'target': {edge}")
    conf = edge.get("confidence_tag", "EXTRACTED")
    if conf not in VALID_CONFIDENCE_TAGS:
        raise ValueError(f"Invalid confidence_tag '{conf}' in edge {edge}")


def validate_extraction(data: dict) -> None:
    """Validate full extraction dict. Raises ValueError on schema error."""
    if not isinstance(data.get("nodes"), list):
        raise ValueError("Extraction dict missing 'nodes' list")
    if not isinstance(data.get("edges"), list):
        raise ValueError("Extraction dict missing 'edges' list")
    for node in data["nodes"]:
        validate_node(node)
    for edge in data["edges"]:
        validate_edge(edge)
