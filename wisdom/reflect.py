"""DIKW promotion engine — elevate Knowledge → Experience → Insight → Wisdom.

This module is designed to be called by Claude as a subagent during /wisdom reflect.
Each function returns a list of promotion dicts that merge.py can write.

Promotion pipeline:
1. find_experience_candidates()  — Knowledge appearing in 2+ projects
2. find_insight_candidates()      — Experiences clustering around the same pattern
3. find_wisdom_candidates()       — Insights with pattern_strength > 0.7
4. write_promotions()             — Execute the MERGE writes
"""
from __future__ import annotations

import math
from datetime import datetime, timezone


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Step 1: Knowledge → Experience ──────────────────────────────────────────

def find_experience_candidates(session, project: str | None = None) -> list[dict]:
    """Find Knowledge nodes that appear in 2+ projects — promote to Experience."""
    query = """
    MATCH (k:Knowledge)
    WITH k.label AS lbl, collect(DISTINCT k.project) AS projects, collect(k.id) AS ids
    WHERE size(projects) >= 2
    RETURN lbl, projects, ids
    """
    results = []
    for record in session.run(query):
        results.append({
            "label": record["lbl"],
            "projects": record["projects"],
            "ids": record["ids"],
        })
    return results


def promote_to_experience(session, candidates: list[dict]) -> int:
    """Write Experience nodes for each candidate. Returns promotion count."""
    promoted = 0
    for c in candidates:
        exp_id = f"exp:{c['label'].lower().replace(' ', '_')}"
        context = f"Observed across {len(c['projects'])} projects: {', '.join(c['projects'])}"
        session.run(
            """
            MERGE (e:Experience {id: $id})
            ON CREATE SET
                e.label = $label,
                e.content = $context,
                e.context = $context,
                e.source_count = $count,
                e.timestamp = $ts,
                e.tier = 'experience'
            ON MATCH SET
                e.source_count = $count,
                e.context = $context
            """,
            id=exp_id,
            label=c["label"],
            context=context,
            count=len(c["projects"]),
            ts=_utcnow(),
        )
        # Link original Knowledge nodes to this Experience
        for kid in c["ids"]:
            session.run(
                """
                MATCH (k:Knowledge {id: $kid}), (e:Experience {id: $eid})
                MERGE (k)-[:GROUNDS]->(e)
                """,
                kid=kid,
                eid=exp_id,
            )
        promoted += 1
    return promoted


# ── Step 2: Experience → Insight ─────────────────────────────────────────────

def find_insight_candidates(session) -> list[dict]:
    """Find Experience clusters with 3+ members connected by GROUNDS or similarity."""
    query = """
    MATCH (e:Experience)
    OPTIONAL MATCH (e)-[:GROUNDS|SEMANTICALLY_SIMILAR_TO]-(peer:Experience)
    WITH e, count(DISTINCT peer) AS peer_count
    WHERE peer_count >= 2
    RETURN e.id AS id, e.label AS label, peer_count,
           e.source_count AS source_count
    ORDER BY peer_count DESC
    """
    results = []
    for record in session.run(query):
        results.append({
            "id": record["id"],
            "label": record["label"],
            "peer_count": record["peer_count"],
            "source_count": record["source_count"] or 1,
        })
    return results


def promote_to_insight(session, candidates: list[dict]) -> int:
    """Write Insight nodes. Returns promotion count."""
    promoted = 0
    for c in candidates:
        ins_id = f"ins:{c['label'].lower().replace(' ', '_')}"
        source_count = c["source_count"]
        pattern_strength = min(
            math.log10(max(source_count, 1) + 1) * min(c["peer_count"] / 5.0, 1.0),
            1.0,
        )
        session.run(
            """
            MERGE (i:Insight {id: $id})
            ON CREATE SET
                i.label = $label,
                i.content = $content,
                i.pattern_strength = $strength,
                i.source_count = $count,
                i.timestamp = $ts,
                i.tier = 'insight'
            ON MATCH SET
                i.pattern_strength = CASE WHEN $strength > i.pattern_strength
                    THEN $strength ELSE i.pattern_strength END,
                i.source_count = $count
            """,
            id=ins_id,
            label=c["label"],
            content=f"Pattern detected across {source_count} sources with {c['peer_count']} related experiences.",
            strength=pattern_strength,
            count=source_count,
            ts=_utcnow(),
        )
        session.run(
            """
            MATCH (e:Experience {id: $eid}), (i:Insight {id: $iid})
            MERGE (e)-[:REVEALS]->(i)
            """,
            eid=c["id"],
            iid=ins_id,
        )
        promoted += 1
    return promoted


# ── Step 3: Insight → Wisdom ──────────────────────────────────────────────────

def find_wisdom_candidates(session) -> list[dict]:
    """Find Insights strong enough to crystallize into Wisdom."""
    query = """
    MATCH (i:Insight)
    WHERE i.pattern_strength >= 0.5 AND i.source_count >= 3
    AND NOT (i)-[:CRYSTALLIZES_INTO]->(:Wisdom)
    RETURN i.id AS id, i.label AS label,
           i.pattern_strength AS strength,
           i.source_count AS count,
           i.content AS content
    ORDER BY i.pattern_strength DESC
    LIMIT 20
    """
    results = []
    for record in session.run(query):
        results.append({
            "id": record["id"],
            "label": record["label"],
            "strength": record["strength"],
            "count": record["count"],
            "content": record["content"],
        })
    return results


def write_wisdom(session, wisdom_nodes: list[dict]) -> int:
    """Write Wisdom nodes from LLM-generated principles. Returns count written."""
    written = 0
    for w in wisdom_nodes:
        session.run(
            """
            MERGE (wis:Wisdom {id: $id})
            ON CREATE SET
                wis.label = $label,
                wis.principle = $principle,
                wis.confidence = $confidence,
                wis.reinforcement_count = 0,
                wis.timestamp = $ts,
                wis.tier = 'wisdom'
            ON MATCH SET
                wis.principle = $principle,
                wis.confidence = CASE WHEN $confidence > wis.confidence
                    THEN $confidence ELSE wis.confidence END
            """,
            id=w["id"],
            label=w["label"],
            principle=w["principle"],
            confidence=float(w.get("confidence", 0.7)),
            ts=_utcnow(),
        )
        if w.get("insight_id"):
            session.run(
                """
                MATCH (i:Insight {id: $iid}), (wis:Wisdom {id: $wid})
                MERGE (i)-[:CRYSTALLIZES_INTO]->(wis)
                """,
                iid=w["insight_id"],
                wid=w["id"],
            )
        written += 1
    return written


# ── Step 4: Feedback — Wisdom reinforces Knowledge ───────────────────────────

def write_reinforcement_edges(session) -> int:
    """Write REINFORCES edges from Wisdom back to grounding Knowledge nodes."""
    query = """
    MATCH (wis:Wisdom)-[:CRYSTALLIZES_INTO*0..1]-(i:Insight)
            -[:REVEALS*0..1]-(e:Experience)
            -[:GROUNDS*0..1]-(k:Knowledge)
    WHERE wis.reinforcement_count >= 2
    MERGE (wis)-[r:REINFORCES]->(k)
    ON CREATE SET r.weight = 1.0
    ON MATCH SET r.weight = coalesce(r.weight, 1.0) + 0.1
    RETURN count(r) AS written
    """
    with session.begin_transaction() as tx:
        result = tx.run(query)
        record = result.single()
        return record["written"] if record else 0


# ── Public entry point ────────────────────────────────────────────────────────

def run_reflect(session, project: str | None = None) -> dict:
    """Run the full promotion pipeline. Returns stats dict."""
    stats: dict[str, int] = {}

    exp_candidates = find_experience_candidates(session, project)
    stats["experience_promoted"] = promote_to_experience(session, exp_candidates)

    ins_candidates = find_insight_candidates(session)
    stats["insight_promoted"] = promote_to_insight(session, ins_candidates)

    wis_candidates = find_wisdom_candidates(session)
    # Wisdom requires LLM generation of principles — return candidates for the skill to handle
    stats["wisdom_candidates"] = len(wis_candidates)
    stats["wisdom_candidates_data"] = wis_candidates

    stats["reinforcement_edges"] = write_reinforcement_edges(session)

    return stats
