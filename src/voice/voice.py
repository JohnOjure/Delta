"""Voice Activation for Delta.

Listens for wake word "Hey Delta" and transcribes following speech.
Uses SpeechRecognition library for both wake word and transcription.
"""

import asyncio
from typing import Callable, Optional
from threading import Thread
import queue

try:
    import speech_recognition as sr
    SPEECH_AVAILABLE = True
except ImportError:
    SPEECH_AVAILABLE = False


class VoiceListener:
    """Listens for voice commands to invoke Delta.
    
    Uses a simple keyword spotting approach for wake word detection.
    Falls back to no-op if speech_recognition is not available.
    """
    
    WAKE_WORDS = ["hey delta", "delta", "hey agent"]
    
    def __init__(self, callback: Callable, language: str = "en-US"):
        """Initialize voice listener.
        
        Args:
            callback: Async function to call with transcribed text
            language: Language code for speech recognition
        """
        self.callback = callback
        self.language = language
        self.running = False
        self._recognizer = None
        self._microphone = None
        self._loop = None
        self._command_queue = queue.Queue()
    
    async def start(self):
        """Start listening for voice commands."""
        if not SPEECH_AVAILABLE:
            print("Voice listener unavailable: speech_recognition not installed")
            print("Install with: pip install SpeechRecognition pyaudio")
            # Keep running but do nothing
            while True:
                await asyncio.sleep(3600)
            return
        
        self.running = True
        self._loop = asyncio.get_event_loop()
        self._recognizer = sr.Recognizer()
        
        # Adjust for ambient noise
        try:
            self._microphone = sr.Microphone()
            with self._microphone as source:
                print("Calibrating microphone for ambient noise...")
                self._recognizer.adjust_for_ambient_noise(source, duration=1)
        except Exception as e:
            print(f"Microphone error: {e}")
            print("Voice activation disabled.")
            while True:
                await asyncio.sleep(3600)
            return
        
        print("Voice listener active. Say 'Hey Delta' to activate.")
        
        # Start listening thread
        listen_thread = Thread(target=self._listen_loop, daemon=True)
        listen_thread.start()
        
        # Process commands from queue
        while self.running:
            try:
                # Non-blocking check for commands
                try:
                    command = self._command_queue.get_nowait()
                    if command and self.callback:
                        await self.callback(command)
                except queue.Empty:
                    pass
                
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
    
    async def stop(self):
        """Stop listening for voice commands."""
        self.running = False
    
    def _listen_loop(self):
        """Background thread for continuous listening."""
        while self.running:
            try:
                with self._microphone as source:
                    # Listen for audio
                    audio = self._recognizer.listen(source, timeout=5, phrase_time_limit=10)
                
                # Try to recognize
                try:
                    text = self._recognizer.recognize_google(audio, language=self.language)
                    text_lower = text.lower()
                    
                    # Check for wake word
                    wake_detected = False
                    remaining_text = text
                    
                    for wake_word in self.WAKE_WORDS:
                        if wake_word in text_lower:
                            wake_detected = True
                            # Extract command after wake word
                            idx = text_lower.find(wake_word)
                            remaining_text = text[idx + len(wake_word):].strip()
                            break
                    
                    if wake_detected:
                        if remaining_text:
                            # Wake word with command in same utterance
                            print(f"Voice command: {remaining_text}")
                            self._command_queue.put(remaining_text)
                        else:
                            # Just wake word - wait for command
                            print("Listening for command...")
                            try:
                                with self._microphone as source:
                                    command_audio = self._recognizer.listen(source, timeout=5, phrase_time_limit=15)
                                command_text = self._recognizer.recognize_google(command_audio, language=self.language)
                                print(f"Voice command: {command_text}")
                                self._command_queue.put(command_text)
                            except sr.WaitTimeoutError:
                                print("No command heard after wake word.")
                            except sr.UnknownValueError:
                                print("Could not understand command.")
                
                except sr.UnknownValueError:
                    # Speech not recognized - this is normal
                    pass
                except sr.RequestError as e:
                    print(f"Speech recognition error: {e}")
                    
            except sr.WaitTimeoutError:
                # No speech detected - continue listening
                pass
            except Exception as e:
                if self.running:
                    print(f"Voice listener error: {e}")
                    asyncio.run(asyncio.sleep(1))


async def _test_callback(text: str):
    """Test callback for debugging."""
    print(f"Received command: {text}")


if __name__ == "__main__":
    # Test the voice listener
    async def main():
        listener = VoiceListener(_test_callback)
        print("Starting voice listener...")
        await listener.start()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
