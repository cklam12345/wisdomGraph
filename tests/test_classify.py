"""Tests for wisdom/classify.py"""
from wisdom.classify import classify_nodes, build_dikw_edges, promote_experiences


def _node(id, label, tier=None, **kwargs):
    n = {"id": id, "label": label}
    if tier:
        n["tier"] = tier
    n.update(kwargs)
    return n


def _edge(src, tgt, relation="calls", conf_tag="EXTRACTED"):
    return {"source": src, "target": tgt, "relation": relation, "confidence_tag": conf_tag}


# ── classify_nodes ────────────────────────────────────────────────────────────

def test_default_tier_is_knowledge():
    nodes = [_node("n1", "MyFunction")]
    result = classify_nodes(nodes, [], project="proj-a")
    assert result[0]["tier"] == "knowledge"


def test_explicit_tier_respected():
    nodes = [_node("w1", "Use JWT", tier="wisdom")]
    result = classify_nodes(nodes, [], project="proj-a")
    assert result[0]["tier"] == "wisdom"


def test_insight_heuristic_3_similarity_edges():
    nodes = [_node("n1", "Auth")]
    edges = [
        _edge("n1", "n2", "semantically_similar_to"),
        _edge("n1", "n3", "semantically_similar_to"),
        _edge("n1", "n4", "conceptually_related_to"),
    ]
    result = classify_nodes(nodes, edges, project="proj-a")
    assert result[0]["tier"] == "insight"


def test_project_injected():
    nodes = [_node("n1", "Foo")]
    result = classify_nodes(nodes, [], project="my-project")
    assert result[0]["project"] == "my-project"


def test_confidence_set_for_extracted():
    nodes = [_node("n1", "Foo", confidence_tag="EXTRACTED")]
    result = classify_nodes(nodes, [], project="p")
    assert result[0]["confidence"] == 1.0


def test_confidence_lower_for_inferred():
    nodes = [_node("n1", "Foo", confidence_tag="INFERRED")]
    result = classify_nodes(nodes, [], project="p")
    assert result[0]["confidence"] < 1.0


# ── build_dikw_edges ─────────────────────────────────────────────────────────

def test_grounds_edge_added_for_k_to_e():
    nodes = [
        _node("k1", "JWT", tier="knowledge"),
        _node("e1", "JWT Context", tier="experience"),
    ]
    edges = [_edge("k1", "e1", "uses")]
    result = build_dikw_edges(nodes, edges)
    relations = [e["relation"] for e in result]
    assert "GROUNDS" in relations


def test_reveals_edge_for_e_to_i():
    nodes = [
        _node("e1", "Pattern", tier="experience"),
        _node("i1", "Auth Insight", tier="insight"),
    ]
    edges = [_edge("e1", "i1", "semantically_similar_to")]
    result = build_dikw_edges(nodes, edges)
    relations = [e["relation"] for e in result]
    assert "REVEALS" in relations


def test_no_duplicate_dikw_edges():
    nodes = [
        _node("k1", "A", tier="knowledge"),
        _node("e1", "B", tier="experience"),
    ]
    edges = [_edge("k1", "e1", "uses"), _edge("k1", "e1", "calls")]
    result = build_dikw_edges(nodes, edges)
    grounds_count = sum(1 for e in result if e["relation"] == "GROUNDS")
    assert grounds_count == 1


def test_same_tier_no_dikw_edge():
    nodes = [_node("k1", "A", tier="knowledge"), _node("k2", "B", tier="knowledge")]
    edges = [_edge("k1", "k2", "calls")]
    result = build_dikw_edges(nodes, edges)
    assert all(e["relation"] != "GROUNDS" for e in result if e["source"] == "k1" and e["target"] == "k2" and e["relation"] not in ("calls",))


# ── promote_experiences ───────────────────────────────────────────────────────

def test_promotes_knowledge_when_in_existing_projects():
    nodes = [_node("k1", "JWT", tier="knowledge")]
    result = promote_experiences(nodes, existing_projects=["k1"])
    assert result[0]["tier"] == "experience"


def test_no_promotion_when_not_in_existing():
    nodes = [_node("k1", "JWT", tier="knowledge")]
    result = promote_experiences(nodes, existing_projects=["other_id"])
    assert result[0]["tier"] == "knowledge"
