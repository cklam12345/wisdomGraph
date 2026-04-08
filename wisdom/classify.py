"""DIKW tier classification — assign epistemic role to extracted nodes.

Rules (applied in order, first match wins):
1. Wisdom   — node explicitly marked tier=wisdom by LLM extraction
2. Insight  — node explicitly marked tier=insight, OR matches insight heuristics
3. Experience — node explicitly marked tier=experience, OR matches experience heuristics
4. Knowledge — default for all first-time extractions

Promotion heuristics (applied when tier not explicitly set):
- Experience: same concept id appears in 2+ distinct projects in this batch
- Insight: node has 3+ SEMANTICALLY_SIMILAR_TO or CONTRADICTS edges in this batch
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_nodes(
    nodes: list[dict],
    edges: list[dict],
    project: str,
) -> list[dict]:
    """Assign DIKW tier to each node. Returns enriched node list.

    Args:
        nodes: Raw extracted nodes (from extract.py output)
        edges: Raw extracted edges
        project: Project slug / root path for provenance

    Returns:
        Nodes with 'tier', 'project', 'timestamp' fields set.
    """
    # Count cross-edge relationships per node
    similarity_count: Counter[str] = Counter()
    for edge in edges:
        rel = edge.get("relation", "")
        if rel in ("semantically_similar_to", "conceptually_related_to", "contradicts"):
            similarity_count[edge["source"]] += 1
            similarity_count[edge["target"]] += 1

    enriched = []
    for node in nodes:
        n = dict(node)
        n.setdefault("project", project)
        n.setdefault("timestamp", _utcnow())
        n.setdefault("access_count", 0)
        n.setdefault("confidence", 1.0 if n.get("confidence_tag") == "EXTRACTED" else 0.7)

        # Explicit tier from LLM extraction takes priority
        explicit_tier = n.get("tier", "").lower()
        if explicit_tier in ("wisdom", "insight", "experience", "knowledge"):
            n["tier"] = explicit_tier
        # Insight heuristic: 3+ semantic similarity edges
        elif similarity_count.get(n["id"], 0) >= 3:
            n["tier"] = "insight"
        # Default: Knowledge
        else:
            n["tier"] = "knowledge"

        enriched.append(n)

    return enriched


def promote_experiences(
    nodes: list[dict],
    existing_projects: list[str],
) -> list[dict]:
    """Promote Knowledge nodes to Experience when concept appears in 2+ projects.

    This is a batch operation run after merging a new corpus.
    existing_projects: project slugs already in the graph for this concept id.
    """
    promoted = []
    for node in nodes:
        n = dict(node)
        if n.get("tier") == "knowledge" and n["id"] in existing_projects:
            n["tier"] = "experience"
            n["context"] = f"Observed in multiple projects: {', '.join(existing_projects)}"
        promoted.append(n)
    return promoted


def build_dikw_edges(nodes: list[dict], edges: list[dict]) -> list[dict]:
    """Add implicit DIKW hierarchy edges (GROUNDS, REVEALS, CRYSTALLIZES_INTO).

    These edges represent the epistemic structure:
    - Knowledge GROUNDS Experience (when Experience promoted from Knowledge)
    - Experience REVEALS Insight
    - Insight CRYSTALLIZES_INTO Wisdom
    """
    tier_map = {n["id"]: n.get("tier", "knowledge") for n in nodes}
    hierarchy = {
        ("knowledge", "experience"): "GROUNDS",
        ("experience", "insight"): "REVEALS",
        ("insight", "wisdom"): "CRYSTALLIZES_INTO",
    }
    dikw_edges = []
    seen_pairs: set[tuple[str, str]] = set()

    for edge in edges:
        src_tier = tier_map.get(edge["source"], "knowledge")
        tgt_tier = tier_map.get(edge["target"], "knowledge")
        pair = (src_tier, tgt_tier)
        rel = hierarchy.get(pair)
        if rel and (edge["source"], edge["target"]) not in seen_pairs:
            dikw_edges.append({
                "source": edge["source"],
                "target": edge["target"],
                "relation": rel,
                "confidence_tag": "EXTRACTED",
                "confidence": 1.0,
            })
            seen_pairs.add((edge["source"], edge["target"]))

    return edges + dikw_edges
