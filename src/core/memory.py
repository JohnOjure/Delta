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
