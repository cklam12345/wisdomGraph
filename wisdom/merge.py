"""Neo4j MERGE operations — write DIKW nodes and edges idempotently."""
from __future__ import annotations

from datetime import datetime, timezone

from .validate import validate_extraction


_TIER_TO_LABEL = {
    "knowledge": "Knowledge",
    "experience": "Experience",
    "insight": "Insight",
    "wisdom": "Wisdom",
}

# Relationship type map: extraction relation → Neo4j relationship label
_RELATION_MAP = {
    "calls": "CALLS",
    "imports": "IMPORTS",
    "uses": "USES",
    "defines": "DEFINES",
    "implements": "IMPLEMENTS",
    "extends": "EXTENDS",
    "references": "REFERENCES",
    "depends_on": "DEPENDS_ON",
    "semantically_similar_to": "SEMANTICALLY_SIMILAR_TO",
    "conceptually_related_to": "SEMANTICALLY_SIMILAR_TO",
    "contradicts": "CONTRADICTS",
    "grounds": "GROUNDS",
    "reveals": "REVEALS",
    "crystallizes_into": "CRYSTALLIZES_INTO",
    "reinforces": "REINFORCES",
    "rationale_for": "RATIONALE_FOR",
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def merge_nodes(session, nodes: list[dict]) -> int:
    """MERGE nodes into Neo4j. Returns count of nodes written."""
    written = 0
    for node in nodes:
        tier = node.get("tier", "knowledge").lower()
        label = _TIER_TO_LABEL.get(tier, "Knowledge")

        # Build property dict — exclude None values
        props = {k: v for k, v in {
            "label": node.get("label", ""),
            "content": node.get("content", ""),
            "source_file": node.get("source_file", ""),
            "source_loc": node.get("source_loc", ""),
            "confidence": float(node.get("confidence", 1.0)),
            "confidence_tag": node.get("confidence_tag", "EXTRACTED"),
            "project": node.get("project", ""),
            "tier": tier,
            "context": node.get("context", ""),
            "outcome": node.get("outcome", ""),
            "pattern_strength": float(node.get("pattern_strength", 0.0)),
            "source_count": int(node.get("source_count", 1)),
            "principle": node.get("principle", ""),
            "reinforcement_count": int(node.get("reinforcement_count", 0)),
        }.items() if v is not None and v != ""}

        session.run(
            f"""
            MERGE (n:{label} {{id: $id}})
            ON CREATE SET n += $props, n.timestamp = $ts, n.access_count = 0
            ON MATCH SET
                n.confidence = CASE WHEN $conf > n.confidence THEN $conf ELSE n.confidence END,
                n.source_file = CASE WHEN $conf > n.confidence THEN $src ELSE n.source_file END,
                n.access_count = coalesce(n.access_count, 0)
            """,
            id=node["id"],
            props=props,
            ts=_utcnow(),
            conf=float(node.get("confidence", 1.0)),
            src=node.get("source_file", ""),
        )
        written += 1
    return written


def merge_edges(session, edges: list[dict]) -> int:
    """MERGE edges into Neo4j. Returns count written."""
    written = 0
    for edge in edges:
        rel = _RELATION_MAP.get(edge.get("relation", "").lower(), "RELATED_TO")
        conf = float(edge.get("confidence", 1.0))
        session.run(
            f"""
            MATCH (a {{id: $src}}), (b {{id: $tgt}})
            MERGE (a)-[r:{rel}]->(b)
            ON CREATE SET r.confidence = $conf, r.confidence_tag = $tag, r.weight = 1.0
            ON MATCH SET r.weight = coalesce(r.weight, 1.0) + 0.1
            """,
            src=edge["source"],
            tgt=edge["target"],
            conf=conf,
            tag=edge.get("confidence_tag", "EXTRACTED"),
        )
        written += 1
    return written


def merge_source(session, uri: str, author: str = "", contributor: str = "") -> str:
    """MERGE a Source node and return its uri."""
    import hashlib
    content_hash = hashlib.sha256(uri.encode()).hexdigest()[:16]
    session.run(
        """
        MERGE (s:Source {uri: $uri})
        ON CREATE SET s.author = $author, s.contributor = $contrib,
                      s.ingested_at = $ts, s.content_hash = $hash
        """,
        uri=uri,
        author=author,
        contrib=contributor,
        ts=_utcnow(),
        hash=content_hash,
    )
    return uri


def link_nodes_to_source(session, node_ids: list[str], source_uri: str) -> None:
    """Create SOURCED_FROM edges from nodes to a Source node."""
    for nid in node_ids:
        session.run(
            """
            MATCH (n {id: $nid}), (s:Source {uri: $uri})
            MERGE (n)-[:SOURCED_FROM]->(s)
            """,
            nid=nid,
            uri=source_uri,
        )


def merge_extraction(session, extraction: dict, source_uri: str = "", project: str = "") -> dict:
    """Full MERGE pipeline for one extraction dict. Returns stats."""
    validate_extraction(extraction)

    nodes = extraction.get("nodes", [])
    edges = extraction.get("edges", [])

    # Enrich with project + tier defaults
    for n in nodes:
        n.setdefault("project", project)
        n.setdefault("tier", "knowledge")

    node_count = merge_nodes(session, nodes)
    edge_count = merge_edges(session, edges)

    if source_uri:
        merge_source(session, source_uri)
        link_nodes_to_source(session, [n["id"] for n in nodes], source_uri)

    return {"nodes": node_count, "edges": edge_count}
