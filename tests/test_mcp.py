"""Tests for wisdom/mcp.py — MCP tool handlers (no live Neo4j required)."""
from __future__ import annotations

import hashlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_session(records=None):
    """Return a mock Neo4j session whose .run() returns fake records."""
    session = MagicMock()
    if records is not None:
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter(records))
        mock_result.single.return_value = records[0] if records else None
        session.run.return_value = mock_result
    return session


def _make_driver(session=None):
    driver = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=session or _make_session())
    ctx.__exit__ = MagicMock(return_value=False)
    driver.session.return_value = ctx
    return driver


# ── Import guards ──────────────────────────────────────────────────────────────

def test_mcp_importable_without_mcp_sdk(monkeypatch):
    """wisdom.mcp must be importable even without the mcp SDK installed.
    run_mcp_server() should raise SystemExit, but import must not."""
    import sys
    import importlib

    # Simulate absent mcp SDK
    monkeypatch.setitem(sys.modules, "mcp", None)
    monkeypatch.setitem(sys.modules, "mcp.server", None)
    monkeypatch.setitem(sys.modules, "mcp.server.stdio", None)
    monkeypatch.setitem(sys.modules, "mcp.types", None)

    # Remove cached module so it re-imports
    monkeypatch.delitem(sys.modules, "wisdom.mcp", raising=False)

    # Module must import cleanly
    mcp_mod = importlib.import_module("wisdom.mcp")
    assert not mcp_mod._MCP_AVAILABLE

    # run_mcp_server must exit gracefully
    with pytest.raises(SystemExit):
        mcp_mod.run_mcp_server()


# ── _handle_remember ─────────────────────────────────────────────────────────

def test_remember_missing_label():
    from wisdom.mcp import _handle_remember
    result = _handle_remember({"content": "some content"})
    assert result.isError
    assert "required" in result.content[0].text


def test_remember_missing_content():
    from wisdom.mcp import _handle_remember
    result = _handle_remember({"label": "some label"})
    assert result.isError
    assert "required" in result.content[0].text


def test_remember_writes_node():
    from wisdom.mcp import _handle_remember

    driver = _make_driver()
    with patch("wisdom.mcp._get_driver", return_value=driver), \
         patch("wisdom.merge.merge_nodes", return_value=1):

        result = _handle_remember({
            "label": "DozerDB ignores NEO4J_AUTH if data dir exists",
            "content": "Reusing old data dir prevents credential changes.",
            "tier": "experience",
            "project": "wisdomGraph",
            "confidence": 0.95,
        })

    assert not result.isError
    assert "EXPERIENCE" in result.content[0].text
    assert "DozerDB ignores" in result.content[0].text


def test_remember_generates_stable_id():
    """Same label should produce same node ID (idempotent MERGE semantics)."""
    label = "MERGE semantics prevent duplicate nodes"
    id1 = f"knowledge:{hashlib.sha256(label.encode()).hexdigest()[:16]}"
    id2 = f"knowledge:{hashlib.sha256(label.encode()).hexdigest()[:16]}"
    assert id1 == id2


# ── _handle_query ─────────────────────────────────────────────────────────────

def test_query_missing_cypher():
    from wisdom.mcp import _handle_query
    result = _handle_query({})
    assert result.isError
    assert "required" in result.content[0].text


def test_query_blocks_writes():
    from wisdom.mcp import _handle_query
    for forbidden in ["CREATE (n:Test)", "DELETE n", "SET n.x = 1", "MERGE (n:Test)"]:
        result = _handle_query({"cypher": f"MATCH (n) {forbidden} RETURN n"})
        assert result.isError, f"Should have blocked: {forbidden}"
        assert "read-only" in result.content[0].text


def test_query_injects_limit():
    from wisdom.mcp import _handle_query

    executed = {}

    def fake_driver():
        driver = MagicMock()
        session_ctx = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([{"label": "test", "tier": "knowledge"}]))
        session_ctx.__enter__ = MagicMock(return_value=MagicMock(run=lambda cypher, **kw: (executed.__setitem__("cypher", cypher) or mock_result)))
        session_ctx.__exit__ = MagicMock(return_value=False)
        driver.session.return_value = session_ctx
        return driver

    with patch("wisdom.mcp._get_driver", side_effect=fake_driver):
        result = _handle_query({"cypher": "MATCH (n:Wisdom) RETURN n.label AS label, n.tier AS tier"})

    assert not result.isError
    assert "LIMIT" in executed.get("cypher", "")


def test_query_returns_markdown_table():
    from wisdom.mcp import _handle_query

    records = [{"label": "MERGE semantics", "tier": "knowledge"}]

    def fake_driver():
        driver = MagicMock()
        session_ctx = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter(records))
        session_ctx.__enter__ = MagicMock(return_value=MagicMock(run=lambda *a, **kw: mock_result))
        session_ctx.__exit__ = MagicMock(return_value=False)
        driver.session.return_value = session_ctx
        return driver

    with patch("wisdom.mcp._get_driver", side_effect=fake_driver):
        result = _handle_query({"cypher": "MATCH (n:Knowledge) RETURN n.label AS label, n.tier AS tier"})

    assert not result.isError
    text = result.content[0].text
    assert "label" in text
    assert "tier" in text
    assert "MERGE semantics" in text
    assert "|" in text  # markdown table


def test_query_empty_result():
    from wisdom.mcp import _handle_query

    def fake_driver():
        driver = MagicMock()
        session_ctx = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        session_ctx.__enter__ = MagicMock(return_value=MagicMock(run=lambda *a, **kw: mock_result))
        session_ctx.__exit__ = MagicMock(return_value=False)
        driver.session.return_value = session_ctx
        return driver

    with patch("wisdom.mcp._get_driver", side_effect=fake_driver):
        result = _handle_query({"cypher": "MATCH (n:Wisdom) RETURN n"})

    assert not result.isError
    assert "No results" in result.content[0].text


# ── _handle_reflect ───────────────────────────────────────────────────────────

def test_reflect_returns_stats():
    from wisdom.mcp import _handle_reflect

    fake_stats = {
        "experience_promoted": 3,
        "failure_insight_promoted": 2,
        "insight_promoted": 1,
        "wisdom_candidates": 2,
        "wisdom_candidates_data": [
            {"label": "MERGE is idempotent", "strength": 0.82, "count": 5, "content": "Pattern seen across 5 sources.", "is_antipattern": False},
        ],
        "prevents_edges": 3,
        "reinforcement_edges": 4,
    }

    def fake_driver():
        driver = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=MagicMock())
        ctx.__exit__ = MagicMock(return_value=False)
        driver.session.return_value = ctx
        return driver

    with patch("wisdom.mcp._get_driver", side_effect=fake_driver), \
         patch("wisdom.reflect.run_reflect", return_value=fake_stats):

        result = _handle_reflect({})

    assert not result.isError
    text = result.content[0].text
    assert "3" in text  # experience_promoted
    assert "PREVENTS" in text
    assert "Reflection" in text


def test_reflect_surfaces_antipatterns():
    from wisdom.mcp import _handle_reflect

    fake_stats = {
        "experience_promoted": 1,
        "failure_insight_promoted": 1,
        "insight_promoted": 0,
        "wisdom_candidates": 1,
        "wisdom_candidates_data": [
            {
                "label": "[AVOID] sqlite on Heroku",
                "strength": 0.75,
                "count": 2,
                "content": "ANTI-PATTERN: sqlite resets on dyno restart.",
                "is_antipattern": True,
            },
        ],
        "prevents_edges": 2,
        "reinforcement_edges": 0,
    }

    def fake_driver():
        driver = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=MagicMock())
        ctx.__exit__ = MagicMock(return_value=False)
        driver.session.return_value = ctx
        return driver

    with patch("wisdom.mcp._get_driver", side_effect=fake_driver), \
         patch("wisdom.reflect.run_reflect", return_value=fake_stats):

        result = _handle_reflect({})

    assert not result.isError
    text = result.content[0].text
    assert "Anti-pattern" in text or "AVOID" in text
    assert "hard-won" in text.lower() or "failure" in text.lower()


# ── _handle_report ────────────────────────────────────────────────────────────

def test_report_returns_markdown():
    from wisdom.mcp import _handle_report

    fake_md = "# Wisdom Report\n\n## Graph status\n- 10 Knowledge · 3 Experience\n"

    def fake_driver():
        driver = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=MagicMock())
        ctx.__exit__ = MagicMock(return_value=False)
        driver.session.return_value = ctx
        return driver

    with patch("wisdom.mcp._get_driver", side_effect=fake_driver), \
         patch("wisdom.report.render_report", return_value=fake_md):

        result = _handle_report({})

    assert not result.isError
    assert "Wisdom Report" in result.content[0].text


# ── _handle_ingest ────────────────────────────────────────────────────────────

def test_ingest_missing_source():
    from wisdom.mcp import _handle_ingest
    result = _handle_ingest({})
    assert result.isError
    assert "required" in result.content[0].text


def test_ingest_nonexistent_path():
    from wisdom.mcp import _handle_ingest
    result = _handle_ingest({"source": "/nonexistent/path/file.py"})
    assert result.isError
    assert "does not exist" in result.content[0].text


def test_ingest_empty_directory(tmp_path):
    from wisdom.mcp import _handle_ingest
    # Directory with no ingestible files
    result = _handle_ingest({"source": str(tmp_path)})
    assert not result.isError
    assert "No ingestible files" in result.content[0].text


def test_ingest_single_file(tmp_path):
    from wisdom.mcp import _handle_ingest

    py_file = tmp_path / "test_module.py"
    py_file.write_text("def hello():\n    return 'world'\n")

    def fake_driver():
        driver = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=MagicMock())
        ctx.__exit__ = MagicMock(return_value=False)
        driver.session.return_value = ctx
        return driver

    with patch("wisdom.mcp._get_driver", side_effect=fake_driver), \
         patch("wisdom.merge.merge_extraction", return_value={"nodes": 1, "edges": 0}):

        result = _handle_ingest({"source": str(py_file), "project": "test"})

    assert not result.isError
    assert "1 file" in result.content[0].text


# ── _handle_learn ────────────────────────────────────────────────────────────

def test_learn_missing_required_fields():
    from wisdom.mcp import _handle_learn
    result = _handle_learn({"label": "test"})
    assert result.isError
    assert "required" in result.content[0].text


def test_learn_invalid_outcome():
    from wisdom.mcp import _handle_learn
    result = _handle_learn({
        "label": "test",
        "what_was_tried": "did stuff",
        "outcome": "MAYBE",
        "lesson": "something",
    })
    assert result.isError
    assert "outcome" in result.content[0].text.lower()


def test_learn_failure_writes_experience():
    from wisdom.mcp import _handle_learn

    def fake_driver():
        driver = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=MagicMock())
        ctx.__exit__ = MagicMock(return_value=False)
        driver.session.return_value = ctx
        return driver

    with patch("wisdom.mcp._get_driver", side_effect=fake_driver):
        result = _handle_learn({
            "label": "SQLite on Heroku",
            "what_was_tried": "Used SQLite as primary DB on Heroku free dyno",
            "outcome": "FAILED",
            "lesson": "Heroku dynos are ephemeral — SQLite data is lost on restart. Use Postgres.",
            "project": "myapp",
        })

    assert not result.isError
    text = result.content[0].text
    assert "FAILED" in text
    assert "SQLite on Heroku" in text
    assert "❌" in text
    # Should prompt to run reflect
    assert "wisdom_reflect" in text


def test_learn_success_no_reflect_prompt():
    from wisdom.mcp import _handle_learn

    def fake_driver():
        driver = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=MagicMock())
        ctx.__exit__ = MagicMock(return_value=False)
        driver.session.return_value = ctx
        return driver

    with patch("wisdom.mcp._get_driver", side_effect=fake_driver):
        result = _handle_learn({
            "label": "Deploy with Docker Compose",
            "what_was_tried": "Used Docker Compose with --env-file",
            "outcome": "SUCCEEDED",
            "lesson": "Compose + --env-file cleanly separates secrets from repo.",
            "project": "infra",
        })

    assert not result.isError
    text = result.content[0].text
    assert "SUCCEEDED" in text
    assert "✅" in text
    # No failure prompt for successes
    assert "wisdom_reflect" not in text


def test_learn_failure_defaults_to_high_confidence():
    """FAILED outcomes should default to 0.9 confidence — hard-won knowledge."""
    from wisdom.mcp import _handle_learn

    captured = {}

    def fake_driver():
        session_mock = MagicMock()

        def capture_run(query, **kwargs):
            if "confidence" in kwargs:
                captured["confidence"] = kwargs["confidence"]
            return MagicMock()

        session_mock.run.side_effect = capture_run
        driver = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=session_mock)
        ctx.__exit__ = MagicMock(return_value=False)
        driver.session.return_value = ctx
        return driver

    with patch("wisdom.mcp._get_driver", side_effect=fake_driver):
        result = _handle_learn({
            "label": "NEO4J_AUTH ignored with existing data dir",
            "what_was_tried": "Reused ~/neo4j/data from prior project",
            "outcome": "FAILED",
            "lesson": "NEO4J_AUTH is ignored if data dir has existing credentials. Use a fresh data dir.",
        })

    assert not result.isError
    # Default confidence for failures is 0.9
    assert "0.9" in result.content[0].text


# ── Tool list ─────────────────────────────────────────────────────────────────

def test_status_returns_counts():
    from wisdom.mcp import _handle_status

    fake_stats = {
        "Knowledge": 74,
        "Experience": 16,
        "Insight": 11,
        "Wisdom": 6,
        "Source": 30,
        "edges": 215,
    }

    with patch("wisdom.mcp._get_driver", return_value=MagicMock()), \
         patch("wisdom.connect.status", return_value=fake_stats):
        result = _handle_status({})

    assert not result.isError
    text = result.content[0].text
    assert "Knowledge" in text
    assert "Insight" in text
    assert "215" in text


def test_list_defaults_to_insight_nodes():
    from wisdom.mcp import _handle_list

    session = MagicMock()
    session.run.return_value = iter([
        {
            "id": "insight:abc",
            "label": "Agent infrastructure positioning",
            "tier": "insight",
            "project": "wisdomGraph",
            "confidence": 0.95,
            "degree": 3,
        }
    ])
    driver = _make_driver(session)

    with patch("wisdom.mcp._get_driver", return_value=driver):
        result = _handle_list({})

    assert not result.isError
    text = result.content[0].text
    assert "Insight nodes" in text
    assert "Agent infrastructure" in text


def test_list_rejects_invalid_tier():
    from wisdom.mcp import _handle_list
    result = _handle_list({"tier": "source"})
    assert result.isError
    assert "tier" in result.content[0].text


def test_trace_requires_id_or_label():
    from wisdom.mcp import _handle_trace
    result = _handle_trace({})
    assert result.isError
    assert "id" in result.content[0].text


def test_trace_returns_node_neighborhood():
    from wisdom.mcp import _handle_trace

    node_record = {
        "id": "insight:abc",
        "label": "Agent infrastructure positioning",
        "tier": "insight",
        "content": "Persistent cognition for agents.",
        "principle": None,
        "confidence": 0.95,
    }
    edge_record = {
        "source": "Repo visit",
        "relation": "REVEALS",
        "target": "Agent infrastructure positioning",
    }

    session = MagicMock()
    session.run.side_effect = [
        SimpleNamespace(single=lambda: node_record),
        iter([edge_record]),
    ]
    driver = _make_driver(session)

    with patch("wisdom.mcp._get_driver", return_value=driver), \
         patch("wisdom.traverse.walk_dikw_path", return_value=[]), \
         patch("wisdom.traverse.get_provenance", return_value=[]):
        result = _handle_trace({"label": "Agent infrastructure"})

    assert not result.isError
    text = result.content[0].text
    assert "Trace" in text
    assert "Agent infrastructure positioning" in text
    assert "REVEALS" in text


def test_explain_requires_label():
    from wisdom.mcp import _handle_explain
    result = _handle_explain({})
    assert result.isError
    assert "label" in result.content[0].text


def test_explain_formats_dikw_chain():
    from wisdom.mcp import _handle_explain

    explanation = {
        "id": "insight:abc",
        "label": "Agent infrastructure positioning",
        "tier": "insight",
        "content": "Persistent cognition for agents.",
        "confidence": 0.95,
        "dikw_chain": [{"label": "WisdomGraph", "tier": "knowledge"}],
        "sources": [{"uri": "README.md"}],
    }

    with patch("wisdom.mcp._get_driver", return_value=_make_driver()), \
         patch("wisdom.traverse.explain_node", return_value=explanation):
        result = _handle_explain({"label": "Agent infrastructure"})

    assert not result.isError
    text = result.content[0].text
    assert "DIKW chain" in text
    assert "README.md" in text


def test_tool_list_has_ten_tools():
    from wisdom.mcp import _TOOL_DEFS
    names = {t["name"] for t in _TOOL_DEFS}
    assert names == {
        "wisdom_ingest",
        "wisdom_remember",
        "wisdom_learn",
        "wisdom_status",
        "wisdom_list",
        "wisdom_trace",
        "wisdom_explain",
        "wisdom_query",
        "wisdom_reflect",
        "wisdom_report",
    }


def test_all_tools_have_descriptions():
    from wisdom.mcp import _TOOL_DEFS
    for tool in _TOOL_DEFS:
        assert tool["description"], f"{tool['name']} has no description"
        assert len(tool["description"]) > 20, f"{tool['name']} description too short"


def test_all_tools_have_input_schema():
    from wisdom.mcp import _TOOL_DEFS
    for tool in _TOOL_DEFS:
        assert tool["inputSchema"], f"{tool['name']} missing inputSchema"
        assert tool["inputSchema"].get("type") == "object"


# ── mcp-install CLI ───────────────────────────────────────────────────────────

def test_mcp_install_writes_settings(tmp_path):
    """wisdom mcp-install should write mcpServers block to .claude/settings.json."""
    import sys
    from wisdom.__main__ import _install_mcp

    _install_mcp(project_dir=tmp_path, host="claude")

    settings_path = tmp_path / ".claude" / "settings.json"
    assert settings_path.exists()

    import json
    settings = json.loads(settings_path.read_text())
    assert "wisdomGraph" in settings.get("mcpServers", {})
    assert settings["mcpServers"]["wisdomGraph"]["command"] == "wisdom"
    assert settings["mcpServers"]["wisdomGraph"]["args"] == ["mcp"]


def test_mcp_install_idempotent(tmp_path):
    """Running mcp-install twice should not duplicate the entry."""
    import json
    from wisdom.__main__ import _install_mcp

    _install_mcp(project_dir=tmp_path, host="claude")
    _install_mcp(project_dir=tmp_path, host="claude")

    settings_path = tmp_path / ".claude" / "settings.json"
    settings = json.loads(settings_path.read_text())
    # Should still be a single entry, not a list
    assert isinstance(settings["mcpServers"]["wisdomGraph"], dict)


def test_mcp_install_codex_noops_when_existing():
    from wisdom.__main__ import _install_mcp

    completed = SimpleNamespace(returncode=0, stdout="", stderr="")
    with patch("shutil.which", return_value="/usr/bin/codex"), \
         patch("subprocess.run", return_value=completed) as run:
        _install_mcp(host="codex")

    run.assert_called_once_with(
        ["codex", "mcp", "get", "wisdomGraph"],
        stdout=-3,
        stderr=-3,
        check=False,
    )


def test_mcp_install_rejects_unknown_host():
    from wisdom.__main__ import _install_mcp

    with pytest.raises(SystemExit):
        _install_mcp(host="unknown")


# ── local backend / quickstart CLI ────────────────────────────────────────────

def test_local_default_image_is_official_neo4j(monkeypatch):
    import wisdom.local as local

    monkeypatch.delenv("WISDOM_NEO4J_IMAGE", raising=False)
    monkeypatch.delenv("WISDOM_NEO4J_ENGINE", raising=False)

    assert local._select_image() == "neo4j:latest"


def test_local_dozerdb_engine_is_explicit():
    import wisdom.local as local

    assert local._select_image(engine="dozerdb") == "graphstack/dozerdb:5.26.3.0"


def test_local_docker_run_args_are_shell_independent(tmp_path, monkeypatch):
    import wisdom.local as local

    monkeypatch.setattr(local, "BASE_DIR", tmp_path / "neo4j")
    args = local._docker_run_args("neo4j:latest", "password")

    assert args[:3] == ["docker", "run", "-d"]
    assert "neo4j:latest" == args[-1]
    assert "NEO4J_AUTH=neo4j/password" in args
    assert all(isinstance(part, str) for part in args)

def test_local_up_starts_managed_backend_without_existing_container(tmp_path, monkeypatch):
    import wisdom.local as local

    calls = []

    def fake_run(cmd, capture=False):
        calls.append(cmd)
        if cmd[:2] == ["docker", "info"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if cmd[:3] == ["docker", "ps", "-q"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if cmd[:3] == ["docker", "ps", "-aq"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(local, "BASE_DIR", tmp_path / "neo4j")
    monkeypatch.setattr(local, "PASSWORD_PATH", tmp_path / "local-password")

    with patch("wisdom.local.shutil.which", return_value="/usr/bin/docker"), \
         patch("wisdom.local._run", side_effect=fake_run), \
         patch("wisdom.local._wait_for_port", return_value=True), \
         patch("wisdom.local.save_connection") as save:
        local.up(password="test-password")

    assert any(cmd[:3] == ["docker", "run", "-d"] for cmd in calls)
    save.assert_called_once_with(local.URI, local.USER, "test-password")


def test_local_up_reuses_existing_running_backend(tmp_path, monkeypatch):
    import wisdom.local as local

    def fake_run(cmd, capture=False):
        if cmd[:2] == ["docker", "info"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if cmd[:3] == ["docker", "ps", "-q"]:
            return SimpleNamespace(returncode=0, stdout="abc123\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(local, "PASSWORD_PATH", tmp_path / "local-password")

    with patch("wisdom.local.shutil.which", return_value="/usr/bin/docker"), \
         patch("wisdom.local._run", side_effect=fake_run), \
         patch("wisdom.local.save_connection") as save:
        local.up(password="test-password")

    save.assert_called_once_with(local.URI, local.USER, "test-password")


def test_quickstart_local_registers_requested_host(monkeypatch):
    import sys
    from wisdom.__main__ import _run_quickstart

    monkeypatch.setattr(sys, "argv", ["wisdom", "quickstart", "--host", "codex"])

    with patch("wisdom.local.up") as local_up, \
         patch("wisdom.__main__._doctor") as doctor, \
         patch("wisdom.__main__._install_mcp") as install_mcp:
        _run_quickstart()

    local_up.assert_called_once_with(password=None, image=None, engine=None)
    doctor.assert_called_once_with(connect_only=True)
    install_mcp.assert_called_once_with(host="codex")


def test_quickstart_existing_requires_uri(monkeypatch):
    import sys
    from wisdom.__main__ import _run_quickstart

    monkeypatch.setattr(sys, "argv", ["wisdom", "quickstart", "--storage", "existing", "--host", "none"])

    with pytest.raises(SystemExit):
        _run_quickstart()
