"""FastAPI backend for Delta Web UI.

Provides REST API and WebSocket endpoints for real-time agent interaction.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from src.adapters.desktop import DesktopAdapter
from src.core.agent import Agent
from src.core.gemini_client import GeminiClient
from src.extensions.registry import ExtensionRegistry
from src.config import get_config


# Models
class GoalRequest(BaseModel):
    goal: str


class ExtensionRequest(BaseModel):
    name: str
    version: Optional[str] = None


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass


# Create app
app = FastAPI(title="Delta Agent", version="1.0.0")
manager = ConnectionManager()

# State (initialized on startup)
_agent: Optional[Agent] = None
_adapter: Optional[DesktopAdapter] = None
_registry: Optional[ExtensionRegistry] = None


async def get_agent() -> Agent:
    global _agent, _adapter, _registry
    
    if _agent is None:
        config = get_config()
        
        if not config.api.gemini_api_key:
            raise HTTPException(500, "GEMINI_API_KEY not configured")
        
        _adapter = DesktopAdapter(
            api_key=config.api.gemini_api_key,
            data_directory=config.paths.data_dir
        )
        await _adapter.initialize()
        
        gemini = GeminiClient(config.api.gemini_api_key)
        _registry = ExtensionRegistry(config.paths.extensions_db)
        
        # Initialize persistent memory
        from src.core.memory import Memory
        memory = Memory(config.paths.data_dir / "memory.db")
        
        _agent = Agent(_adapter, gemini, _registry, memory=memory)
    
    return _agent


# Static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main UI."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return index_file.read_text()
    return """
    <html>
        <head><title>Delta Agent</title></head>
        <body>
            <h1>Delta Agent Web UI</h1>
            <p>Static files not found. Please check installation.</p>
        </body>
    </html>
    """


@app.post("/api/goal")
async def run_goal(request: GoalRequest):
    """Run a goal (non-streaming)."""
    agent = await get_agent()
    result = await agent.run(request.goal)
    
    return {
        "success": result.success,
        "message": result.message,
        "response": result.response,
        "steps": result.steps_taken,
        "extensions_created": result.extensions_created
    }


@app.get("/api/extensions")
async def list_extensions():
    """List all extensions."""
    global _registry
    if _registry is None:
        config = get_config()
        _registry = ExtensionRegistry(config.paths.extensions_db)
    
    extensions = await _registry.list_all()
    return [
        {
            "name": ext.metadata.name,
            "version": ext.metadata.version,
            "description": ext.metadata.description,
            "capabilities": ext.metadata.required_capabilities,
            "executions": ext.execution_count
        }
        for ext in extensions
    ]


@app.get("/api/extensions/{name}")
async def get_extension(name: str):
    """Get extension details."""
    global _registry
    if _registry is None:
        config = get_config()
        _registry = ExtensionRegistry(config.paths.extensions_db)
    
    ext = await _registry.get_by_name(name)
    if ext is None:
        raise HTTPException(404, f"Extension '{name}' not found")
    
    history = await _registry.get_version_history(name)
    
    return {
        "name": ext.metadata.name,
        "version": ext.metadata.version,
        "description": ext.metadata.description,
        "capabilities": ext.metadata.required_capabilities,
        "tags": ext.metadata.tags,
        "source_code": ext.source_code,
        "executions": ext.execution_count,
        "created_at": str(ext.created_at),
        "updated_at": str(ext.updated_at),
        "version_history": history
    }


@app.post("/api/extensions/{name}/rollback")
async def rollback_extension(name: str, request: ExtensionRequest):
    """Rollback an extension to a previous version."""
    if not request.version:
        raise HTTPException(400, "Version required")
    
    global _registry
    if _registry is None:
        config = get_config()
        _registry = ExtensionRegistry(config.paths.extensions_db)
    
    result = await _registry.rollback(name, request.version)
    if result is None:
        raise HTTPException(404, f"Version '{request.version}' not found")
    
    return {"success": True, "new_version": result.metadata.version}


@app.get("/api/stats")
async def get_stats():
    """Get system statistics."""
    global _registry
    if _registry is None:
        config = get_config()
        _registry = ExtensionRegistry(config.paths.extensions_db)
    
    registry_stats = await _registry.get_stats()
    
    # Try to get memory stats
    memory_stats = {}
    try:
        from src.core.memory import Memory
        config = get_config()
        memory = Memory(config.paths.memory_db)
        memory_stats = await memory.get_stats()
    except:
        pass
    
    # Try to get tracking stats
    tracking_stats = {}
    try:
        from src.core.tracking import UsageTracker
        config = get_config()
        tracker = UsageTracker(config.paths.data_dir / "tracking.db")
        tracking_stats = await tracker.get_summary()
    except:
        pass
    
    return {
        "registry": registry_stats,
        "memory": memory_stats,
        "tracking": tracking_stats
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time agent updates."""
    await manager.connect(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "goal":
                goal = message.get("goal", "")
                
                # Notify start
                await manager.broadcast({
                    "type": "status",
                    "status": "started",
                    "goal": goal,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                try:
                    # Create status callback for real-time thinking updates
                    async def on_status(status):
                        await manager.broadcast({
                            "type": "thinking",
                            "state": status.get("state", ""),
                            "activity": status.get("activity", ""),
                            "details": status.get("details", ""),
                            "iteration": status.get("iteration", 0),
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    
                    agent = await get_agent()
                    agent._on_status = on_status  # Attach callback
                    
                    # Run goal with real-time status updates
                    result = await agent.run(goal)
                    
                    await manager.broadcast({
                        "type": "result",
                        "success": result.success,
                        "message": result.message,
                        "response": result.response,
                        "steps": result.steps_taken,
                        "extensions_created": result.extensions_created,
                        "requires_approval": result.requires_approval,
                        "proposed_alternative": result.proposed_alternative,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                except Exception as e:
                    await manager.broadcast({
                        "type": "error",
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/api/approval")
async def handle_approval(request: dict):
    """Handle user approval for an alternative plan."""
    approved = request.get("approved", False)
    alternative = request.get("alternative_plan", "")
    original_goal = request.get("original_goal", "")
    
    if approved and alternative:
        # Notify that we are starting the alternative
        await manager.broadcast({
            "type": "status",
            "status": "started",
            "goal": f"Executing alternative: {alternative[:50]}...",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Run the alternative plan in background
        asyncio.create_task(run_alternative(original_goal, alternative))
    
    return {"status": "received"}

async def run_alternative(original_goal: str, alternative_plan: str):
    """Run the approved alternative plan."""
    try:
        agent = await get_agent()
        
        # Create a new goal that incorporates the alternative approach
        new_goal = f"""Original Goal: {original_goal}
        
The previous attempt failed. 
APPROVED ALTERNATIVE APPROACH: {alternative_plan}

Please execute this alternative approach directly."""
        
        # Run it
        result = await agent.run(new_goal)
        
        # Broadcast result
        await manager.broadcast({
            "type": "result",
            "success": result.success,
            "message": result.message,
            "response": result.response,
            "steps": result.steps_taken,
            "extensions_created": result.extensions_created,
            "requires_approval": result.requires_approval,
            "proposed_alternative": result.proposed_alternative,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        await manager.broadcast({
            "type": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        })

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    global _adapter
    if _adapter:
        await _adapter.shutdown()
