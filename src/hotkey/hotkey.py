"""Global Hotkey Listener for Delta.

Listens for global keyboard shortcuts to invoke Delta.
Default hotkey: Ctrl+Shift+D
"""

import asyncio
from typing import Callable, Optional
from threading import Thread

try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False


class HotkeyListener:
    """Listens for global hotkeys to invoke Delta.
    
    Uses pynput for cross-platform global keyboard hooks.
    Falls back to no-op if pynput is not available.
    """
    
    # Default hotkey: Ctrl+Shift+D
    DEFAULT_HOTKEY = {keyboard.Key.ctrl, keyboard.Key.shift, keyboard.KeyCode.from_char('d')} if PYNPUT_AVAILABLE else set()
    
    def __init__(self, callback: Callable, hotkey: set = None):
        """Initialize hotkey listener.
        
        Args:
            callback: Async function to call when hotkey is pressed
            hotkey: Set of keys that make up the hotkey
        """
        self.callback = callback
        self.hotkey = hotkey or self.DEFAULT_HOTKEY
        self.running = False
        self._listener = None
        self._current_keys = set()
        self._loop = None
    
    async def start(self):
        """Start listening for hotkeys."""
        if not PYNPUT_AVAILABLE:
            print("Hotkey listener unavailable: pynput not installed")
            print("Install with: pip install pynput")
            # Keep running but do nothing
            while True:
                await asyncio.sleep(3600)
            return
        
        self.running = True
        self._loop = asyncio.get_event_loop()
        
        # Run pynput listener in a thread (it blocks)
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self._listener.start()
        
        print(f"Hotkey listener active: Ctrl+Shift+D")
        
        # Keep alive until stopped
        while self.running:
            await asyncio.sleep(1)
        
        if self._listener:
            self._listener.stop()
    
    async def stop(self):
        """Stop listening for hotkeys."""
        self.running = False
        if self._listener:
            self._listener.stop()
    
    def _on_press(self, key):
        """Handle key press."""
        # Normalize key
        normalized = self._normalize_key(key)
        if normalized:
            self._current_keys.add(normalized)
        
        # Check if hotkey combination is pressed
        if self._check_hotkey():
            # Schedule callback on async loop
            if self._loop and self.callback:
                asyncio.run_coroutine_threadsafe(
                    self.callback("Ctrl+Shift+D"),
                    self._loop
                )
    
    def _on_release(self, key):
        """Handle key release."""
        normalized = self._normalize_key(key)
        if normalized:
            self._current_keys.discard(normalized)
    
    def _normalize_key(self, key):
        """Normalize key for comparison."""
        if not PYNPUT_AVAILABLE:
            return None
        
        # Handle special keys
        if hasattr(key, 'char') and key.char:
            return keyboard.KeyCode.from_char(key.char.lower())
        return key
    
    def _check_hotkey(self) -> bool:
        """Check if the hotkey combination is currently pressed."""
        if not PYNPUT_AVAILABLE:
            return False
        
        # Check for Ctrl+Shift+D
        has_ctrl = keyboard.Key.ctrl in self._current_keys or keyboard.Key.ctrl_l in self._current_keys or keyboard.Key.ctrl_r in self._current_keys
        has_shift = keyboard.Key.shift in self._current_keys or keyboard.Key.shift_l in self._current_keys or keyboard.Key.shift_r in self._current_keys
        has_d = any(
            (hasattr(k, 'char') and k.char and k.char.lower() == 'd')
            for k in self._current_keys
        ) or keyboard.KeyCode.from_char('d') in self._current_keys
        
        return has_ctrl and has_shift and has_d


async def _test_callback(hotkey: str):
    """Test callback for debugging."""
    print(f"Hotkey pressed: {hotkey}")


if __name__ == "__main__":
    # Test the hotkey listener
    async def main():
        listener = HotkeyListener(_test_callback)
        print("Press Ctrl+Shift+D to test...")
        await listener.start()
    
    asyncio.run(main())
