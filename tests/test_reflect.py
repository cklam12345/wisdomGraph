"""Tests for wisdom/reflect.py — DIKW promotion pipeline + failure knowledge."""
from __future__ import annotations

import math
from unittest.mock import MagicMock, call

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_session(records_by_query=None):
    """Mock Neo4j session. Optionally provide a list of record dicts to return."""
    session = MagicMock()
    if records_by_query is not None:
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter(records_by_query))
        mock_result.single.return_value = records_by_query[0] if records_by_query else None
        session.run.return_value = mock_result
    return session


# ── Constants ─────────────────────────────────────────────────────────────────

def test_outcome_constants():
    from wisdom.reflect import (
        OUTCOME_FAILED, OUTCOME_SUCCEEDED, OUTCOME_PARTIAL, OUTCOME_UNKNOWN
    )
    assert OUTCOME_FAILED == "FAILED"
    assert OUTCOME_SUCCEEDED == "SUCCEEDED"
    assert OUTCOME_PARTIAL == "PARTIAL"
    assert OUTCOME_UNKNOWN == "UNKNOWN"


def test_failure_confidence_bonus():
    from wisdom.reflect import FAILURE_CONFIDENCE_BONUS
    assert FAILURE_CONFIDENCE_BONUS == 0.15


# ── find_experience_candidates ────────────────────────────────────────────────

def test_find_experience_candidates_returns_list():
    from wisdom.reflect import find_experience_candidates

    records = [
        {"lbl": "MERGE semantics", "projects": ["proj_a", "proj_b"], "ids": ["k:1", "k:2"]},
        {"lbl": "Docker Compose", "projects": ["proj_a", "proj_b", "proj_c"], "ids": ["k:3", "k:4", "k:5"]},
    ]
    session = _make_session(records)
    result = find_experience_candidates(session)

    assert len(result) == 2
    assert result[0]["label"] == "MERGE semantics"
    assert result[1]["label"] == "Docker Compose"
    assert len(result[1]["projects"]) == 3


def test_find_experience_candidates_empty():
    from wisdom.reflect import find_experience_candidates
    session = _make_session([])
    result = find_experience_candidates(session)
    assert result == []


# ── promote_to_experience ─────────────────────────────────────────────────────

def test_promote_to_experience_returns_count():
    from wisdom.reflect import promote_to_experience
    session = MagicMock()
    candidates = [
        {"label": "MERGE semantics", "projects": ["a", "b"], "ids": ["k:1"]},
        {"label": "Docker Compose",  "projects": ["a", "b", "c"], "ids": ["k:2", "k:3"]},
    ]
    count = promote_to_experience(session, candidates)
    assert count == 2
    # Should run at least once per candidate (MERGE node) + once per source id (GROUNDS edge)
    assert session.run.call_count >= 4


def test_promote_to_experience_empty():
    from wisdom.reflect import promote_to_experience
    session = MagicMock()
    count = promote_to_experience(session, [])
    assert count == 0
    session.run.assert_not_called()


# ── find_failure_insight_candidates ──────────────────────────────────────────

def test_find_failure_insight_candidates_returns_failures():
    from wisdom.reflect import find_failure_insight_candidates

    records = [
        {
            "id": "exp:sqlite_on_heroku",
            "label": "SQLite on Heroku",
            "lesson": "SQLite resets on dyno restart",
            "context": "Deployed to Heroku free tier",
            "failure_cluster_size": 2,
            "source_count": 3,
        },
    ]
    session = _make_session(records)
    result = find_failure_insight_candidates(session)

    assert len(result) == 1
    assert result[0]["is_failure"] is True
    assert result[0]["label"] == "SQLite on Heroku"
    assert result[0]["lesson"] == "SQLite resets on dyno restart"
    assert result[0]["failure_cluster_size"] == 2


def test_find_failure_insight_candidates_fills_defaults():
    from wisdom.reflect import find_failure_insight_candidates

    records = [
        {
            "id": "exp:unknown_failure",
            "label": "Unknown failure",
            "lesson": None,   # NULL in DB → should default to ""
            "context": None,
            "failure_cluster_size": None,
            "source_count": None,
        },
    ]
    session = _make_session(records)
    result = find_failure_insight_candidates(session)

    assert result[0]["lesson"] == ""
    assert result[0]["context"] == ""
    assert result[0]["failure_cluster_size"] == 0
    assert result[0]["source_count"] == 1


# ── promote_failure_to_insight ────────────────────────────────────────────────

def test_promote_failure_to_insight_creates_avoid_label():
    from wisdom.reflect import promote_failure_to_insight

    session = MagicMock()
    candidates = [{
        "id": "exp:sqlite_on_heroku",
        "label": "SQLite on Heroku",
        "lesson": "SQLite resets on dyno restart. Use Postgres.",
        "context": "Heroku free tier project",
        "failure_cluster_size": 2,
        "source_count": 3,
        "is_failure": True,
    }]

    count = promote_failure_to_insight(session, candidates)
    assert count == 1

    # Inspect the MERGE call — label should be [AVOID] prefixed
    merge_call = session.run.call_args_list[0]
    # The label kwarg should contain [AVOID]
    call_kwargs = merge_call[1]
    assert "[AVOID]" in call_kwargs.get("label", "")


def test_promote_failure_to_insight_elevated_pattern_strength():
    """Anti-pattern insight strength should include the 0.2 base bonus."""
    from wisdom.reflect import promote_failure_to_insight

    session = MagicMock()
    candidates = [{
        "id": "exp:fail",
        "label": "some failure",
        "lesson": "it broke",
        "context": "ctx",
        "failure_cluster_size": 1,
        "source_count": 2,
        "is_failure": True,
    }]
    promote_failure_to_insight(session, candidates)

    # Verify strength > 0 (formula includes 0.2 base)
    call_kwargs = session.run.call_args_list[0][1]
    strength = call_kwargs.get("strength", 0)
    assert strength >= 0.2, f"Expected >= 0.2, got {strength}"


def test_promote_failure_to_insight_empty():
    from wisdom.reflect import promote_failure_to_insight
    session = MagicMock()
    count = promote_failure_to_insight(session, [])
    assert count == 0


# ── find_wisdom_candidates ────────────────────────────────────────────────────

def test_find_wisdom_candidates_returns_list():
    from wisdom.reflect import find_wisdom_candidates

    records = [
        {
            "id": "ins:antipattern:sqlite_on_heroku",
            "label": "[AVOID] SQLite on Heroku",
            "strength": 0.75,
            "count": 3,
            "content": "ANTI-PATTERN: SQLite resets on dyno restart.",
            "is_antipattern": True,
        },
    ]
    session = _make_session(records)
    result = find_wisdom_candidates(session)

    assert len(result) == 1
    assert result[0]["is_antipattern"] is True
    assert result[0]["strength"] == 0.75


# ── write_wisdom ──────────────────────────────────────────────────────────────

def test_write_wisdom_applies_failure_confidence_bonus():
    """Anti-pattern Wisdom nodes should get FAILURE_CONFIDENCE_BONUS added."""
    from wisdom.reflect import write_wisdom, FAILURE_CONFIDENCE_BONUS

    session = MagicMock()
    wisdom_nodes = [{
        "id": "wis:antipattern:sqlite_on_heroku",
        "label": "[AVOID] SQLite on Heroku",
        "principle": "Never use SQLite on ephemeral dynos. Heroku ephemeral FS erases data on restart.",
        "confidence": 0.7,
        "is_antipattern": True,
        "insight_id": "ins:antipattern:sqlite_on_heroku",
    }]

    write_wisdom(session, wisdom_nodes)

    call_kwargs = session.run.call_args_list[0][1]
    actual_confidence = call_kwargs.get("confidence", 0)
    expected = min(0.7 + FAILURE_CONFIDENCE_BONUS, 1.0)
    assert abs(actual_confidence - expected) < 0.001, \
        f"Expected confidence={expected}, got {actual_confidence}"


def test_write_wisdom_no_bonus_for_success_patterns():
    """Regular (non-antipattern) Wisdom should NOT get the failure bonus."""
    from wisdom.reflect import write_wisdom, FAILURE_CONFIDENCE_BONUS

    session = MagicMock()
    wisdom_nodes = [{
        "id": "wis:merge_semantics",
        "label": "Always MERGE, never CREATE",
        "principle": "MERGE semantics guarantee idempotency across sessions.",
        "confidence": 0.8,
        "is_antipattern": False,
        "insight_id": "ins:merge_semantics",
    }]

    write_wisdom(session, wisdom_nodes)

    call_kwargs = session.run.call_args_list[0][1]
    actual_confidence = call_kwargs.get("confidence", 0)
    assert abs(actual_confidence - 0.8) < 0.001, \
        f"Expected 0.8 (no bonus), got {actual_confidence}"


def test_write_wisdom_caps_confidence_at_1():
    """Failure bonus must not push confidence above 1.0."""
    from wisdom.reflect import write_wisdom

    session = MagicMock()
    wisdom_nodes = [{
        "id": "wis:antipattern:test",
        "label": "[AVOID] test",
        "principle": "...",
        "confidence": 0.95,  # 0.95 + 0.15 would exceed 1.0
        "is_antipattern": True,
        "insight_id": None,
    }]

    write_wisdom(session, wisdom_nodes)

    call_kwargs = session.run.call_args_list[0][1]
    actual_confidence = call_kwargs.get("confidence", 0)
    assert actual_confidence <= 1.0


# ── run_reflect pipeline ──────────────────────────────────────────────────────

def test_run_reflect_returns_stats_dict():
    from wisdom.reflect import run_reflect
    from unittest.mock import patch

    fake_exp_candidates = [
        {"label": "MERGE", "projects": ["a", "b"], "ids": ["k:1"]},
    ]
    fake_failure_candidates = [
        {"id": "exp:x", "label": "SQLite fail", "lesson": "use postgres", "context": "", "failure_cluster_size": 1, "source_count": 1, "is_failure": True},
    ]
    fake_ins_candidates = []
    fake_wis_candidates = []

    session = MagicMock()
    single_mock = MagicMock()
    single_mock.__getitem__ = MagicMock(return_value=0)
    session.run.return_value.single.return_value = single_mock

    with patch("wisdom.reflect.find_experience_candidates", return_value=fake_exp_candidates), \
         patch("wisdom.reflect.promote_to_experience", return_value=1), \
         patch("wisdom.reflect.find_failure_insight_candidates", return_value=fake_failure_candidates), \
         patch("wisdom.reflect.promote_failure_to_insight", return_value=1), \
         patch("wisdom.reflect.find_insight_candidates", return_value=fake_ins_candidates), \
         patch("wisdom.reflect.promote_to_insight", return_value=0), \
         patch("wisdom.reflect.find_wisdom_candidates", return_value=fake_wis_candidates), \
         patch("wisdom.reflect.write_prevents_edges", return_value=2), \
         patch("wisdom.reflect.write_reinforcement_edges", return_value=0):

        stats = run_reflect(session)

    assert stats["experience_promoted"] == 1
    assert stats["failure_insight_promoted"] == 1
    assert stats["insight_promoted"] == 0
    assert stats["wisdom_candidates"] == 0
    assert stats["prevents_edges"] == 2


def test_run_reflect_failure_promoted_before_success():
    """Failure anti-patterns must be promoted BEFORE success patterns (Step 2a before 2b)."""
    from wisdom.reflect import run_reflect
    from unittest.mock import patch, call as mock_call

    call_order = []

    with patch("wisdom.reflect.find_experience_candidates", return_value=[]), \
         patch("wisdom.reflect.promote_to_experience", return_value=0), \
         patch("wisdom.reflect.find_failure_insight_candidates", side_effect=lambda s: call_order.append("failure_candidates") or []), \
         patch("wisdom.reflect.promote_failure_to_insight", side_effect=lambda s, c: call_order.append("failure_promote") or 0), \
         patch("wisdom.reflect.find_insight_candidates", side_effect=lambda s: call_order.append("insight_candidates") or []), \
         patch("wisdom.reflect.promote_to_insight", side_effect=lambda s, c: call_order.append("insight_promote") or 0), \
         patch("wisdom.reflect.find_wisdom_candidates", return_value=[]), \
         patch("wisdom.reflect.write_prevents_edges", return_value=0), \
         patch("wisdom.reflect.write_reinforcement_edges", return_value=0):

        session = MagicMock()
        run_reflect(session)

    # failure_candidates must come before insight_candidates
    fc_idx = call_order.index("failure_candidates")
    ic_idx = call_order.index("insight_candidates")
    assert fc_idx < ic_idx, f"Failure candidates ({fc_idx}) must be found before success insights ({ic_idx})"
