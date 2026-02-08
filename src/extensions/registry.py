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
                
                -- Version history table for rollback support
                CREATE TABLE IF NOT EXISTS version_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    extension_name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    source_code TEXT NOT NULL,
                    description TEXT,
                    required_capabilities TEXT,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (extension_name) REFERENCES extensions(name)
                );
                
                CREATE INDEX IF NOT EXISTS idx_version_history_name 
                ON version_history(extension_name, version DESC);
            """)

            # Inject Core Extensions
            from src.extensions.core import CORE_EXTENSIONS
            for ext in CORE_EXTENSIONS:
                # Check if exists
                cursor = await conn.execute("SELECT id FROM extensions WHERE name = ?", (ext["name"],))
                exists = await cursor.fetchone()
                
                caps_json = json.dumps(ext["required_capabilities"])
                tags_json = json.dumps(["core", "safety_net"])
                
                if exists:
                    # Force update to ensure core extensions are always correct
                    await conn.execute("""
                        UPDATE extensions SET
                            description = ?,
                            required_capabilities = ?,
                            tags = ?,
                            source_code = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE name = ?
                    """, (ext["description"], caps_json, tags_json, ext["code"], ext["name"]))
                else:
                    await conn.execute("""
                        INSERT INTO extensions (name, version, description, required_capabilities, tags, source_code)
                        VALUES (?, '1.0.0', ?, ?, ?, ?)
                    """, (ext["name"], ext["description"], caps_json, tags_json, ext["code"]))
            
            await conn.commit()
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
        
        try:
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
        finally:
            await conn.close()
        
        # Fetch and return the complete record
        return await self.get_by_name(metadata.name)
    
    async def get_by_name(self, name: str) -> Optional[ExtensionRecord]:
        """Get an extension by name."""
        conn = await self._ensure_initialized()
        
        try:
            cursor = await conn.execute(
                "SELECT * FROM extensions WHERE name = ?",
                (name,)
            )
            row = await cursor.fetchone()
            
            if row is None:
                return None
            
            return self._row_to_record(row)
        finally:
            await conn.close()
    
    async def get_by_id(self, ext_id: int) -> Optional[ExtensionRecord]:
        """Get an extension by ID."""
        conn = await self._ensure_initialized()
        
        try:
            cursor = await conn.execute(
                "SELECT * FROM extensions WHERE id = ?",
                (ext_id,)
            )
            row = await cursor.fetchone()
            
            if row is None:
                return None
            
            return self._row_to_record(row)
        finally:
            await conn.close()
    
    async def search(self, query: str, limit: int = 10) -> list[ExtensionRecord]:
        """Search extensions using full-text search."""
        conn = await self._ensure_initialized()
        
        try:
            cursor = await conn.execute("""
                SELECT e.* FROM extensions e
                JOIN extensions_fts fts ON e.id = fts.rowid
                WHERE extensions_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
            
            rows = await cursor.fetchall()
            return [self._row_to_record(row) for row in rows]
        finally:
            await conn.close()
    
    async def list_all(self, limit: int = 100) -> list[ExtensionRecord]:
        """List all extensions."""
        conn = await self._ensure_initialized()
        
        try:
            cursor = await conn.execute(
                "SELECT * FROM extensions ORDER BY updated_at DESC LIMIT ?",
                (limit,)
            )
            rows = await cursor.fetchall()
            return [self._row_to_record(row) for row in rows]
        finally:
            await conn.close()
    
    async def list_by_capability(self, capability: str) -> list[ExtensionRecord]:
        """List extensions that use a specific capability."""
        conn = await self._ensure_initialized()
        
        try:
            # Using JSON search
            cursor = await conn.execute("""
                SELECT * FROM extensions 
                WHERE required_capabilities LIKE ?
                ORDER BY updated_at DESC
            """, (f'%"{capability}"%',))
            
            rows = await cursor.fetchall()
            return [self._row_to_record(row) for row in rows]
        finally:
            await conn.close()
    
    async def record_execution(
        self,
        name: str,
        result: any = None,
        error: str = None
    ):
        """Record an execution of an extension."""
        conn = await self._ensure_initialized()
        
        try:
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
        finally:
            await conn.close()
    
    async def delete(self, name: str) -> bool:
        """Delete an extension."""
        conn = await self._ensure_initialized()
        
        try:
            cursor = await conn.execute(
                "DELETE FROM extensions WHERE name = ?",
                (name,)
            )
            await conn.commit()
            return cursor.rowcount > 0
        finally:
            await conn.close()
    
    async def _archive_version(
        self, 
        conn: aiosqlite.Connection,
        name: str,
        version: str,
        source_code: str,
        description: str,
        required_capabilities: str,
        tags: str
    ) -> None:
        """Archive an extension version to history."""
        await conn.execute("""
            INSERT INTO version_history 
            (extension_name, version, source_code, description, required_capabilities, tags)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, version, source_code, description, required_capabilities, tags))
    
    async def get_version_history(self, name: str) -> list[dict]:
        """Get version history for an extension.
        
        Returns list of {version, created_at} dicts, newest first.
        """
        conn = await self._ensure_initialized()
        
        try:
            cursor = await conn.execute("""
                SELECT version, created_at FROM version_history
                WHERE extension_name = ?
                ORDER BY created_at DESC
            """, (name,))
            rows = await cursor.fetchall()
            return [{"version": row[0], "created_at": row[1]} for row in rows]
        finally:
            await conn.close()
    
    async def rollback(self, name: str, version: str) -> Optional[ExtensionRecord]:
        """Rollback an extension to a previous version.
        
        Args:
            name: Extension name
            version: Version to rollback to
            
        Returns:
            Updated ExtensionRecord or None if version not found
        """
        conn = await self._ensure_initialized()
        
        try:
            # Get the archived version
            cursor = await conn.execute("""
                SELECT version, source_code, description, required_capabilities, tags
                FROM version_history
                WHERE extension_name = ? AND version = ?
            """, (name, version))
            row = await cursor.fetchone()
            
            if row is None:
                return None
            
            old_version, source_code, description, required_caps, tags = row
            
            # Archive current version first
            cursor = await conn.execute("""
                SELECT version, source_code, description, required_capabilities, tags
                FROM extensions WHERE name = ?
            """, (name,))
            current = await cursor.fetchone()
            
            if current:
                await self._archive_version(
                    conn, name, current[0], current[1], current[2], current[3], current[4]
                )
            
            # Update to the old version
            await conn.execute("""
                UPDATE extensions SET
                    version = ?,
                    source_code = ?,
                    description = ?,
                    required_capabilities = ?,
                    tags = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE name = ?
            """, (old_version, source_code, description, required_caps, tags, name))
            
            await conn.commit()
        finally:
            await conn.close()
        
        return await self.get_by_name(name)
    
    async def get_stats(self) -> dict:
        """Get registry statistics."""
        conn = await self._ensure_initialized()
        
        try:
            cursor = await conn.execute("SELECT COUNT(*) FROM extensions")
            total = (await cursor.fetchone())[0]
            
            cursor = await conn.execute(
                "SELECT SUM(execution_count) FROM extensions"
            )
            total_executions = (await cursor.fetchone())[0] or 0
            
            cursor = await conn.execute("""
                SELECT name, execution_count FROM extensions
                ORDER BY execution_count DESC LIMIT 5
            """)
            top_extensions = [
                {"name": row[0], "executions": row[1]}
                for row in await cursor.fetchall()
            ]
            
            return {
                "total_extensions": total,
                "total_executions": total_executions,
                "top_extensions": top_extensions
            }
        finally:
            await conn.close()

