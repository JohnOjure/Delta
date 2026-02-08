"""System Tray Icon for Delta.

Shows Delta in the system tray with status and quick actions.
Uses pystray for cross-platform tray support.
"""

import asyncio
from typing import Optional
from threading import Thread
from pathlib import Path

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False


class DeltaTray:
    """System tray icon for Delta.
    
    Provides quick access to Delta functionality from the system tray.
    """
    
    def __init__(self):
        self.icon = None
        self.running = False
        self._loop = None
    
    def start(self):
        """Start the system tray icon (blocking)."""
        if not TRAY_AVAILABLE:
            print("System tray unavailable: pystray not installed")
            print("Install with: pip install pystray Pillow")
            return
        
        self.running = True
        
        # Create icon image
        image = self._create_icon()
        
        # Create menu
        menu = pystray.Menu(
            pystray.MenuItem("Delta Agent", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Ask Delta...", self._on_ask),
            pystray.MenuItem("Open Shell", self._on_shell),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Status", self._on_status),
            pystray.MenuItem("View Logs", self._on_logs),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Start Daemon", self._on_start),
            pystray.MenuItem("Stop Daemon", self._on_stop),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit)
        )
        
        # Create and run icon
        self.icon = pystray.Icon("delta", image, "Delta Agent", menu)
        
        print("System tray icon active.")
        self.icon.run()
    
    def stop(self):
        """Stop the system tray icon."""
        self.running = False
        if self.icon:
            self.icon.stop()
    
    def _create_icon(self) -> "Image":
        """Create the Delta icon image."""
        # Create a simple delta symbol icon
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Draw a triangle (delta symbol)
        points = [
            (size // 2, 8),      # Top
            (8, size - 8),       # Bottom left
            (size - 8, size - 8) # Bottom right
        ]
        draw.polygon(points, fill=(100, 149, 237))  # Cornflower blue
        
        # Draw inner triangle (hollow effect)
        inner_points = [
            (size // 2, 20),
            (18, size - 18),
            (size - 18, size - 18)
        ]
        draw.polygon(inner_points, fill=(30, 30, 30))
        
        return image
    
    def _on_ask(self, icon, item):
        """Handle Ask Delta menu item."""
        import subprocess
        # Open a terminal with delta shell
        try:
            subprocess.Popen(["gnome-terminal", "--", "delta", "shell"])
        except:
            try:
                subprocess.Popen(["xterm", "-e", "delta", "shell"])
            except:
                print("Could not open terminal. Run: delta shell")
    
    def _on_shell(self, icon, item):
        """Handle Open Shell menu item."""
        self._on_ask(icon, item)
    
    def _on_status(self, icon, item):
        """Handle Status menu item."""
        from src.daemon.manager import ServiceManager
        manager = ServiceManager()
        status = manager.status()
        
        if status.get("status") == "stopped":
            self.icon.notify("Delta is not running", "Status")
        else:
            uptime = status.get("uptime", "unknown")
            self.icon.notify(f"Running\nUptime: {uptime}", "Delta Status")
    
    def _on_logs(self, icon, item):
        """Handle View Logs menu item."""
        import subprocess
        log_file = Path.home() / ".delta" / "delta.log"
        try:
            subprocess.Popen(["xdg-open", str(log_file)])
        except:
            print(f"Open log file: {log_file}")
    
    def _on_start(self, icon, item):
        """Handle Start Daemon menu item."""
        from src.daemon.manager import ServiceManager
        manager = ServiceManager()
        if manager.start():
            self.icon.notify("Delta daemon started", "Delta")
        else:
            self.icon.notify("Failed to start daemon", "Delta")
    
    def _on_stop(self, icon, item):
        """Handle Stop Daemon menu item."""
        from src.daemon.manager import ServiceManager
        manager = ServiceManager()
        if manager.stop():
            self.icon.notify("Delta daemon stopped", "Delta")
    
    def _on_quit(self, icon, item):
        """Handle Quit menu item."""
        self.stop()


def run_tray():
    """Run the system tray icon."""
    tray = DeltaTray()
    tray.start()


if __name__ == "__main__":
    run_tray()
