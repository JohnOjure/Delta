"""Capability usage tracking for Delta Agent.

Records and analyzes capability usage for optimization and debugging.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, asdict
import aiosqlite


@dataclass
class UsageRecord:
    """Record of a capability usage."""
    id: Optional[int]
    timestamp: str
    capability: str
    operation: str
    success: bool
    duration_ms: float
    input_summary: str
    output_summary: str
    error: Optional[str]
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class UsageStats:
    """Statistics for a capability."""
    capability: str
    total_calls: int
    successful_calls: int
    failed_calls: int
    success_rate: float
    avg_duration_ms: float
    total_duration_ms: float


class UsageTracker:
    """Tracks capability usage with SQLite persistence."""
    
    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._initialized = False
    
    async def _ensure_initialized(self) -> aiosqlite.Connection:
        """Initialize database if needed."""
        conn = await aiosqlite.connect(self._db_path)
        
        if not self._initialized:
            await conn.executescript("""
                CREATE TABLE IF NOT EXISTS usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    operation TEXT,
                    success INTEGER NOT NULL,
                    duration_ms REAL,
                    input_summary TEXT,
                    output_summary TEXT,
                    error TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_usage_capability 
                ON usage(capability);
                
                CREATE INDEX IF NOT EXISTS idx_usage_timestamp 
                ON usage(timestamp DESC);
                
                CREATE TABLE IF NOT EXISTS daily_stats (
                    date TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    calls INTEGER DEFAULT 0,
                    successes INTEGER DEFAULT 0,
                    failures INTEGER DEFAULT 0,
                    total_duration_ms REAL DEFAULT 0,
                    PRIMARY KEY (date, capability)
                );
            """)
            self._initialized = True
        
        return conn
    
    async def record(
        self,
        capability: str,
        operation: str,
        success: bool,
        duration_ms: float,
        input_summary: str = "",
        output_summary: str = "",
        error: Optional[str] = None
    ) -> int:
        """Record a capability usage."""
        conn = await self._ensure_initialized()
        try:
            timestamp = datetime.utcnow().isoformat() + "Z"
            date = timestamp[:10]  # YYYY-MM-DD
            
            # Record detailed usage
            cursor = await conn.execute(
                """INSERT INTO usage 
                   (timestamp, capability, operation, success, duration_ms, input_summary, output_summary, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (timestamp, capability, operation, 1 if success else 0, duration_ms, 
                 input_summary[:500], output_summary[:500], error)
            )
            
            # Update daily stats
            await conn.execute(
                """INSERT INTO daily_stats (date, capability, calls, successes, failures, total_duration_ms)
                   VALUES (?, ?, 1, ?, ?, ?)
                   ON CONFLICT(date, capability) DO UPDATE SET
                   calls = calls + 1,
                   successes = successes + ?,
                   failures = failures + ?,
                   total_duration_ms = total_duration_ms + ?""",
                (date, capability, 
                 1 if success else 0, 
                 0 if success else 1, 
                 duration_ms,
                 1 if success else 0,
                 0 if success else 1,
                 duration_ms)
            )
            
            await conn.commit()
            return cursor.lastrowid
        finally:
            await conn.close()
    
    async def get_capability_stats(self, capability: Optional[str] = None) -> list[UsageStats]:
        """Get usage statistics for capabilities."""
        conn = await self._ensure_initialized()
        try:
            if capability:
                cursor = await conn.execute(
                    """SELECT capability, 
                              SUM(calls) as total_calls,
                              SUM(successes) as successful,
                              SUM(failures) as failed,
                              SUM(total_duration_ms) as total_duration
                       FROM daily_stats
                       WHERE capability = ?
                       GROUP BY capability""",
                    (capability,)
                )
            else:
                cursor = await conn.execute(
                    """SELECT capability, 
                              SUM(calls) as total_calls,
                              SUM(successes) as successful,
                              SUM(failures) as failed,
                              SUM(total_duration_ms) as total_duration
                       FROM daily_stats
                       GROUP BY capability
                       ORDER BY total_calls DESC"""
                )
            
            rows = await cursor.fetchall()
            results = []
            
            for row in rows:
                total = row[1] or 0
                successful = row[2] or 0
                failed = row[3] or 0
                total_duration = row[4] or 0
                
                results.append(UsageStats(
                    capability=row[0],
                    total_calls=total,
                    successful_calls=successful,
                    failed_calls=failed,
                    success_rate=successful / total if total > 0 else 0,
                    avg_duration_ms=total_duration / total if total > 0 else 0,
                    total_duration_ms=total_duration
                ))
            
            return results
        finally:
            await conn.close()
    
    async def get_recent_usage(self, limit: int = 50, capability: Optional[str] = None) -> list[UsageRecord]:
        """Get recent usage records."""
        conn = await self._ensure_initialized()
        try:
            if capability:
                cursor = await conn.execute(
                    """SELECT id, timestamp, capability, operation, success, duration_ms, 
                              input_summary, output_summary, error
                       FROM usage
                       WHERE capability = ?
                       ORDER BY timestamp DESC
                       LIMIT ?""",
                    (capability, limit)
                )
            else:
                cursor = await conn.execute(
                    """SELECT id, timestamp, capability, operation, success, duration_ms, 
                              input_summary, output_summary, error
                       FROM usage
                       ORDER BY timestamp DESC
                       LIMIT ?""",
                    (limit,)
                )
            
            rows = await cursor.fetchall()
            return [
                UsageRecord(
                    id=row[0],
                    timestamp=row[1],
                    capability=row[2],
                    operation=row[3] or "",
                    success=bool(row[4]),
                    duration_ms=row[5] or 0,
                    input_summary=row[6] or "",
                    output_summary=row[7] or "",
                    error=row[8]
                )
                for row in rows
            ]
        finally:
            await conn.close()
    
    async def get_daily_breakdown(self, days: int = 7) -> dict[str, dict]:
        """Get daily usage breakdown."""
        conn = await self._ensure_initialized()
        try:
            cursor = await conn.execute(
                """SELECT date, capability, calls, successes, failures, total_duration_ms
                   FROM daily_stats
                   ORDER BY date DESC, calls DESC
                   LIMIT ?""",
                (days * 20,)  # Assume max 20 capabilities
            )
            
            rows = await cursor.fetchall()
            result = {}
            
            for row in rows:
                date = row[0]
                if date not in result:
                    result[date] = {}
                
                result[date][row[1]] = {
                    "calls": row[2],
                    "successes": row[3],
                    "failures": row[4],
                    "duration_ms": row[5]
                }
            
            return result
        finally:
            await conn.close()
    
    async def get_summary(self) -> dict:
        """Get overall usage summary."""
        stats = await self.get_capability_stats()
        
        total_calls = sum(s.total_calls for s in stats)
        total_successes = sum(s.successful_calls for s in stats)
        total_duration = sum(s.total_duration_ms for s in stats)
        
        top_capabilities = sorted(stats, key=lambda s: s.total_calls, reverse=True)[:5]
        
        return {
            "total_calls": total_calls,
            "total_successes": total_successes,
            "overall_success_rate": total_successes / total_calls if total_calls > 0 else 0,
            "total_duration_ms": total_duration,
            "capabilities_used": len(stats),
            "top_capabilities": [
                {"name": s.capability, "calls": s.total_calls, "success_rate": s.success_rate}
                for s in top_capabilities
            ]
        }
