"""Extension registry - SQLite-backed storage for extensions."""

from datetime import datetime
from pathlib import Path
from typing import Optional
import aiosqlite
import json

from src.models.extension import ExtensionMetadata, ExtensionRecord


class ExtensionRegistry:
    """Manages storage and retrieval of extensions.
    
    Uses SQLite for persistence with full-text search support
    for extension discovery.
    """
    
    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False
    
    async def _ensure_initialized(self) -> aiosqlite.Connection:
        """Get connection and ensure tables exist."""
        conn = await aiosqlite.connect(self._db_path)
        
        if not self._initialized:
            await conn.executescript("""
                CREATE TABLE IF NOT EXISTS extensions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    version TEXT NOT NULL,
                    description TEXT NOT NULL,
                    required_capabilities TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    source_code TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    execution_count INTEGER DEFAULT 0,
                    last_executed_at TIMESTAMP,
                    last_result TEXT,
                    last_error TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_extensions_name ON extensions(name);
                CREATE INDEX IF NOT EXISTS idx_extensions_tags ON extensions(tags);
                
                -- Full-text search table
                CREATE VIRTUAL TABLE IF NOT EXISTS extensions_fts USING fts5(
                    name, description, tags,
                    content='extensions',
                    content_rowid='id'
                );
                
                -- Triggers to keep FTS in sync
                CREATE TRIGGER IF NOT EXISTS extensions_ai AFTER INSERT ON extensions BEGIN
                    INSERT INTO extensions_fts(rowid, name, description, tags)
                    VALUES (new.id, new.name, new.description, new.tags);
                END;
                
                CREATE TRIGGER IF NOT EXISTS extensions_ad AFTER DELETE ON extensions BEGIN
                    INSERT INTO extensions_fts(extensions_fts, rowid, name, description, tags)
                    VALUES ('delete', old.id, old.name, old.description, old.tags);
                END;
                
                CREATE TRIGGER IF NOT EXISTS extensions_au AFTER UPDATE ON extensions BEGIN
                    INSERT INTO extensions_fts(extensions_fts, rowid, name, description, tags)
                    VALUES ('delete', old.id, old.name, old.description, old.tags);
                    INSERT INTO extensions_fts(rowid, name, description, tags)
                    VALUES (new.id, new.name, new.description, new.tags);
                END;
            """)
            self._initialized = True
        
        return conn
    
    def _row_to_record(self, row: tuple) -> ExtensionRecord:
        """Convert a database row to an ExtensionRecord."""
        return ExtensionRecord(
            id=row[0],
            metadata=ExtensionMetadata(
                name=row[1],
                version=row[2],
                description=row[3],
                required_capabilities=json.loads(row[4]),
                tags=json.loads(row[5])
            ),
            source_code=row[6],
            created_at=datetime.fromisoformat(row[7]) if row[7] else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row[8]) if row[8] else datetime.utcnow(),
            execution_count=row[9] or 0,
            last_executed_at=datetime.fromisoformat(row[10]) if row[10] else None,
            last_result=json.loads(row[11]) if row[11] else None,
            last_error=row[12]
        )
    
    async def register(self, metadata: ExtensionMetadata, source_code: str) -> ExtensionRecord:
        """Register a new extension or update an existing one.
        
        Args:
            metadata: Extension metadata
            source_code: The Python source code
            
        Returns:
            The registered ExtensionRecord with assigned ID
        """
        conn = await self._ensure_initialized()
        
        async with conn:
            # Check if extension exists
            cursor = await conn.execute(
                "SELECT id FROM extensions WHERE name = ?",
                (metadata.name,)
            )
            existing = await cursor.fetchone()
            
            caps_json = json.dumps(metadata.required_capabilities)
            tags_json = json.dumps(metadata.tags)
            
            if existing:
                # Update existing
                await conn.execute("""
                    UPDATE extensions SET
                        version = ?,
                        description = ?,
                        required_capabilities = ?,
                        tags = ?,
                        source_code = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE name = ?
                """, (
                    metadata.version,
                    metadata.description,
                    caps_json,
                    tags_json,
                    source_code,
                    metadata.name
                ))
                ext_id = existing[0]
            else:
                # Insert new
                cursor = await conn.execute("""
                    INSERT INTO extensions (name, version, description, required_capabilities, tags, source_code)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    metadata.name,
                    metadata.version,
                    metadata.description,
                    caps_json,
                    tags_json,
                    source_code
                ))
                ext_id = cursor.lastrowid
            
            await conn.commit()
        
        # Fetch and return the complete record
        return await self.get_by_name(metadata.name)
    
    async def get_by_name(self, name: str) -> Optional[ExtensionRecord]:
        """Get an extension by name."""
        conn = await self._ensure_initialized()
        
        async with conn:
            cursor = await conn.execute(
                "SELECT * FROM extensions WHERE name = ?",
                (name,)
            )
            row = await cursor.fetchone()
            
            if row is None:
                return None
            
            return self._row_to_record(row)
    
    async def get_by_id(self, ext_id: int) -> Optional[ExtensionRecord]:
        """Get an extension by ID."""
        conn = await self._ensure_initialized()
        
        async with conn:
            cursor = await conn.execute(
                "SELECT * FROM extensions WHERE id = ?",
                (ext_id,)
            )
            row = await cursor.fetchone()
            
            if row is None:
                return None
            
            return self._row_to_record(row)
    
    async def search(self, query: str, limit: int = 10) -> list[ExtensionRecord]:
        """Search extensions using full-text search."""
        conn = await self._ensure_initialized()
        
        async with conn:
            cursor = await conn.execute("""
                SELECT e.* FROM extensions e
                JOIN extensions_fts fts ON e.id = fts.rowid
                WHERE extensions_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
            
            rows = await cursor.fetchall()
            return [self._row_to_record(row) for row in rows]
    
    async def list_all(self, limit: int = 100) -> list[ExtensionRecord]:
        """List all extensions."""
        conn = await self._ensure_initialized()
        
        async with conn:
            cursor = await conn.execute(
                "SELECT * FROM extensions ORDER BY updated_at DESC LIMIT ?",
                (limit,)
            )
            rows = await cursor.fetchall()
            return [self._row_to_record(row) for row in rows]
    
    async def list_by_capability(self, capability: str) -> list[ExtensionRecord]:
        """List extensions that use a specific capability."""
        conn = await self._ensure_initialized()
        
        async with conn:
            # Using JSON search
            cursor = await conn.execute("""
                SELECT * FROM extensions 
                WHERE required_capabilities LIKE ?
                ORDER BY updated_at DESC
            """, (f'%"{capability}"%',))
            
            rows = await cursor.fetchall()
            return [self._row_to_record(row) for row in rows]
    
    async def record_execution(
        self,
        name: str,
        result: any = None,
        error: str = None
    ):
        """Record an execution of an extension."""
        conn = await self._ensure_initialized()
        
        async with conn:
            result_json = json.dumps(result) if result is not None else None
            
            await conn.execute("""
                UPDATE extensions SET
                    execution_count = execution_count + 1,
                    last_executed_at = CURRENT_TIMESTAMP,
                    last_result = ?,
                    last_error = ?
                WHERE name = ?
            """, (result_json, error, name))
            
            await conn.commit()
    
    async def delete(self, name: str) -> bool:
        """Delete an extension."""
        conn = await self._ensure_initialized()
        
        async with conn:
            cursor = await conn.execute(
                "DELETE FROM extensions WHERE name = ?",
                (name,)
            )
            await conn.commit()
            return cursor.rowcount > 0
