"""Storage capabilities.

Provides key-value storage backed by SQLite.
"""

import json
from pathlib import Path
from typing import Any
import aiosqlite

from src.models.capability import CapabilityDescriptor, CapabilityResult, CapabilityStatus
from .base import Capability


class StorageBase:
    """Shared storage backend for all storage capabilities."""
    
    _instance = None
    _db_path: Path
    
    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
    
    async def _get_connection(self) -> aiosqlite.Connection:
        """Get a database connection, creating the table if needed."""
        conn = await aiosqlite.connect(self._db_path)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS kv_store (
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (namespace, key)
            )
        """)
        await conn.commit()
        return conn


class StorageGetCapability(Capability):
    """Get a value from storage."""
    
    def __init__(self, storage: StorageBase, namespace: str = "default"):
        self._storage = storage
        self._namespace = namespace
    
    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="storage.get",
            description="Get a value from key-value storage",
            status=CapabilityStatus.AVAILABLE,
            parameters={"key": "str - Key to retrieve"},
            returns="Any - Stored value (or None if not found)",
            restrictions=[f"Namespace: {self._namespace}"]
        )
    
    async def execute(self, **kwargs: Any) -> CapabilityResult:
        key = kwargs.get("key")
        if not key:
            return CapabilityResult.fail("Missing required parameter: key")
        
        conn = await self._storage._get_connection()
        try:
            cursor = await conn.execute(
                "SELECT value FROM kv_store WHERE namespace = ? AND key = ?",
                (self._namespace, key)
            )
            row = await cursor.fetchone()
            
            if row is None:
                return CapabilityResult.ok(None)
            
            value = json.loads(row[0])
            return CapabilityResult.ok(value)
        except Exception as e:
            return CapabilityResult.fail(f"Storage error: {e}")
        finally:
            await conn.close()


class StorageSetCapability(Capability):
    """Set a value in storage."""
    
    def __init__(self, storage: StorageBase, namespace: str = "default"):
        self._storage = storage
        self._namespace = namespace
    
    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="storage.set",
            description="Store a value in key-value storage",
            status=CapabilityStatus.AVAILABLE,
            parameters={
                "key": "str - Key to store",
                "value": "Any - Value to store (must be JSON-serializable)"
            },
            returns="bool - True if successful",
            restrictions=[f"Namespace: {self._namespace}"]
        )
    
    async def execute(self, **kwargs: Any) -> CapabilityResult:
        key = kwargs.get("key")
        value = kwargs.get("value")
        
        if not key:
            return CapabilityResult.fail("Missing required parameter: key")
        if value is None:
            return CapabilityResult.fail("Missing required parameter: value")
        
        try:
            value_json = json.dumps(value)
        except (TypeError, ValueError) as e:
            return CapabilityResult.fail(f"Value is not JSON-serializable: {e}")
        
        conn = await self._storage._get_connection()
        try:
            await conn.execute("""
                INSERT INTO kv_store (namespace, key, value, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT (namespace, key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
            """, (self._namespace, key, value_json))
            await conn.commit()
            return CapabilityResult.ok(True)
        except Exception as e:
            return CapabilityResult.fail(f"Storage error: {e}")
        finally:
            await conn.close()


class StorageDeleteCapability(Capability):
    """Delete a value from storage."""
    
    def __init__(self, storage: StorageBase, namespace: str = "default"):
        self._storage = storage
        self._namespace = namespace
    
    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="storage.delete",
            description="Delete a value from key-value storage",
            status=CapabilityStatus.AVAILABLE,
            parameters={"key": "str - Key to delete"},
            returns="bool - True if deleted, False if key didn't exist",
            restrictions=[f"Namespace: {self._namespace}"]
        )
    
    async def execute(self, **kwargs: Any) -> CapabilityResult:
        key = kwargs.get("key")
        if not key:
            return CapabilityResult.fail("Missing required parameter: key")
        
        conn = await self._storage._get_connection()
        try:
            cursor = await conn.execute(
                "DELETE FROM kv_store WHERE namespace = ? AND key = ?",
                (self._namespace, key)
            )
            await conn.commit()
            return CapabilityResult.ok(cursor.rowcount > 0)
        except Exception as e:
            return CapabilityResult.fail(f"Storage error: {e}")
        finally:
            await conn.close()
