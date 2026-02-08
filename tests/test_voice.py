"""Tests for voice activation."""

import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.voice.voice import VoiceListener


class TestVoiceListener:
    """Tests for VoiceListener."""
    
    def test_init(self):
        """Test VoiceListener initialization."""
        callback = AsyncMock()
        listener = VoiceListener(callback)
        
        assert listener.callback == callback
        assert listener.language == "en-US"
        assert listener.running == False
        assert "hey delta" in listener.WAKE_WORDS
    
    def test_init_custom_language(self):
        """Test VoiceListener with custom language."""
        callback = AsyncMock()
        listener = VoiceListener(callback, language="de-DE")
        
        assert listener.language == "de-DE"
    
    def test_wake_words(self):
        """Test wake words are defined."""
        callback = AsyncMock()
        listener = VoiceListener(callback)
        
        assert len(listener.WAKE_WORDS) > 0
        assert "delta" in listener.WAKE_WORDS
    
    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """Test stop is safe when not running."""
        callback = AsyncMock()
        listener = VoiceListener(callback)
        listener.running = False
        
        # Should not raise
        await listener.stop()
        assert listener.running == False


class TestVoiceIntegration:
    """Integration tests for voice functionality."""
    
    def test_speech_recognition_import(self):
        """Test that missing speech_recognition is handled gracefully."""
        # The module should import even without speech_recognition
        from src.voice.voice import SPEECH_AVAILABLE
        # Just verify the constant exists
        assert isinstance(SPEECH_AVAILABLE, bool)
