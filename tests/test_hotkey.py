"""Tests for the hotkey listener."""

import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.hotkey.hotkey import HotkeyListener


class TestHotkeyListener:
    """Tests for HotkeyListener."""
    
    def test_init(self):
        """Test HotkeyListener initialization."""
        callback = AsyncMock()
        listener = HotkeyListener(callback)
        
        assert listener.callback == callback
        assert listener.running == False
        assert listener._listener is None
        assert listener._current_keys == set()
    
    def test_init_custom_hotkey(self):
        """Test HotkeyListener with custom hotkey."""
        callback = AsyncMock()
        custom_hotkey = {"test", "hotkey"}
        listener = HotkeyListener(callback, hotkey=custom_hotkey)
        
        assert listener.hotkey == custom_hotkey
    
    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """Test stop is safe when not running."""
        callback = AsyncMock()
        listener = HotkeyListener(callback)
        listener.running = False
        
        # Should not raise
        await listener.stop()
        assert listener.running == False


class TestHotkeyIntegration:
    """Integration tests for hotkey functionality."""
    
    def test_pynput_import_handling(self):
        """Test that missing pynput is handled gracefully."""
        from src.hotkey.hotkey import PYNPUT_AVAILABLE
        # Just verify the constant exists
        assert isinstance(PYNPUT_AVAILABLE, bool)
    
    def test_default_hotkey_exists(self):
        """Test default hotkey is defined."""
        from src.hotkey.hotkey import HotkeyListener
        # Default hotkey might be empty if pynput not available
        callback = AsyncMock()
        listener = HotkeyListener(callback)
        assert listener.hotkey is not None
