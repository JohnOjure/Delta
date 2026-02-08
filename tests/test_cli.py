"""Tests for the Delta CLI."""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from src.cli.cli import cli


class TestCLI:
    """Tests for Delta CLI commands."""
    
    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()
    
    def test_cli_version(self, runner):
        """Test --version flag."""
        result = runner.invoke(cli, ['--version'])
        assert result.exit_code == 0
        assert 'Delta' in result.output or '1.0.0' in result.output
    
    def test_cli_help(self, runner):
        """Test --help flag."""
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'Delta' in result.output
        assert 'Self-Extensible' in result.output
    
    def test_status_stopped(self, runner):
        """Test status command when daemon not running."""
        with patch('src.cli.cli.ServiceManager') as MockManager:
            mock_manager = MagicMock()
            mock_manager.status.return_value = {"status": "stopped"}
            MockManager.return_value = mock_manager
            
            result = runner.invoke(cli, ['status'])
            assert result.exit_code == 0
            assert 'stopped' in result.output.lower()
    
    def test_status_running(self, runner):
        """Test status command when daemon running."""
        with patch('src.cli.cli.ServiceManager') as MockManager:
            mock_manager = MagicMock()
            mock_manager.status.return_value = {
                "status": "running",
                "pid": 12345,
                "uptime": "1h 30m 0s"
            }
            MockManager.return_value = mock_manager
            
            result = runner.invoke(cli, ['status'])
            assert result.exit_code == 0
            assert 'running' in result.output.lower()
    
    def test_stop_not_running(self, runner):
        """Test stop command when daemon not running."""
        with patch('src.cli.cli.ServiceManager') as MockManager:
            mock_manager = MagicMock()
            mock_manager.stop.return_value = False
            MockManager.return_value = mock_manager
            
            result = runner.invoke(cli, ['stop'])
            # Should complete without error
            assert result.exit_code == 0
    
    def test_logs_command(self, runner):
        """Test logs command."""
        with patch('src.cli.cli.ServiceManager') as MockManager:
            mock_manager = MagicMock()
            MockManager.return_value = mock_manager
            
            result = runner.invoke(cli, ['logs'])
            assert result.exit_code == 0
            mock_manager.tail_logs.assert_called_once()
    
    def test_config_show(self, runner):
        """Test config --show command."""
        result = runner.invoke(cli, ['config', '--show'])
        assert result.exit_code == 0
    
    def test_ask_daemon_not_running(self, runner):
        """Test ask command when daemon not running."""
        with patch('src.cli.cli.ServiceManager') as MockManager:
            mock_manager = MagicMock()
            mock_manager.is_running.return_value = False
            MockManager.return_value = mock_manager
            
            # Mock the direct run to avoid actually running
            with patch('src.cli.cli._run_goal_direct') as mock_run:
                # Make it a proper async mock
                async def mock_async(*args, **kwargs):
                    pass
                mock_run.return_value = mock_async
                
                result = runner.invoke(cli, ['ask', 'hello'])
                # Will try to run directly
                assert 'not running' in result.output.lower() or result.exit_code == 0


class TestCLICommands:
    """Test individual CLI command structures."""
    
    def test_all_commands_exist(self):
        """Test all expected commands are registered."""
        commands = cli.commands.keys()
        expected = ['ask', 'start', 'stop', 'restart', 'status', 'logs', 'config', 'shell']
        
        for cmd in expected:
            assert cmd in commands, f"Missing command: {cmd}"
