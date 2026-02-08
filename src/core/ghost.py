import asyncio
import psutil
import time
from pathlib import Path
from typing import Callable
from datetime import datetime

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
        print("👻 Smart Ghost Mode activated.")
    
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
        # Warmup
        await asyncio.sleep(5)
        
        while self.running:
            try:
                # Gather system stats
                stats = {
                    "cpu_percent": psutil.cpu_percent(interval=1),
                    "memory_percent": psutil.virtual_memory().percent,
                    "disk_usage": psutil.disk_usage('/').percent,
                    "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Ask Gemini (Flash model) for analysis
                # We access the private _gemini client from agent - strictly speaking we should pass it in __init__
                # but for this refactor using agent._gemini is practical
                analysis = await self.agent._gemini.analyze_system_health(stats)
                
                if analysis.get("alert_needed"):
                    msg = analysis.get("message", "System anomaly detected.")
                    severity = analysis.get("severity", "medium")
                    
                    print(f"👻 Ghost Alert ({severity}): {msg}")
                    
                    await self._propose_action(
                        f"Ghost Mode Alert ({severity}): {msg}"
                    )
                
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Ghost loop error: {e}")
                await asyncio.sleep(60)

    async def _propose_action(self, suggestion: str):
        """Propose an action to the user via the agent's web interface."""
        if self.agent._on_status:
            await self.agent._on_status({
                "state": "waiting",
                "activity": "Ghost Mode",
                "details": suggestion
            })
