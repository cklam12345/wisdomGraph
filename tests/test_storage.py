"""MCP storage switching, rollback, and credential isolation."""
import json
from unittest.mock import MagicMock, patch

import pytest

from wisdom import connect, local
from wisdom.mcp import _handle_storage, _handle_remember, _handle_query


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setattr(connect, '_CONFIG_PATH', tmp_path / 'config.json')
    monkeypatch.setattr(local, 'PASSWORD_PATH', tmp_path / 'docker-password')
    connect._save_config({'backend': 'relate', 'graph_path': str(tmp_path / 'memory.rl'),
                          'neo4j_uri': 'neo4j+s://saved.example', 'neo4j_user': 'neo4j'})
    return tmp_path


def test_status_does_not_open_database_or_start_docker(config):
    with patch('wisdom.connect.get_driver') as driver, patch('wisdom.local.up') as up:
        result = _handle_storage({})
    assert not result.is_error
    assert 'Storage: relate' in result.text
    driver.assert_not_called()
    up.assert_not_called()


def test_mcp_switch_changes_next_call_and_preserves_old_graph(config, capsys):
    _handle_remember({'label': 'Original memory', 'content': 'Keep this'})
    result = _handle_storage({'action': 'switch', 'backend': 'relate', 'path': str(config / 'second.rl')})
    assert not result.is_error
    query = {'cypher': 'MATCH (n:Knowledge) RETURN n.label AS label'}
    assert 'Original memory' not in _handle_query(query).text
    assert not _handle_storage({'action': 'switch', 'backend': 'relate', 'path': str(config / 'memory.rl')}).is_error
    assert 'Original memory' in _handle_query(query).text
    assert capsys.readouterr().out == ''


def test_remote_switch_reuses_saved_uri_without_password_in_config(config, monkeypatch):
    monkeypatch.setenv('AURA_SECRET', 'not-for-output')
    driver = MagicMock()
    with patch('neo4j.GraphDatabase.driver', return_value=driver) as factory:
        result = _handle_storage({'action': 'switch', 'backend': 'aura', 'password_env': 'AURA_SECRET'})
    assert not result.is_error
    factory.assert_called_once_with('neo4j+s://saved.example', auth=('neo4j', 'not-for-output'))
    assert connect.backend_name(connect._load_config()) == 'neo4j'
    assert 'not-for-output' not in result.text + connect._CONFIG_PATH.read_text()
    driver.close.assert_called_once()


def test_failed_probe_keeps_old_selection_and_hides_credentials(config, monkeypatch, capsys):
    monkeypatch.setenv('AURA_SECRET', 'not-for-output')
    previous = connect._CONFIG_PATH.read_text()
    driver = MagicMock()
    driver.verify_connectivity.side_effect = RuntimeError('not-for-output')
    with patch('neo4j.GraphDatabase.driver', return_value=driver):
        result = _handle_storage({'action': 'switch', 'backend': 'neo4j', 'password_env': 'AURA_SECRET'})
    assert result.is_error
    assert connect._CONFIG_PATH.read_text() == previous
    captured = capsys.readouterr()
    assert 'not-for-output' not in result.text + captured.out + captured.err
    driver.close.assert_called_once()


def test_docker_switch_preserves_saved_remote_and_uses_local_password(config, capsys):
    local.PASSWORD_PATH.write_text('docker-secret')
    def start(**kwargs):
        print('progress including docker-secret')
    driver = MagicMock()
    with patch('wisdom.local.up', side_effect=start) as up, patch('neo4j.GraphDatabase.driver', return_value=driver) as factory:
        result = _handle_storage({'action': 'switch', 'backend': 'docker', 'engine': 'dozerdb'})
    assert not result.is_error
    up.assert_called_once_with(connect=False, engine='dozerdb')
    factory.assert_called_once_with(local.URI, auth=(local.USER, 'docker-secret'))
    cfg = connect._load_config()
    assert cfg['backend'] == 'docker'
    assert cfg['neo4j_uri'] == 'neo4j+s://saved.example'
    assert 'docker-secret' not in result.text + json.dumps(cfg) + capsys.readouterr().out


def test_docker_failure_preserves_selection(config):
    before = connect._CONFIG_PATH.read_text()
    with patch('wisdom.local.up', side_effect=SystemExit(1)):
        assert _handle_storage({'action': 'switch', 'backend': 'docker'}).is_error
    assert connect._CONFIG_PATH.read_text() == before


@pytest.mark.parametrize('args', [
    {'action': 'switch', 'backend': 'other'},
    {'action': 'switch', 'backend': 'neo4j', 'password': 'secret'},
    {'action': 'switch', 'backend': 'neo4j', 'uri': 'neo4j://user:secret@example'},
    {'action': 'switch', 'backend': 'docker', 'engine': 'other'},
    {'backend': 'docker'},
    {'action': 'switch', 'backend': 'relate', 'uri': 'neo4j://example'},
])
def test_invalid_switch_does_not_mutate_config(config, args):
    before = connect._CONFIG_PATH.read_text()
    assert _handle_storage(args).is_error
    assert connect._CONFIG_PATH.read_text() == before
