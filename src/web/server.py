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
    session_id: Optional[int] = None


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
    result = await agent.run(request.goal, session_id=request.session_id)
    
    return {
        "success": result.success,
        "message": result.message,
        "response": result.response,
        "steps": result.steps_taken,
        "extensions_created": result.extensions_created
    }


class GhostAlert(BaseModel):
    """Ghost Mode alert message."""
    severity: str = "medium"
    message: str


@app.post("/api/ghost/alert")
async def ghost_alert(alert: GhostAlert):
    """Broadcast a Ghost Mode alert to all connected WebSocket clients."""
    await manager.broadcast({
        "type": "ghost_alert",
        "severity": alert.severity,
        "message": alert.message,
        "timestamp": datetime.utcnow().isoformat()
    })
    return {"success": True, "broadcast_to": len(manager.active_connections)}


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


class SessionCreateRequest(BaseModel):
    title: str = "New Chat"


@app.post("/api/sessions")
async def create_session(request: SessionCreateRequest):
    """Create a new session."""
    agent = await get_agent()
    if not agent._conversation:
        raise HTTPException(503, "Conversation manager not initialized")
    
    session_id = await agent._conversation.create_session(request.title)
    return {"id": session_id, "title": request.title}


@app.get("/api/sessions")
async def list_sessions():
    """List recent sessions."""
    agent = await get_agent()
    if not agent._conversation:
        return []
    
    return await agent._conversation.get_sessions()


@app.get("/api/sessions/{session_id}/history")
async def get_session_history(session_id: int):
    """Get history for a session."""
    agent = await get_agent()
    if not agent._conversation:
        return []
    
    return await agent._conversation.get_session_history(session_id)


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: int):
    """Delete a session (optional, for management)."""
    # Not yet implemented in ConversationManager but good to have endpoint ready
    return {"success": False, "message": "Not implemented yet"}


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


@app.get("/api/config")
async def get_config_endpoint():
    """Get current configuration."""
    config_mgr = get_config()
    
    # Mask API key for security
    api_key = config_mgr.api.gemini_api_key
    masked_key = ""
    if api_key and len(api_key) > 8:
        masked_key = f"{api_key[:4]}...{api_key[-4:]}"
    elif api_key:
        masked_key = "********"
        
    return {
        "user_name": config_mgr.user_name if hasattr(config_mgr, "user_name") else "User",
        "model_name": config_mgr.api.gemini_model,
        "api_key": masked_key,
        "usage_limit": config_mgr.execution.max_iterations, # mapping usage_limit to max_iterations for now or just checking if usage_limit exists
        "voice_enabled": False # config_mgr doesn't seem to have voice_enabled in the Dataclass, defaulting to False
    }


@app.get("/api/logs")
async def get_logs(lines: int = 100):
    """Get the last N lines of logs."""
    log_path = Path.home() / ".delta" / "delta.log"
    if not log_path.exists():
        return {"logs": []}
        
    try:
        # Simple implementation for reading last N lines
        # For large files, seeking from end is better, but this is fine for now
        content = log_path.read_text(encoding="utf-8", errors="replace")
        all_lines = content.splitlines()
        return {"logs": all_lines[-lines:]}
    except Exception as e:
        return {"logs": [f"Error reading logs: {e}"]}


@app.post("/api/config")
async def update_config_endpoint(start_config: dict):
    """Update configuration."""
    from src.core.config import ConfigManager
    from src.config import reset_config
    
    manager = ConfigManager()
    config = manager.load()
    
    if not config:
        return {"success": False, "message": "No configuration found"}
    
    updates = {}
    if "user_name" in start_config: updates["user_name"] = start_config["user_name"]
    if "model_name" in start_config: updates["model_name"] = start_config["model_name"]
    
    # Handle API Key updates safely
    if "api_key" in start_config:
        new_key = start_config["api_key"]
        
        # Get current key from loaded config
        current_key = config.api_key if hasattr(config, 'api_key') else ""
        
        # Check if this is the masked key being sent back
        is_masked = False
        if current_key and len(current_key) > 8:
            masked_version = f"{current_key[:4]}...{current_key[-4:]}"
            if new_key == masked_version:
                is_masked = True
        
        if not is_masked and new_key != "********":
            # Trim whitespace from API key
            updates["api_key"] = new_key.strip()

    if "usage_limit" in start_config: updates["usage_limit"] = int(start_config["usage_limit"])
    if "voice_enabled" in start_config: updates["voice_enabled"] = bool(start_config["voice_enabled"])
    
    manager.update(**updates)
    
    # Reset the global config cache
    reset_config()
    
    global _agent, _adapter
    # If API key or Model changed, we might need to re-init agent components
    if "api_key" in updates or "model_name" in updates:
        _agent = None # Force re-creation on next get_agent()
        _adapter = None
        
    return {"success": True, "message": "Configuration updated"}


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
                session_id = message.get("session_id")
                
                # Notify start
                await manager.broadcast({
                    "type": "status",
                    "status": "started",
                    "goal": goal,
                    "session_id": session_id,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                try:
                    # Create status callback for real-time thinking updates
                    async def on_status(status):
                        broadcast_data = {
                            "type": "thinking",
                            "state": status.get("state", ""),
                            "activity": status.get("activity", ""),
                            "details": status.get("details", ""),
                            "iteration": status.get("iteration", 0),
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        # Include code preview if present
                        if status.get("code"):
                            broadcast_data["code"] = status.get("code")
                            broadcast_data["extension_name"] = status.get("extension_name", "")
                        
                        # Handle direct tool outputs
                        if status.get("state") == "tool_output":
                            broadcast_data["type"] = "tool_output"
                            broadcast_data["output"] = status.get("details", "")
                        
                        await manager.broadcast(broadcast_data)

                        # await manager.broadcast(broadcast_data)
                    
                    agent = await get_agent()
                    agent._on_status = on_status  # Attach callback
                    
                    # Run goal with real-time status updates
                    result = await agent.run(goal, session_id=session_id)
                    
                    await manager.broadcast({
                        "type": "result",
                        "success": result.success,
                        "message": result.message,
                        "response": result.response,
                        "steps": result.steps_taken,
                        "extensions_created": result.extensions_created,
                        "requires_approval": result.requires_approval,
                        "propsed_alternative": result.proposed_alternative,
                        "session_id": session_id,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                except Exception as e:
                    import traceback
                    print(f"  [Error] WebSocket loop error: {e}")
                    traceback.print_exc()
                    
                    await manager.broadcast({
                        "type": "error",
                        "error": "An internal error occurred. Please try again.",
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
        import traceback
        print(f"  [Error] Alternative plan error: {e}")
        traceback.print_exc()
        
        await manager.broadcast({
            "type": "error",
            "error": "An internal error occurred while executing the plan.",
            "timestamp": datetime.utcnow().isoformat()
        })

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    global _adapter
    if _adapter:
        await _adapter.shutdown()
