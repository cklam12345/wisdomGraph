"""Cypher traversal engine — answer natural language questions by walking the DIKW graph."""
from __future__ import annotations

from datetime import datetime, timezone


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def full_text_search(session, query: str, limit: int = 10) -> list[dict]:
    """Full-text search across all DIKW tiers. Returns scored node list."""
    try:
        result = session.run(
            """
            CALL db.index.fulltext.queryNodes('wisdom_content', $query)
            YIELD node, score
            RETURN node.id AS id, node.label AS label, node.tier AS tier,
                   node.content AS content, node.principle AS principle,
                   node.confidence AS confidence, score
            ORDER BY score DESC
            LIMIT $limit
            """,
            query=query,
            limit=limit,
        )
        return [dict(r) for r in result]
    except Exception:
        # Fallback: keyword scan if full-text index not available
        return _keyword_fallback(session, query, limit)


def _keyword_fallback(session, query: str, limit: int) -> list[dict]:
    """Keyword scan fallback when full-text index unavailable."""
    terms = [t.lower() for t in query.split() if len(t) > 2]
    if not terms:
        return []
    # Build OR condition
    conditions = " OR ".join(f"toLower(n.label) CONTAINS '{t}' OR toLower(n.content) CONTAINS '{t}'" for t in terms[:5])
    cypher = f"""
    MATCH (n)
    WHERE (n:Knowledge OR n:Experience OR n:Insight OR n:Wisdom)
    AND ({conditions})
    RETURN n.id AS id, n.label AS label, n.tier AS tier,
           n.content AS content, n.principle AS principle,
           n.confidence AS confidence,
           1.0 AS score
    LIMIT {limit}
    """
    result = session.run(cypher)
    return [dict(r) for r in result]


def walk_dikw_path(session, node_id: str, depth: int = 3) -> list[dict]:
    """Walk up the DIKW hierarchy from a node. Returns the full provenance chain."""
    result = session.run(
        """
        MATCH path = (start {id: $id})-[:GROUNDS|REVEALS|CRYSTALLIZES_INTO*1..3]->(end)
        UNWIND nodes(path) AS n
        RETURN DISTINCT n.id AS id, n.label AS label, n.tier AS tier,
               n.content AS content, n.principle AS principle,
               n.confidence AS confidence,
               n.pattern_strength AS pattern_strength,
               n.reinforcement_count AS reinforcement_count
        ORDER BY
            CASE n.tier
                WHEN 'wisdom' THEN 4
                WHEN 'insight' THEN 3
                WHEN 'experience' THEN 2
                ELSE 1
            END DESC
        """,
        id=node_id,
    )
    return [dict(r) for r in result]


def get_provenance(session, node_id: str) -> list[dict]:
    """Get source files that contributed to a node."""
    result = session.run(
        """
        MATCH (n {id: $id})-[:SOURCED_FROM]->(s:Source)
        RETURN s.uri AS uri, s.author AS author, s.ingested_at AS ingested_at
        """,
        id=node_id,
    )
    return [dict(r) for r in result]


def increment_access(session, node_ids: list[str]) -> None:
    """Increment access_count on traversed nodes (feeds reinforcement)."""
    session.run(
        """
        MATCH (n) WHERE n.id IN $ids
        SET n.access_count = coalesce(n.access_count, 0) + 1,
            n.last_accessed = $ts
        """,
        ids=node_ids,
        ts=_utcnow(),
    )


def increment_wisdom_reinforcement(session, wisdom_ids: list[str]) -> None:
    """Increment reinforcement_count on Wisdom nodes that were returned."""
    session.run(
        """
        MATCH (w:Wisdom) WHERE w.id IN $ids
        SET w.reinforcement_count = coalesce(w.reinforcement_count, 0) + 1,
            w.last_reinforced = $ts
        """,
        ids=wisdom_ids,
        ts=_utcnow(),
    )


def shortest_path(session, label_a: str, label_b: str) -> list[dict]:
    """Find shortest path between two concepts by label."""
    result = session.run(
        """
        MATCH (a), (b)
        WHERE toLower(a.label) CONTAINS toLower($a)
          AND toLower(b.label) CONTAINS toLower($b)
        WITH a, b LIMIT 1
        MATCH path = shortestPath((a)-[*1..6]-(b))
        UNWIND nodes(path) AS n
        RETURN n.id AS id, n.label AS label, n.tier AS tier
        """,
        a=label_a,
        b=label_b,
    )
    return [dict(r) for r in result]


def explain_node(session, label: str) -> dict:
    """Return full DIKW context for a node identified by label."""
    # Find node
    result = session.run(
        """
        MATCH (n)
        WHERE (n:Knowledge OR n:Experience OR n:Insight OR n:Wisdom)
          AND toLower(n.label) CONTAINS toLower($label)
        RETURN n.id AS id, n.label AS label, n.tier AS tier,
               n.content AS content, n.principle AS principle,
               n.confidence AS confidence
        LIMIT 1
        """,
        label=label,
    )
    record = result.single()
    if not record:
        return {"error": f"No node found matching '{label}'"}

    node = dict(record)
    node_id = node["id"]

    # Walk up
    node["dikw_chain"] = walk_dikw_path(session, node_id)
    # Get sources
    node["sources"] = get_provenance(session, node_id)

    return node


def god_nodes(session, limit: int = 10) -> list[dict]:
    """Return highest-degree nodes across all tiers."""
    result = session.run(
        """
        MATCH (n)
        WHERE (n:Knowledge OR n:Experience OR n:Insight OR n:Wisdom)
        RETURN n.id AS id, n.label AS label, n.tier AS tier,
               n.confidence AS confidence,
               count{(n)--()}  AS degree
        ORDER BY degree DESC
        LIMIT $limit
        """,
        limit=limit,
    )
    return [dict(r) for r in result]


def answer_question(session, question: str, tier_filter: str | None = None) -> dict:
    """Top-level query: search, walk DIKW paths, score, return answer package."""
    candidates = full_text_search(session, question, limit=5)
    if not candidates:
        return {"answer": "No matching nodes found in the wisdom graph.", "nodes": []}

    # Filter by tier if requested
    if tier_filter:
        candidates = [c for c in candidates if c.get("tier") == tier_filter.lower()]
        if not candidates:
            return {"answer": f"No {tier_filter}-tier nodes matched this question.", "nodes": []}

    all_nodes: list[dict] = []
    wisdom_ids: list[str] = []
    all_ids: list[str] = []

    for candidate in candidates:
        chain = walk_dikw_path(session, candidate["id"])
        all_nodes.extend(chain if chain else [candidate])
        for n in (chain or [candidate]):
            all_ids.append(n["id"])
            if n.get("tier") == "wisdom":
                wisdom_ids.append(n["id"])

    # Deduplicate by id, prefer higher-tier
    seen: set[str] = set()
    deduped: list[dict] = []
    tier_rank = {"wisdom": 4, "insight": 3, "experience": 2, "knowledge": 1}
    for n in sorted(all_nodes, key=lambda x: tier_rank.get(x.get("tier", "knowledge"), 0), reverse=True):
        if n["id"] not in seen:
            seen.add(n["id"])
            deduped.append(n)

    # Track access
    increment_access(session, list(set(all_ids)))
    if wisdom_ids:
        increment_wisdom_reinforcement(session, list(set(wisdom_ids)))

    return {
        "question": question,
        "nodes": deduped[:20],
        "wisdom_nodes": [n for n in deduped if n.get("tier") == "wisdom"],
        "answer_tier": deduped[0].get("tier", "knowledge") if deduped else "none",
    }
