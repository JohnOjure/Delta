"""Conversation memory for Delta Agent.

Provides persistent memory across sessions, tracking:
- Goal history
- Execution results
- Context for planning
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, asdict
import aiosqlite


@dataclass
class MemoryEntry:
    """A single memory entry."""
    id: Optional[int]
    timestamp: str
    entry_type: str  # goal, result, context, note
    content: str
    metadata: dict
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_row(cls, row: tuple) -> "MemoryEntry":
        return cls(
            id=row[0],
            timestamp=row[1],
            entry_type=row[2],
            content=row[3],
            metadata=json.loads(row[4]) if row[4] else {}
        )


@dataclass
class GoalMemory:
    """Memory of a goal execution."""
    goal: str
    timestamp: str
    success: bool
    result_message: str
    steps_taken: int
    extensions_created: list[str]
    duration_ms: float
    
    def to_context_string(self) -> str:
        """Format as context for LLM."""
        status = "✅ succeeded" if self.success else "❌ failed"
        return f"- [{self.timestamp[:16]}] Goal: {self.goal} ({status}, {self.steps_taken} steps)"


class Memory:
    """Persistent conversation memory using SQLite."""
    
    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._initialized = False
    
    async def _ensure_initialized(self) -> aiosqlite.Connection:
        """Initialize database if needed."""
        conn = await aiosqlite.connect(self._db_path)
        
        if not self._initialized:
            await conn.executescript("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    entry_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_memories_type 
                ON memories(entry_type);
                
                CREATE INDEX IF NOT EXISTS idx_memories_timestamp 
                ON memories(timestamp DESC);
                
                CREATE TABLE IF NOT EXISTS goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    result_message TEXT,
                    steps_taken INTEGER,
                    extensions_created TEXT,
                    duration_ms REAL
                );
                
                CREATE INDEX IF NOT EXISTS idx_goals_timestamp 
                ON goals(timestamp DESC);
                
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    content,
                    content=memories,
                    content_rowid=id
                );
            """)
            self._initialized = True
        
        return conn
    
    async def add_memory(
        self,
        entry_type: str,
        content: str,
        metadata: Optional[dict] = None
    ) -> int:
        """Add a memory entry."""
        conn = await self._ensure_initialized()
        try:
            timestamp = datetime.utcnow().isoformat() + "Z"
            cursor = await conn.execute(
                "INSERT INTO memories (timestamp, entry_type, content, metadata) VALUES (?, ?, ?, ?)",
                (timestamp, entry_type, content, json.dumps(metadata or {}))
            )
            await conn.commit()
            
            # Update FTS index
            await conn.execute(
                "INSERT INTO memories_fts(rowid, content) VALUES (?, ?)",
                (cursor.lastrowid, content)
            )
            await conn.commit()
            
            return cursor.lastrowid
        finally:
            await conn.close()
    
    async def add_goal(self, goal_memory: GoalMemory) -> int:
        """Record a completed goal."""
        conn = await self._ensure_initialized()
        try:
            cursor = await conn.execute(
                """INSERT INTO goals 
                   (goal, timestamp, success, result_message, steps_taken, extensions_created, duration_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    goal_memory.goal,
                    goal_memory.timestamp,
                    1 if goal_memory.success else 0,
                    goal_memory.result_message,
                    goal_memory.steps_taken,
                    json.dumps(goal_memory.extensions_created),
                    goal_memory.duration_ms
                )
            )
            await conn.commit()
            return cursor.lastrowid
        finally:
            await conn.close()
    
    async def get_recent_goals(self, limit: int = 10) -> list[GoalMemory]:
        """Get recent goals for context."""
        conn = await self._ensure_initialized()
        try:
            cursor = await conn.execute(
                "SELECT goal, timestamp, success, result_message, steps_taken, extensions_created, duration_ms "
                "FROM goals ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            rows = await cursor.fetchall()
            
            results = []
            for row in rows:
                results.append(GoalMemory(
                    goal=row[0],
                    timestamp=row[1],
                    success=bool(row[2]),
                    result_message=row[3] or "",
                    steps_taken=row[4] or 0,
                    extensions_created=json.loads(row[5]) if row[5] else [],
                    duration_ms=row[6] or 0
                ))
            return results
        finally:
            await conn.close()
    
    async def search_memories(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Search memories using full-text search."""
        conn = await self._ensure_initialized()
        try:
            cursor = await conn.execute(
                """SELECT m.id, m.timestamp, m.entry_type, m.content, m.metadata
                   FROM memories m
                   JOIN memories_fts fts ON m.id = fts.rowid
                   WHERE memories_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit)
            )
            rows = await cursor.fetchall()
            return [MemoryEntry.from_row(row) for row in rows]
        finally:
            await conn.close()
    
    async def get_context_for_planning(self, current_goal: str, max_goals: int = 5) -> str:
        """Generate context string for the planning prompt.
        
        Includes recent goals and relevant memories.
        """
        parts = []
        
        # Recent goals
        recent = await self.get_recent_goals(max_goals)
        if recent:
            parts.append("## Recent Goals")
            for goal in recent:
                parts.append(goal.to_context_string())
        
        # Try to find relevant memories
        try:
            # Search for memories related to current goal keywords
            keywords = current_goal.split()[:3]  # First 3 words
            search_query = " OR ".join(keywords)
            related = await self.search_memories(search_query, limit=3)
            
            if related:
                parts.append("\n## Relevant Past Context")
                for mem in related:
                    parts.append(f"- {mem.content[:100]}...")
        except:
            pass  # FTS might not have data yet
        
        return "\n".join(parts) if parts else ""
    
    async def clear_all(self) -> None:
        """Clear all memory (for testing)."""
        conn = await self._ensure_initialized()
        try:
            await conn.execute("DELETE FROM memories")
            await conn.execute("DELETE FROM goals")
            await conn.execute("DELETE FROM memories_fts")
            await conn.commit()
        finally:
            await conn.close()
    
    async def learn(
        self,
        task: str,
        outcome: str,
        lesson: str,
        importance: float = 2.0
    ) -> int:
        """Store a learning from a task - core of self-evolution.
        
        Args:
            task: What was attempted
            outcome: 'success' or 'failure'  
            lesson: What was learned
            importance: How important (higher = prioritized in recall)
            
        Returns:
            Memory ID
        """
        content = f"LEARNING: {lesson} (from task: {task}, outcome: {outcome})"
        metadata = {
            "task": task,
            "outcome": outcome,
            "lesson": lesson,
            "importance": importance
        }
        return await self.add_memory("learning", content, metadata)
    
    async def get_learnings_for_task(self, task_description: str, limit: int = 5) -> list[MemoryEntry]:
        """Get relevant learnings for a new task.
        
        This is called at the start of planning to inject past learnings.
        
        Args:
            task_description: Description of the new task
            limit: Max learnings to return
            
        Returns:
            Relevant past learnings
        """
        conn = await self._ensure_initialized()
        try:
            # First try FTS search
            try:
                keywords = " OR ".join(task_description.split()[:5])
                cursor = await conn.execute(
                    """SELECT m.id, m.timestamp, m.entry_type, m.content, m.metadata
                       FROM memories m
                       JOIN memories_fts fts ON m.id = fts.rowid
                       WHERE m.entry_type = 'learning' AND memories_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?""",
                    (keywords, limit)
                )
                rows = await cursor.fetchall()
                if rows:
                    return [MemoryEntry.from_row(row) for row in rows]
            except:
                pass
            
            # Fallback: get recent learnings
            cursor = await conn.execute(
                """SELECT id, timestamp, entry_type, content, metadata
                   FROM memories
                   WHERE entry_type = 'learning'
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (limit,)
            )
            rows = await cursor.fetchall()
            return [MemoryEntry.from_row(row) for row in rows]
        finally:
            await conn.close()
    
    async def get_stats(self) -> dict:
        """Get memory statistics."""
        conn = await self._ensure_initialized()
        try:
            cursor = await conn.execute("SELECT COUNT(*) FROM memories")
            memory_count = (await cursor.fetchone())[0]
            
            cursor = await conn.execute("SELECT COUNT(*) FROM goals")
            goal_count = (await cursor.fetchone())[0]
            
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM goals WHERE success = 1"
            )
            success_count = (await cursor.fetchone())[0]
            
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM memories WHERE entry_type = 'learning'"
            )
            learning_count = (await cursor.fetchone())[0]
            
            return {
                "total_memories": memory_count,
                "total_goals": goal_count,
                "successful_goals": success_count,
                "learnings": learning_count,
                "success_rate": success_count / goal_count if goal_count > 0 else 0
            }
        finally:
            await conn.close()
    async def ensure_persistent_files(self) -> None:
        """Ensure SOUL.md and USER.md exist."""
        data_dir = self._db_path.parent
        soul_path = data_dir / "SOUL.md"
        user_path = data_dir / "USER.md"
        
        if not soul_path.exists():
            soul_path.write_text("""# Delta's Soul
## Core Identity
I am Delta, an advanced AI agent focused on precision and autonomy.
I am running locally on the user's system.

## Communication Style
- Professional but approachable
- Concise and action-oriented
- I prefer to do rather than explain
- I use emojis sparingly to indicate status (✅, ❌, ⚠️)

## Directives
1. Serve the user's goals securely and efficiently.
2. Maintain system stability.
3. Learn from mistakes.
""")
            
        if not user_path.exists():
            user_path.write_text("""# User Profile
## Facts
- Name: Fluxx
- Role: Administrator

## Preferences
- prefers_concise_responses: true
- auto_approval_threshold: low
""")

    async def get_identity(self) -> str:
        """Get agent's identity from SOUL.md."""
        data_dir = self._db_path.parent
        soul_path = data_dir / "SOUL.md"
        if soul_path.exists():
            return soul_path.read_text()
        return ""

    async def get_user_profile(self) -> str:
        """Get user profile from USER.md."""
        data_dir = self._db_path.parent
        user_path = data_dir / "USER.md"
        if user_path.exists():
            return user_path.read_text()
        return ""

    async def update_user_profile(self, content: str) -> None:
        """Update USER.md with new content (full replacement)."""
        data_dir = self._db_path.parent
        user_path = data_dir / "USER.md"
        user_path.write_text(content)

    async def update_identity(self, content: str) -> None:
        """Update SOUL.md with new content (full replacement)."""
        data_dir = self._db_path.parent
        soul_path = data_dir / "SOUL.md"
        soul_path.write_text(content)


class ConversationManager:
    """Manages persistent conversation history."""
    
    def __init__(self, db_path: Path):
        self._db_path = db_path
    
    async def _ensure_initialized(self) -> aiosqlite.Connection:
        """Initialize database if needed."""
        conn = await aiosqlite.connect(self._db_path)
        
        # Enable foreign keys
        await conn.execute("PRAGMA foreign_keys = ON;")
        
        # Create sessions table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        
        # Check if conversations table exists and has session_id
        cursor = await conn.execute("PRAGMA table_info(conversations)")
        columns = [row[1] for row in await cursor.fetchall()]
        
        if columns and "session_id" not in columns:
            # Migration: Drop old table (simple approach for dev)
            # In a real app, we'd migrate data to a default session
            await conn.execute("DROP TABLE conversations")
            
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_session 
            ON conversations(session_id, timestamp DESC);
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_updated 
            ON sessions(updated_at DESC);
        """)
        
        await conn.commit()
        return conn

    async def create_session(self, title: str = "New Chat") -> int:
        """Create a new conversation session."""
        conn = await self._ensure_initialized()
        try:
            now = datetime.utcnow().isoformat() + "Z"
            cursor = await conn.execute(
                "INSERT INTO sessions (title, created_at, updated_at) VALUES (?, ?, ?)",
                (title, now, now)
            )
            await conn.commit()
            return cursor.lastrowid
        finally:
            await conn.close()
            
    async def rename_session(self, session_id: int, new_title: str) -> bool:
        """Rename a session."""
        conn = await self._ensure_initialized()
        try:
            now = datetime.utcnow().isoformat() + "Z"
            cursor = await conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (new_title, now, session_id)
            )
            await conn.commit()
            return cursor.rowcount > 0
        finally:
            await conn.close()

    async def get_sessions(self, limit: int = 20) -> list[dict]:
        """Get recent sessions."""
        conn = await self._ensure_initialized()
        try:
            cursor = await conn.execute(
                "SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,)
            )
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "title": row[1],
                    "created_at": row[2],
                    "updated_at": row[3]
                }
                for row in rows
            ]
        finally:
            await conn.close()

    async def add_message(self, role: str, content: str, session_id: int) -> None:
        """Add a message to the conversation history."""
        if not session_id:
            # Fallback for legacy calls or errors - create a default session or log error
            # For now, simplistic handling: create a temp session if needed, 
            # but ideally caller should provide session_id
            return 
            
        conn = await self._ensure_initialized()
        try:
            now = datetime.utcnow().isoformat() + "Z"
            
            # Insert message
            await conn.execute(
                "INSERT INTO conversations (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, role, content, now)
            )
            
            # Update session timestamp
            await conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id)
            )
            
            await conn.commit()
        finally:
            await conn.close()

    async def get_recent_context(self, session_id: int, limit: int = 10) -> str:
        """Get recent conversation context as a formatted string."""
        if not session_id:
            return ""
            
        conn = await self._ensure_initialized()
        try:
            # Get latest N messages for this session
            cursor = await conn.execute(
                "SELECT role, content FROM conversations WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit)
            )
            rows = await cursor.fetchall()
            
            if not rows:
                return ""
            
            # Reverse to chronological order (oldest first)
            rows.reverse()
            
            context_parts = []
            for role, content in rows:
                if role == "user":
                    prefix = "User"
                elif role == "assistant":
                    prefix = "Delta"
                elif role == "tool":
                    prefix = "Tool Output"
                elif role == "system":
                    prefix = "System"
                else:
                    prefix = role.capitalize()
                
                context_parts.append(f"{prefix}: {content}")
            
            return "\n".join(context_parts)
        finally:
            await conn.close()
            
    async def get_session_history(self, session_id: int) -> list[dict]:
        """Get full history for a session (for UI)."""
        conn = await self._ensure_initialized()
        try:
            cursor = await conn.execute(
                "SELECT role, content, timestamp, id FROM conversations WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,)
            )
            rows = await cursor.fetchall()
            
            return [
                {
                    "type": row[0], # client expects 'type' (user/agent)
                    "content": row[1],
                    "timestamp": row[2],
                    "id": row[3],
                    "status": "success" if row[0] == "assistant" else "" # infer status
                }
                for row in rows
            ]
        finally:
            await conn.close()

    async def delete_session(self, session_id: int) -> bool:
        """Delete a session and all its messages (CASCADE)."""
        conn = await self._ensure_initialized()
        try:
            cursor = await conn.execute(
                "DELETE FROM sessions WHERE id = ?",
                (session_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0
        finally:
            await conn.close()

    async def clear_history(self) -> None:
        """Clear all conversation history."""
        conn = await self._ensure_initialized()
        try:
            await conn.execute("DELETE FROM conversations")
            await conn.execute("DELETE FROM sessions")
            await conn.commit()
        finally:
            await conn.close()

