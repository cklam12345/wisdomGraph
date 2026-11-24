"""Real Relate integration tests: no Docker or external database required."""
import json
import subprocess
import sys
from unittest.mock import patch, MagicMock

import pytest

from wisdom import connect
from wisdom.embedded import EmbeddedDriver
from wisdom.merge import merge_extraction, merge_nodes
from wisdom.reflect import run_reflect, write_wisdom
from wisdom.traverse import answer_question, full_text_search, _keyword_fallback
from wisdom.export import export_json, export_cypher, export_obsidian
from wisdom.report import render_report


@pytest.fixture
def driver(tmp_path):
    driver = EmbeddedDriver(str(tmp_path / 'graph.rl'))
    connect.ensure_schema(driver)
    yield driver
    driver.close()


def test_persistence_merge_search_provenance_and_exports(driver, tmp_path):
    extraction = {'nodes': [
        {'id': 'k1', 'label': 'Graph memory', 'content': "agent's graph", 'tier': 'knowledge'},
        {'id': 'k2', 'label': 'Persistent memory', 'tier': 'knowledge'},
    ], 'edges': [{'source': 'k1', 'target': 'k2', 'relation': 'uses'}]}
    with driver.session() as session:
        for _ in range(2):
            merge_extraction(session, extraction, source_uri='notes.md')
    reopened = EmbeddedDriver(driver.path)
    assert connect.status(reopened)['Knowledge'] == 2
    with reopened.session() as session:
        # Exercise the real fulltext procedure, without accepting fallback.
        with patch('wisdom.traverse._keyword_fallback', side_effect=AssertionError('unexpected fallback')):
            assert full_text_search(session, 'graph')[0]['id'] == 'k1'
        assert _keyword_fallback(session, "agent's", 5)[0]['id'] == 'k1'
        assert answer_question(session, 'graph')['nodes']
        assert 'Knowledge' in render_report(session)
        assert len(json.loads(export_json(session, tmp_path).read_text())['nodes']) == 2
        assert 'Graph memory' in export_cypher(session, tmp_path).read_text()
        assert (export_obsidian(session, tmp_path) / 'index.md').exists()
    reopened.close()


def test_reflection_promotes_real_graph(driver):
    with driver.session() as session:
        merge_nodes(session, [
            dict(id='a', label='Recurring pattern', tier='knowledge', project='a'),
            dict(id='b', label='Recurring pattern', tier='knowledge', project='b'),
            dict(id='failure', label='Unsafe retry', tier='experience', outcome='FAILED', source_count=5),
        ])
        stats = run_reflect(session)
        assert stats['experience_promoted'] == 1
        assert stats['failure_insight_promoted'] == 1
        assert stats['wisdom_candidates'] >= 1
        candidate = stats['wisdom_candidates_data'][0]
        write_wisdom(session, [dict(id='w1', label='Safe retry', principle='Make retries idempotent',
                                    insight_id=candidate['id'], is_antipattern=True)])
        assert session.run('MATCH (:Insight)-[:CRYSTALLIZES_INTO]->(:Wisdom) RETURN count(*) AS c').single()['c'] == 1
    assert connect.status(driver)['Wisdom'] == 1


def test_missing_node_returns_none_instead_of_cursor_error(driver):
    from wisdom.traverse import explain_node
    with driver.session() as session:
        assert session.run("MATCH (n:Knowledge {id: 'missing'}) RETURN n").single() is None
        assert 'error' in explain_node(session, 'missing')


def test_exception_releases_store(driver):
    with pytest.raises(ValueError):
        with driver.session() as session:
            session.run("CREATE (:Knowledge {id: 'survives'})")
            raise ValueError('caller failed after autocommit')
    other = EmbeddedDriver(driver.path)
    assert connect.status(other)['Knowledge'] == 1
    other.close()


def test_second_process_cannot_open_active_writer(driver):
    with driver.session():
        result = subprocess.run(
            [sys.executable, '-c', 'import relate, sys; relate.connect(sys.argv[1])', driver.path],
            capture_output=True, text=True, timeout=15,
        )
    assert result.returncode != 0
    assert 'locked' in result.stderr.lower()
    assert connect.status(driver)['Knowledge'] == 0


def test_corrupt_config_does_not_silently_select_empty_graph(tmp_path, monkeypatch):
    path = tmp_path / 'config.json'
    path.write_text('{broken')
    monkeypatch.setattr(connect, '_CONFIG_PATH', path)
    with pytest.raises(ValueError, match='Repair the saved configuration'):
        connect.get_driver()


def test_default_and_legacy_config_routing(tmp_path, monkeypatch):
    monkeypatch.setattr(connect, '_CONFIG_PATH', tmp_path / 'config.json')
    assert connect.backend_name(connect._load_config()) == 'relate'
    connect._save_config({'neo4j_uri': 'neo4j+s://example.databases.neo4j.io', 'neo4j_user': 'neo4j'})
    monkeypatch.setenv('WISDOM_NEO4J_PASSWORD', 'test-password')
    remote = MagicMock()
    with patch('neo4j.GraphDatabase.driver', return_value=remote) as factory:
        assert connect.get_driver() is remote
        factory.assert_called_once_with('neo4j+s://example.databases.neo4j.io', auth=('neo4j', 'test-password'))
    connect.save_embedded(str(tmp_path / 'local.rl'))
    local = connect.get_driver()
    assert local.backend == 'relate'
    local.close()
    with patch('wisdom.connect._write_env_password'):
        connect.save_connection('neo4j+s://example.databases.neo4j.io', 'neo4j', 'secret')
    assert connect.backend_name(connect._load_config()) == 'neo4j'


def test_quickstart_without_docker(tmp_path, monkeypatch):
    from wisdom.__main__ import _run_quickstart
    monkeypatch.setattr(connect, '_CONFIG_PATH', tmp_path / 'config.json')
    monkeypatch.setattr('sys.argv', ['wisdom', 'quickstart', '--path', str(tmp_path / 'quick.rl'), '--host', 'none'])
    with patch('wisdom.local.up', side_effect=AssertionError('Docker invoked')):
        _run_quickstart()
    assert (tmp_path / 'quick.rl').exists()


def test_mcp_remember_and_query_real_engine(tmp_path, monkeypatch):
    from wisdom import mcp
    monkeypatch.setattr(connect, '_CONFIG_PATH', tmp_path / 'config.json')
    connect.save_embedded(str(tmp_path / 'mcp.rl'))
    result = mcp._handle_remember({'label': 'Embedded memory', 'content': 'No Docker needed'})
    assert not result.is_error
    result = mcp._handle_query({'cypher': 'MATCH (n:Knowledge) RETURN n.label AS label'})
    assert not result.is_error
    assert 'Embedded memory' in result.text
