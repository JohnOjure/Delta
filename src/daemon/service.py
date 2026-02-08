"""Delta Service - Main daemon that runs Delta as a background service.

This service manages all Delta subsystems:
- Ghost Mode (proactive monitoring)
- Hotkey listener (global shortcuts)
- Voice listener (wake word detection)
- IPC server (CLI communication)
"""

import asyncio
import signal
import os
import sys
import json
import socket
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime

from src.config import get_config
from src.adapters.desktop import DesktopAdapter
from src.core.agent import Agent
from src.core.gemini_client import GeminiClient
from src.core.memory import Memory
from src.extensions.registry import ExtensionRegistry
from src.core.ghost import GhostMode


class DeltaService:
    """Main Delta daemon service.
    
    Runs as a background process and manages all subsystems.
    Communicates with CLI via Unix socket IPC.
    """
    
    def __init__(self):
        self.config = get_config()
        self.running = False
        self._agent: Optional[Agent] = None
        self._ghost: Optional[GhostMode] = None
        self._ipc_server = None
        self._hotkey_task = None
        self._voice_task = None
        
        # Paths
        self.data_dir = Path.home() / ".delta"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.pid_file = self.data_dir / "delta.pid"
        self.socket_path = self.data_dir / "delta.sock"
        self.log_file = self.data_dir / "delta.log"
        
        # Callbacks
        self._on_message: Optional[Callable] = None
    
    async def initialize(self) -> bool:
        """Initialize all components."""
        try:
            if not self.config.api.gemini_api_key:
                self._log("ERROR: GEMINI_API_KEY not configured")
                return False
            
            # Initialize adapter
            adapter = DesktopAdapter(
                api_key=self.config.api.gemini_api_key,
                data_directory=self.config.paths.data_dir
            )
            await adapter.initialize()
            
            # Initialize agent
            gemini = GeminiClient(self.config.api.gemini_api_key)
            registry = ExtensionRegistry(self.config.paths.extensions_db)
            memory = Memory(self.config.paths.data_dir / "memory.db")
            
            self._agent = Agent(adapter, gemini, registry, memory=memory)
            
            # Initialize Ghost Mode
            self._ghost = GhostMode(self._agent, interval=60)
            
            self._log("Delta service initialized successfully")
            return True
            
        except Exception as e:
            self._log(f"ERROR: Failed to initialize: {e}")
            return False
    
    async def start(self):
        """Start the daemon service."""
        if self.running:
            return
        
        self.running = True
        self._write_pid()
        
        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
        
        self._log("Delta service starting...")
        
        # Start subsystems
        tasks = []
        
        # Start Ghost Mode
        if self._ghost:
            await self._ghost.start()
        
        # Start IPC server
        tasks.append(asyncio.create_task(self._run_ipc_server()))
        
        # Start hotkey listener (if available)
        try:
            from src.hotkey.hotkey import HotkeyListener
            hotkey = HotkeyListener(self._on_hotkey)
            self._hotkey_task = asyncio.create_task(hotkey.start())
            tasks.append(self._hotkey_task)
        except ImportError:
            self._log("Hotkey listener not available (pynput not installed)")
        
        # Start voice listener (if available)
        try:
            from src.voice.voice import VoiceListener
            voice = VoiceListener(self._on_voice)
            self._voice_task = asyncio.create_task(voice.start())
            tasks.append(self._voice_task)
        except ImportError:
            self._log("Voice listener not available (speech_recognition not installed)")
        
        self._log("Delta service started. Listening for commands...")
        
        # Wait for all tasks
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
    
    async def stop(self):
        """Stop the daemon service."""
        if not self.running:
            return
        
        self._log("Delta service stopping...")
        self.running = False
        
        # Stop subsystems
        if self._ghost:
            await self._ghost.stop()
        
        # Cleanup
        self._remove_pid()
        if self.socket_path.exists():
            self.socket_path.unlink()
        
        self._log("Delta service stopped.")
    
    async def run_goal(self, goal: str) -> dict:
        """Run a goal through the agent."""
        if not self._agent:
            return {"success": False, "error": "Agent not initialized"}
        
        try:
            result = await self._agent.run(goal)
            return {
                "success": result.success,
                "message": result.message,
                "response": result.response,
                "steps": result.steps_taken,
                "extensions_created": result.extensions_created
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _run_ipc_server(self):
        """Run Unix socket IPC server for CLI communication."""
        # Remove old socket if exists
        if self.socket_path.exists():
            self.socket_path.unlink()
        
        server = await asyncio.start_unix_server(
            self._handle_ipc_client,
            path=str(self.socket_path)
        )
        
        # Set socket permissions
        os.chmod(self.socket_path, 0o600)
        
        async with server:
            await server.serve_forever()
    
    async def _handle_ipc_client(self, reader, writer):
        """Handle IPC client connection."""
        try:
            data = await reader.read(4096)
            if not data:
                return
            
            request = json.loads(data.decode())
            command = request.get("command", "")
            
            if command == "status":
                response = {
                    "status": "running",
                    "ghost_mode": self._ghost.running if self._ghost else False,
                    "uptime": self._get_uptime()
                }
            elif command == "goal":
                goal = request.get("goal", "")
                response = await self.run_goal(goal)
            elif command == "stop":
                response = {"status": "stopping"}
                asyncio.create_task(self.stop())
            else:
                response = {"error": f"Unknown command: {command}"}
            
            writer.write(json.dumps(response).encode())
            await writer.drain()
            
        except Exception as e:
            writer.write(json.dumps({"error": str(e)}).encode())
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def _on_hotkey(self, hotkey: str):
        """Handle hotkey press."""
        self._log(f"Hotkey pressed: {hotkey}")
        # For now, show notification. Could open quick input dialog.
        if self._on_message:
            await self._on_message("Delta activated via hotkey")
    
    async def _on_voice(self, text: str):
        """Handle voice command."""
        self._log(f"Voice command: {text}")
        if text:
            result = await self.run_goal(text)
            if self._on_message:
                await self._on_message(result.get("response", result.get("message", "")))
    
    def _write_pid(self):
        """Write PID file."""
        self.pid_file.write_text(str(os.getpid()))
    
    def _remove_pid(self):
        """Remove PID file."""
        if self.pid_file.exists():
            self.pid_file.unlink()
    
    def _get_uptime(self) -> str:
        """Get service uptime."""
        if not self.pid_file.exists():
            return "unknown"
        
        try:
            start_time = self.pid_file.stat().st_mtime
            uptime = datetime.now().timestamp() - start_time
            hours, remainder = divmod(int(uptime), 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours}h {minutes}m {seconds}s"
        except:
            return "unknown"
    
    def _log(self, message: str):
        """Log message to file and stdout."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        print(log_line)
        
        with open(self.log_file, "a") as f:
            f.write(log_line + "\n")


async def run_daemon():
    """Entry point for running Delta as a daemon."""
    service = DeltaService()
    
    if not await service.initialize():
        sys.exit(1)
    
    await service.start()


if __name__ == "__main__":
    asyncio.run(run_daemon())
