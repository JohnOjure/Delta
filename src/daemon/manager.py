"""Service Manager - Controls Delta daemon lifecycle.

Provides start/stop/status/restart functionality for the Delta service.
"""

import os
import sys
import signal
import asyncio
import json
import socket
from pathlib import Path
from typing import Optional


class ServiceManager:
    """Manages Delta daemon service lifecycle."""
    
    def __init__(self):
        self.data_dir = Path.home() / ".delta"
        self.pid_file = self.data_dir / "delta.pid"
        self.socket_path = self.data_dir / "delta.sock"
        self.log_file = self.data_dir / "delta.log"
    
    def is_running(self) -> bool:
        """Check if the daemon is running."""
        if not self.pid_file.exists():
            return False
        
        try:
            pid = int(self.pid_file.read_text().strip())
            # Check if process exists
            os.kill(pid, 0)
            return True
        except (ValueError, OSError):
            # Process doesn't exist, clean up stale PID file
            self.pid_file.unlink(missing_ok=True)
            return False
    
    def get_pid(self) -> Optional[int]:
        """Get the daemon PID."""
        if not self.is_running():
            return None
        
        try:
            return int(self.pid_file.read_text().strip())
        except:
            return None
    
    def start(self, foreground: bool = False) -> bool:
        """Start the Delta daemon.
        
        Args:
            foreground: If True, run in foreground. If False, daemonize.
        
        Returns:
            True if started successfully.
        """
        if self.is_running():
            print("Delta daemon is already running.")
            return False
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        if foreground:
            # Run in foreground - import and run directly
            from src.daemon.service import run_daemon
            print("Starting Delta daemon in foreground...")
            asyncio.run(run_daemon())
            return True
        else:
            # Daemonize - fork and run in background
            return self._daemonize()
    
    def _daemonize(self) -> bool:
        """Fork and daemonize the process."""
        # First fork
        try:
            pid = os.fork()
            if pid > 0:
                # Parent - wait briefly then check if started
                import time
                time.sleep(1)
                if self.is_running():
                    print(f"Delta daemon started (PID: {self.get_pid()})")
                    return True
                else:
                    print("Failed to start Delta daemon. Check ~/.delta/delta.log")
                    return False
        except OSError as e:
            print(f"Fork failed: {e}")
            return False
        
        # Child - become session leader
        os.setsid()
        
        # Second fork
        try:
            pid = os.fork()
            if pid > 0:
                # Exit first child
                os._exit(0)
        except OSError as e:
            os._exit(1)
        
        # Redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        
        with open('/dev/null', 'r') as devnull:
            os.dup2(devnull.fileno(), sys.stdin.fileno())
        
        # Redirect stdout/stderr to log file
        log_fd = open(self.log_file, 'a')
        os.dup2(log_fd.fileno(), sys.stdout.fileno())
        os.dup2(log_fd.fileno(), sys.stderr.fileno())
        
        # Run the daemon
        from src.daemon.service import run_daemon
        asyncio.run(run_daemon())
        
        return True
    
    def stop(self) -> bool:
        """Stop the Delta daemon."""
        if not self.is_running():
            print("Delta daemon is not running.")
            return False
        
        pid = self.get_pid()
        if pid is None:
            return False
        
        try:
            # Send SIGTERM for graceful shutdown
            os.kill(pid, signal.SIGTERM)
            
            # Wait for process to stop
            import time
            for _ in range(10):
                time.sleep(0.5)
                if not self.is_running():
                    print("Delta daemon stopped.")
                    return True
            
            # Force kill if still running
            os.kill(pid, signal.SIGKILL)
            print("Delta daemon force stopped.")
            return True
            
        except OSError as e:
            print(f"Failed to stop daemon: {e}")
            return False
    
    def restart(self) -> bool:
        """Restart the Delta daemon."""
        self.stop()
        import time
        time.sleep(1)
        return self.start()
    
    def status(self) -> dict:
        """Get daemon status."""
        if not self.is_running():
            return {"status": "stopped"}
        
        # Try to get status via IPC
        try:
            response = self._send_command({"command": "status"})
            return response
        except:
            return {
                "status": "running",
                "pid": self.get_pid()
            }
    
    def send_goal(self, goal: str) -> dict:
        """Send a goal to the running daemon."""
        if not self.is_running():
            return {"error": "Daemon not running. Start with: delta start"}
        
        return self._send_command({"command": "goal", "goal": goal})
    
    def _send_command(self, command: dict) -> dict:
        """Send command to daemon via IPC socket."""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(str(self.socket_path))
            sock.sendall(json.dumps(command).encode())
            
            response = sock.recv(8192)
            return json.loads(response.decode())
        finally:
            sock.close()
    
    def tail_logs(self, lines: int = 50):
        """Display recent log entries."""
        if not self.log_file.exists():
            print("No logs found.")
            return
        
        with open(self.log_file, 'r') as f:
            all_lines = f.readlines()
            recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
            for line in recent:
                print(line, end='')
