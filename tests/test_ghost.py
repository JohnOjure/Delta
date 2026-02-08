"""Tests for the enhanced Ghost Mode."""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.core.ghost import GhostMode


class TestGhostMode:
    """Tests for enhanced Ghost Mode."""
    
    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent."""
        agent = MagicMock()
        agent._gemini = MagicMock()
        agent._gemini.analyze_system_health = AsyncMock(return_value={"alert_needed": False})
        agent._on_status = AsyncMock()
        return agent
    
    def test_init(self, mock_agent):
        """Test GhostMode initialization."""
        ghost = GhostMode(mock_agent)
        
        assert ghost.agent == mock_agent
        assert ghost.interval == 60
        assert ghost.running == False
        assert len(ghost.monitored_paths) > 0
        assert ghost._event_history == []
    
    def test_init_custom_interval(self, mock_agent):
        """Test GhostMode with custom interval."""
        ghost = GhostMode(mock_agent, interval=30)
        
        assert ghost.interval == 30
    
    def test_monitored_paths(self, mock_agent):
        """Test monitored paths are set."""
        ghost = GhostMode(mock_agent)
        
        assert Path.home() / "Downloads" in ghost.monitored_paths
        assert Path.home() / "Documents" in ghost.monitored_paths
    
    @pytest.mark.asyncio
    async def test_start_sets_running(self, mock_agent):
        """Test start sets running flag."""
        ghost = GhostMode(mock_agent)
        
        # Start in background, then immediately stop
        await ghost.start()
        assert ghost.running == True
        
        await ghost.stop()
        assert ghost.running == False
    
    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, mock_agent):
        """Test stop is safe when not started."""
        ghost = GhostMode(mock_agent)
        ghost.running = False
        
        # Should not raise
        await ghost.stop()
    
    def test_add_to_history(self, mock_agent):
        """Test event history management."""
        ghost = GhostMode(mock_agent)
        
        # Add an event
        event = {"type": "test", "data": "test data"}
        ghost._add_to_history(event)
        
        assert len(ghost._event_history) == 1
        assert ghost._event_history[0] == event
    
    def test_add_to_history_max_limit(self, mock_agent):
        """Test event history respects max limit."""
        ghost = GhostMode(mock_agent)
        ghost._max_history = 5
        
        # Add more events than the limit
        for i in range(10):
            ghost._add_to_history({"id": i})
        
        assert len(ghost._event_history) == 5
        # Should keep the most recent
        assert ghost._event_history[0]["id"] == 5
        assert ghost._event_history[-1]["id"] == 9
    
    def test_get_recent_events(self, mock_agent):
        """Test getting recent events."""
        ghost = GhostMode(mock_agent)
        
        # Add some events
        ghost._add_to_history({"type": "file_event", "name": "test1"})
        ghost._add_to_history({"type": "system_stats", "cpu": 50})
        ghost._add_to_history({"type": "file_event", "name": "test2"})
        
        # Get all events
        events = ghost.get_recent_events()
        assert len(events) == 3
        
        # Get filtered events
        file_events = ghost.get_recent_events(event_type="file_event")
        assert len(file_events) == 2
    
    def test_check_local_anomalies_high_cpu(self, mock_agent):
        """Test local anomaly detection for high CPU."""
        ghost = GhostMode(mock_agent)
        
        stats = {
            "cpu_percent": 95,
            "memory_percent": 50,
            "disk_usage": 50
        }
        
        alerts = ghost._check_local_anomalies(stats)
        assert len(alerts) == 1
        assert "CPU" in alerts[0]
    
    def test_check_local_anomalies_high_memory(self, mock_agent):
        """Test local anomaly detection for high memory."""
        ghost = GhostMode(mock_agent)
        
        stats = {
            "cpu_percent": 50,
            "memory_percent": 95,
            "disk_usage": 50
        }
        
        alerts = ghost._check_local_anomalies(stats)
        assert len(alerts) == 1
        assert "memory" in alerts[0].lower()
    
    def test_check_local_anomalies_low_disk(self, mock_agent):
        """Test local anomaly detection for low disk space."""
        ghost = GhostMode(mock_agent)
        
        stats = {
            "cpu_percent": 50,
            "memory_percent": 50,
            "disk_usage": 95
        }
        
        alerts = ghost._check_local_anomalies(stats)
        assert len(alerts) == 1
        assert "disk" in alerts[0].lower()
    
    def test_check_local_anomalies_all_normal(self, mock_agent):
        """Test no alerts when everything is normal."""
        ghost = GhostMode(mock_agent)
        
        stats = {
            "cpu_percent": 30,
            "memory_percent": 40,
            "disk_usage": 50
        }
        
        alerts = ghost._check_local_anomalies(stats)
        assert len(alerts) == 0
    
    def test_check_local_anomalies_multiple(self, mock_agent):
        """Test multiple anomalies detected."""
        ghost = GhostMode(mock_agent)
        
        stats = {
            "cpu_percent": 95,
            "memory_percent": 95,
            "disk_usage": 95
        }
        
        alerts = ghost._check_local_anomalies(stats)
        assert len(alerts) == 3


class TestFileMonitorHandler:
    """Tests for file monitoring functionality."""
    
    def test_watchdog_import_handling(self):
        """Test that missing watchdog is handled gracefully."""
        from src.core.ghost import WATCHDOG_AVAILABLE
        # Just verify the constant exists
        assert isinstance(WATCHDOG_AVAILABLE, bool)
