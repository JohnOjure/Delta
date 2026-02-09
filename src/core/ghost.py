import asyncio
import psutil
import time
from pathlib import Path
from typing import Callable, Optional, List
from datetime import datetime

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False


class FileMonitorHandler(FileSystemEventHandler):
    """Handles file system events for Ghost Mode."""
    
    def __init__(self, callback):
        self.callback = callback
        self._last_event_time = 0
        self._debounce_seconds = 2
    
    def on_created(self, event):
        if event.is_directory:
            return
        
        # Debounce rapid events
        now = time.time()
        if now - self._last_event_time < self._debounce_seconds:
            return
        self._last_event_time = now
        
        # Notify about new file
        self.callback(event.src_path, "created")


class GhostMode:
    """Background monitoring and proactive action system.
    
    Ghost Mode runs in the background and:
    - Monitors system health (CPU, memory, disk)
    - Watches for new files in monitored directories
    - Detects anomalies and proposes solutions
    - Provides proactive suggestions based on patterns
    """
    
    def __init__(self, agent, interval: int = 60):
        self.agent = agent
        self.interval = interval
        self.running = False
        self._task = None
        self._file_observer = None
        
        # Monitored paths
        self.monitored_paths: List[Path] = [
            Path.home() / "Downloads",
            Path.home() / "Documents",
        ]
        
        # Event history for pattern detection
        self._event_history: List[dict] = []
        self._max_history = 100
    
    async def start(self):
        """Start the ghost loop and file monitoring."""
        self.running = True
        self._task = asyncio.create_task(self._loop())
        
        # Start file monitoring if watchdog available
        if WATCHDOG_AVAILABLE:
            self._start_file_monitor()
        
        print("👻 Ghost Mode activated (enhanced).")
    
    async def stop(self):
        """Stop the ghost loop and file monitoring."""
        self.running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        if self._file_observer:
            self._file_observer.stop()
            self._file_observer.join()
    
    def _start_file_monitor(self):
        """Start file system monitoring."""
        self._file_observer = Observer()
        handler = FileMonitorHandler(self._on_file_event)
        
        for path in self.monitored_paths:
            if path.exists():
                self._file_observer.schedule(handler, str(path), recursive=False)
                print(f"👻 Monitoring: {path}")
        
        self._file_observer.start()
    
    def _on_file_event(self, file_path: str, event_type: str):
        """Handle file system events."""
        path = Path(file_path)
        
        # Record event
        event = {
            "type": "file_event",
            "path": str(path),
            "name": path.name,
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat()
        }
        self._add_to_history(event)
        
        # Check if this is something we should proactively help with
        asyncio.create_task(self._analyze_file_event(path, event_type))
    
    async def _analyze_file_event(self, path: Path, event_type: str):
        """Analyze a file event and potentially offer help."""
        suffix = path.suffix.lower()
        name = path.name
        
        suggestions = []
        
        # Suggest actions based on file type
        if suffix == ".zip" or suffix == ".tar.gz":
            suggestions.append(f"New archive detected: {name}. Would you like me to extract it?")
        elif suffix in [".jpg", ".png", ".jpeg", ".gif"]:
            suggestions.append(f"New image: {name}. I can organize photos or resize if needed.")
        elif suffix == ".pdf":
            suggestions.append(f"New PDF: {name}. I can extract text or summarize it.")
        elif suffix in [".csv", ".xlsx"]:
            suggestions.append(f"New spreadsheet: {name}. I can analyze or visualize this data.")
        
        if suggestions:
            await self._propose_action(suggestions[0])
    
    async def _loop(self):
        """Main monitoring loop."""
        # Warmup
        await asyncio.sleep(5)
        
        cycle_count = 0
        optimization_interval = 10  # Run optimization every 10 cycles
        
        while self.running:
            try:
                cycle_count += 1
                
                # Gather system stats
                stats = {
                    "cpu_percent": psutil.cpu_percent(interval=1),
                    "memory_percent": psutil.virtual_memory().percent,
                    "disk_usage": psutil.disk_usage('/').percent,
                    "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Record stats
                self._add_to_history({
                    "type": "system_stats",
                    **stats
                })
                
                # Check for anomalies locally first
                alerts = self._check_local_anomalies(stats)
                
                if alerts:
                    for alert in alerts:
                        print(f"👻 {alert}")
                        await self._propose_action(alert)
                else:
                    # Ask Gemini for deeper analysis periodically
                    if hasattr(self.agent, '_gemini') and self.agent._gemini:
                        try:
                            analysis = await self.agent._gemini.analyze_system_health(stats)
                            
                            if analysis.get("alert_needed"):
                                msg = analysis.get("message", "System anomaly detected.")
                                severity = analysis.get("severity", "medium")
                                
                                print(f"👻 Ghost Alert ({severity}): {msg}")
                                await self._propose_action(
                                    f"Ghost Mode Alert ({severity}): {msg}"
                                )
                        except Exception as e:
                            pass  # Gemini analysis is optional
                
                # === AUTONOMOUS SELF-OPTIMIZATION ===
                if cycle_count % optimization_interval == 0:
                    await self._run_self_optimization()
                
                await asyncio.sleep(self.interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Ghost loop error: {e}")
                await asyncio.sleep(60)
    
    async def _run_self_optimization(self):
        """Autonomously check for optimization opportunities and fix them."""
        try:
            from .optimization import OptimizationEngine
            
            optimizer = OptimizationEngine()
            suggestions = optimizer.analyze_performance()
            
            if not suggestions:
                return  # No issues found
            
            print(f"👻 Self-Optimization: Found {len(suggestions)} improvement opportunities.")
            
            # Only auto-fix LOW severity issues without user approval
            low_severity = [s for s in suggestions if s.severity == "low"]
            high_severity = [s for s in suggestions if s.severity in ("medium", "high")]
            
            # Notify user about high-severity issues
            for s in high_severity:
                await self._propose_action(f"⚠️ Optimization needed: {s.suggested_action}")
            
            # Auto-execute low-severity optimizations
            if low_severity and hasattr(self.agent, 'run'):
                goal = "Perform these minor self-optimizations:\n"
                for s in low_severity:
                    goal += f"- {s.suggested_action}\n"
                
                print("👻 Auto-executing low-severity optimizations...")
                try:
                    result = await self.agent.run(goal)
                    if result.success:
                        print("👻 Self-optimization complete.")
                    else:
                        print(f"👻 Self-optimization failed: {result.message}")
                except Exception as e:
                    print(f"👻 Self-optimization error: {e}")
                    
        except ImportError:
            pass  # OptimizationEngine not available
        except Exception as e:
            print(f"👻 Self-optimization check failed: {e}")
    
    def _check_local_anomalies(self, stats: dict) -> List[str]:
        """Check for anomalies using local rules."""
        alerts = []
        
        # High CPU
        if stats["cpu_percent"] > 90:
            alerts.append(f"High CPU usage: {stats['cpu_percent']:.1f}%")
        
        # High memory
        if stats["memory_percent"] > 90:
            alerts.append(f"High memory usage: {stats['memory_percent']:.1f}%")
        
        # Low disk space
        if stats["disk_usage"] > 90:
            alerts.append(f"Disk space low: {stats['disk_usage']:.1f}% used")
        
        return alerts
    
    def _add_to_history(self, event: dict):
        """Add event to history with size limit."""
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
    
    def get_recent_events(self, event_type: str = None, limit: int = 10) -> List[dict]:
        """Get recent events, optionally filtered by type."""
        events = self._event_history
        if event_type:
            events = [e for e in events if e.get("type") == event_type]
        return events[-limit:]

    async def _propose_action(self, suggestion: str):
        """Propose an action to the user via the agent's web interface."""
        if hasattr(self.agent, '_on_status') and self.agent._on_status:
            await self.agent._on_status({
                "state": "waiting",
                "activity": "Ghost Mode",
                "details": suggestion
            })

