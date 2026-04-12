"""DIKW promotion engine — elevate Knowledge → Experience → Insight → Wisdom.

This module is designed to be called by Claude as a subagent during /wisdom reflect.
Each function returns a list of promotion dicts that merge.py can write.

Promotion pipeline:
1. find_experience_candidates()     — Knowledge appearing in 2+ projects
2. find_failure_insight_candidates() — FAILED Experiences clustering → anti-pattern Insights
3. find_insight_candidates()         — all Experiences clustering around the same pattern
4. find_wisdom_candidates()          — Insights with pattern_strength > 0.5
5. write_prevents_edges()            — Wisdom that grounds FAILED Experiences → PREVENTS Knowledge
6. write_reinforcement_edges()       — Wisdom → Knowledge feedback loop

Failure knowledge is first-class:
- Experience.outcome: SUCCEEDED | FAILED | PARTIAL | UNKNOWN
- Experience.lesson:  what was learned (especially from failure)
- (:Wisdom)-[:PREVENTS]->(:Knowledge)  — "don't go here" edges
- Failure-grounded Wisdom gets confidence += 0.15 bonus (hard-won)
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

# ── Outcome taxonomy ──────────────────────────────────────────────────────────
OUTCOME_FAILED    = "FAILED"
OUTCOME_SUCCEEDED = "SUCCEEDED"
OUTCOME_PARTIAL   = "PARTIAL"
OUTCOME_UNKNOWN   = "UNKNOWN"

FAILURE_CONFIDENCE_BONUS = 0.15  # hard-won knowledge earns higher confidence


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
                e.outcome = $outcome,
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
            outcome=c.get("outcome", OUTCOME_UNKNOWN),
            ts=_utcnow(),
        )
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


# ── Step 2a: FAILED Experiences → anti-pattern Insights ─────────────────────

def find_failure_insight_candidates(session) -> list[dict]:
    """Find FAILED Experience clusters — these become anti-pattern Insights.

    Failure Insights get elevated pattern_strength because hard-won failure
    knowledge is more reliable than success pattern detection.
    """
    query = """
    MATCH (e:Experience)
    WHERE e.outcome = 'FAILED'
    OPTIONAL MATCH (e)-[:GROUNDS|SEMANTICALLY_SIMILAR_TO]-(peer:Experience)
    WHERE peer.outcome = 'FAILED'
    WITH e, count(DISTINCT peer) AS failure_cluster_size
    RETURN e.id AS id, e.label AS label,
           e.lesson AS lesson,
           e.context AS context,
           failure_cluster_size,
           e.source_count AS source_count
    ORDER BY failure_cluster_size DESC
    """
    results = []
    for record in session.run(query):
        results.append({
            "id": record["id"],
            "label": record["label"],
            "lesson": record["lesson"] or "",
            "context": record["context"] or "",
            "failure_cluster_size": record["failure_cluster_size"] or 0,
            "source_count": record["source_count"] or 1,
            "is_failure": True,
        })
    return results


def promote_failure_to_insight(session, candidates: list[dict]) -> int:
    """Write anti-pattern Insight nodes from failure clusters. Returns count."""
    promoted = 0
    for c in candidates:
        ins_id = f"ins:antipattern:{c['label'].lower().replace(' ', '_')[:40]}"
        source_count = c["source_count"]
        cluster = c["failure_cluster_size"]

        # Failure insights get elevated strength — one confirmed failure is worth
        # more signal than many success observations
        pattern_strength = min(
            math.log10(max(source_count, 1) + 1) * min((cluster + 1) / 3.0, 1.0) + 0.2,
            1.0,
        )

        lesson = c["lesson"] or f"Pattern failed across {source_count} sources."
        content = f"ANTI-PATTERN: {lesson} Context: {c['context']}"

        session.run(
            """
            MERGE (i:Insight {id: $id})
            ON CREATE SET
                i.label = $label,
                i.content = $content,
                i.pattern_strength = $strength,
                i.source_count = $count,
                i.is_antipattern = true,
                i.timestamp = $ts,
                i.tier = 'insight'
            ON MATCH SET
                i.pattern_strength = CASE WHEN $strength > i.pattern_strength
                    THEN $strength ELSE i.pattern_strength END,
                i.source_count = $count,
                i.content = $content,
                i.is_antipattern = true
            """,
            id=ins_id,
            label=f"[AVOID] {c['label']}",
            content=content,
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


# ── Step 2b: Experience → Insight (success patterns) ────────────────────────

def find_insight_candidates(session) -> list[dict]:
    """Find Experience clusters with 3+ members — success patterns."""
    query = """
    MATCH (e:Experience)
    WHERE e.outcome <> 'FAILED' OR e.outcome IS NULL
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
            "is_failure": False,
        })
    return results


def promote_to_insight(session, candidates: list[dict]) -> int:
    """Write Insight nodes from success patterns. Returns promotion count."""
    promoted = 0
    for c in candidates:
        ins_id = f"ins:{c['label'].lower().replace(' ', '_')[:40]}"
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
                i.is_antipattern = false,
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
    """Find Insights strong enough to crystallize into Wisdom.

    Anti-pattern Insights have a lower threshold — failure knowledge
    crystallizes faster because it's harder to acquire.
    """
    query = """
    MATCH (i:Insight)
    WHERE (
        (coalesce(i.is_antipattern, false) = true  AND i.pattern_strength >= 0.35 AND i.source_count >= 1) OR
        (coalesce(i.is_antipattern, false) = false AND i.pattern_strength >= 0.5  AND i.source_count >= 3)
    )
    AND NOT (i)-[:CRYSTALLIZES_INTO]->(:Wisdom)
    RETURN i.id AS id, i.label AS label,
           i.pattern_strength AS strength,
           i.source_count AS count,
           i.content AS content,
           coalesce(i.is_antipattern, false) AS is_antipattern
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
            "is_antipattern": record["is_antipattern"],
        })
    return results


def write_wisdom(session, wisdom_nodes: list[dict]) -> int:
    """Write Wisdom nodes from LLM-generated principles. Returns count written.

    Failure-grounded Wisdom gets a confidence bonus — hard-won knowledge
    earned through failure is more reliable than success-pattern inference.
    """
    written = 0
    for w in wisdom_nodes:
        base_confidence = float(w.get("confidence", 0.7))
        # Failure-grounded wisdom earns higher baseline confidence
        if w.get("is_antipattern"):
            confidence = min(base_confidence + FAILURE_CONFIDENCE_BONUS, 1.0)
        else:
            confidence = base_confidence

        session.run(
            """
            MERGE (wis:Wisdom {id: $id})
            ON CREATE SET
                wis.label = $label,
                wis.principle = $principle,
                wis.confidence = $confidence,
                wis.is_antipattern = $is_antipattern,
                wis.reinforcement_count = 0,
                wis.timestamp = $ts,
                wis.tier = 'wisdom'
            ON MATCH SET
                wis.principle = $principle,
                wis.confidence = CASE WHEN $confidence > wis.confidence
                    THEN $confidence ELSE wis.confidence END,
                wis.is_antipattern = $is_antipattern
            """,
            id=w["id"],
            label=w["label"],
            principle=w["principle"],
            confidence=confidence,
            is_antipattern=bool(w.get("is_antipattern", False)),
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


# ── Step 4: PREVENTS edges — anti-pattern Wisdom → Knowledge to avoid ────────

def write_prevents_edges(session) -> int:
    """Write PREVENTS edges from anti-pattern Wisdom back to grounding Knowledge.

    This is the 'standing on shoulders of giants' edge — Wisdom earned from
    failure points back at the Knowledge patterns that led there, so future
    traversals surface the warning before going down the same path.
    """
    query = """
    MATCH (wis:Wisdom)
    WHERE wis.is_antipattern = true
    MATCH (wis)<-[:CRYSTALLIZES_INTO]-(i:Insight)<-[:REVEALS]-(e:Experience)
    WHERE e.outcome = 'FAILED'
    MATCH (e)<-[:GROUNDS]-(k:Knowledge)
    MERGE (wis)-[r:PREVENTS]->(k)
    ON CREATE SET r.weight = 1.0, r.created = $ts
    ON MATCH SET r.weight = coalesce(r.weight, 1.0) + 0.2
    RETURN count(r) AS written
    """
    result = session.run(query, ts=_utcnow())
    record = result.single()
    return record["written"] if record else 0


# ── Step 5: REINFORCES edges — successful Wisdom → Knowledge ─────────────────

def write_reinforcement_edges(session) -> int:
    """Write REINFORCES edges from successful Wisdom back to grounding Knowledge."""
    query = """
    MATCH (wis:Wisdom)
    WHERE coalesce(wis.is_antipattern, false) = false
    AND wis.reinforcement_count >= 2
    MATCH (wis)<-[:CRYSTALLIZES_INTO*0..1]-(i:Insight)
    MATCH (i)<-[:REVEALS*0..1]-(e:Experience)
    MATCH (e)<-[:GROUNDS*0..1]-(k:Knowledge)
    MERGE (wis)-[r:REINFORCES]->(k)
    ON CREATE SET r.weight = 1.0
    ON MATCH SET r.weight = coalesce(r.weight, 1.0) + 0.1
    RETURN count(r) AS written
    """
    result = session.run(query)
    record = result.single()
    return record["written"] if record else 0


# ── Public entry point ────────────────────────────────────────────────────────

def run_reflect(session, project: str | None = None) -> dict:
    """Run the full promotion pipeline. Returns stats dict.

    Pipeline order matters:
    1. Promote Knowledge → Experience (both success and failure)
    2. Promote FAILED Experiences → anti-pattern Insights FIRST
    3. Promote success Experiences → Insights
    4. Find Wisdom candidates (failure threshold is lower)
    5. Write PREVENTS edges (failure wisdom → Knowledge to avoid)
    6. Write REINFORCES edges (success wisdom → Knowledge to build on)
    """
    stats: dict = {}

    # Step 1
    exp_candidates = find_experience_candidates(session, project)
    stats["experience_promoted"] = promote_to_experience(session, exp_candidates)

    # Step 2a — failure anti-patterns first
    failure_candidates = find_failure_insight_candidates(session)
    stats["failure_insight_promoted"] = promote_failure_to_insight(session, failure_candidates)

    # Step 2b — success patterns
    ins_candidates = find_insight_candidates(session)
    stats["insight_promoted"] = promote_to_insight(session, ins_candidates)

    # Step 3
    wis_candidates = find_wisdom_candidates(session)
    stats["wisdom_candidates"] = len(wis_candidates)
    stats["wisdom_candidates_data"] = wis_candidates

    # Step 4 — PREVENTS edges
    stats["prevents_edges"] = write_prevents_edges(session)

    # Step 5 — REINFORCES edges
    stats["reinforcement_edges"] = write_reinforcement_edges(session)

    return stats
