"""Tests for the Delta daemon service."""

import asyncio
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.daemon.service import DeltaService
from src.daemon.manager import ServiceManager


class TestServiceManager:
    """Tests for ServiceManager."""
    
    def test_init(self):
        """Test ServiceManager initialization."""
        manager = ServiceManager()
        assert manager.data_dir == Path.home() / ".delta"
        assert manager.pid_file == Path.home() / ".delta" / "delta.pid"
        assert manager.socket_path == Path.home() / ".delta" / "delta.sock"
    
    def test_is_running_no_pid_file(self):
        """Test is_running returns False when no PID file exists."""
        manager = ServiceManager()
        
        # Temporarily move PID file if it exists
        if manager.pid_file.exists():
            backup = manager.pid_file.read_text()
            manager.pid_file.unlink()
            try:
                assert manager.is_running() == False
            finally:
                manager.pid_file.write_text(backup)
        else:
            assert manager.is_running() == False
    
    def test_get_pid_not_running(self):
        """Test get_pid returns None when not running."""
        manager = ServiceManager()
        
        with patch.object(manager, 'is_running', return_value=False):
            assert manager.get_pid() is None
    
    def test_status_stopped(self):
        """Test status returns stopped when not running."""
        manager = ServiceManager()
        
        with patch.object(manager, 'is_running', return_value=False):
            status = manager.status()
            assert status == {"status": "stopped"}
    
    def test_send_goal_not_running(self):
        """Test send_goal returns error when daemon not running."""
        manager = ServiceManager()
        
        with patch.object(manager, 'is_running', return_value=False):
            result = manager.send_goal("test goal")
            assert "error" in result
            assert "not running" in result["error"].lower()


class TestDeltaService:
    """Tests for DeltaService."""
    
    def test_init(self):
        """Test DeltaService initialization."""
        service = DeltaService()
        
        assert service.running == False
        assert service._agent is None
        assert service._ghost is None
        assert service.data_dir == Path.home() / ".delta"
    
    def test_paths_setup(self):
        """Test that service sets up correct paths."""
        service = DeltaService()
        
        assert service.pid_file == service.data_dir / "delta.pid"
        assert service.socket_path == service.data_dir / "delta.sock"
        assert service.log_file == service.data_dir / "delta.log"
    
    @pytest.mark.asyncio
    async def test_initialize_no_api_key(self):
        """Test initialize fails without API key."""
        service = DeltaService()
        
        with patch.object(service.config.api, 'gemini_api_key', None):
            result = await service.initialize()
            assert result == False
    
    @pytest.mark.asyncio
    async def test_run_goal_not_initialized(self):
        """Test run_goal returns error when not initialized."""
        service = DeltaService()
        service._agent = None
        
        result = await service.run_goal("test goal")
        assert result["success"] == False
        assert "not initialized" in result["error"].lower()
    
    def test_log_writes_to_file(self):
        """Test that _log writes to log file."""
        service = DeltaService()
        
        # Use a temp directory for testing
        with tempfile.TemporaryDirectory() as tmpdir:
            service.log_file = Path(tmpdir) / "test.log"
            service._log("Test message")
            
            assert service.log_file.exists()
            content = service.log_file.read_text()
            assert "Test message" in content


class TestDaemonIntegration:
    """Integration tests for daemon functionality."""
    
    def test_data_directory_created(self):
        """Test that data directory is created on init."""
        service = DeltaService()
        assert service.data_dir.exists()
    
    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """Test stop is safe to call when not running."""
        service = DeltaService()
        service.running = False
        
        # Should not raise
        await service.stop()
