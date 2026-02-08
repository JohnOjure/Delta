"""Ghost Mode - Proactive autonomy loop."""

import asyncio
import psutil
import time
from pathlib import Path
from typing import Callable

class GhostMode:
    """Background monitoring and proactive action system."""
    
    def __init__(self, agent, interval: int = 60):
        self.agent = agent
        self.interval = interval
        self.running = False
        self._task = None
        self.monitored_paths = [Path.home() / "Downloads"]
    
    async def start(self):
        """Start the ghost loop."""
        self.running = True
        self._task = asyncio.create_task(self._loop())
        print("👻 Ghost Mode activated.")
    
    async def stop(self):
        """Stop the ghost loop."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                # Check system stats
                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.virtual_memory().percent
                
                if cpu > 80:
                    await self._propose_action(
                        f"Sir, CPU usage is critically high ({cpu}%). Shall I analyze running processes?"
                    )
                
                if mem > 90:
                    await self._propose_action(
                        f"Memory usage is critical ({mem}%). I recommend closing unused applications."
                    )
                
                # Check downloads (simplified)
                # In a real implementation, we'd track file diffs
                
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Ghost loop error: {e}")
                await asyncio.sleep(60)

    async def _propose_action(self, suggestion: str):
        """Propose an action to the user via the agent's web interface."""
        # This requires threading into the existing websocket broadcast if possible
        # Or using the agent's memory/status callbacks
        if self.agent._on_status:
            await self.agent._on_status({
                "state": "waiting",
                "activity": "Ghost Mode",
                "details": suggestion
            })
