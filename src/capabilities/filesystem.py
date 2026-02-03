"""Filesystem capabilities.

Provides controlled access to the filesystem.
All operations go through these capabilities - no direct file access allowed.
"""

import os
from pathlib import Path
from typing import Any

from src.models.capability import CapabilityDescriptor, CapabilityResult, CapabilityStatus
from .base import Capability


class FileSystemReadCapability(Capability):
    """Read files from the filesystem."""
    
    def __init__(self, allowed_paths: list[str] | None = None):
        """Initialize with optional path restrictions.
        
        Args:
            allowed_paths: If provided, only these paths (and their subdirectories) are accessible.
                          If None, all paths are accessible.
        """
        self._allowed_paths = [Path(p).resolve() for p in allowed_paths] if allowed_paths else None
    
    @property
    def descriptor(self) -> CapabilityDescriptor:
        restrictions = []
        if self._allowed_paths:
            restrictions.append(f"Limited to: {', '.join(str(p) for p in self._allowed_paths)}")
        
        return CapabilityDescriptor(
            name="fs.read",
            description="Read the contents of a file",
            status=CapabilityStatus.AVAILABLE,
            parameters={"path": "str - Path to the file to read"},
            returns="str - File contents",
            restrictions=restrictions
        )
    
    def _is_path_allowed(self, path: Path) -> bool:
        """Check if a path is within allowed paths."""
        if self._allowed_paths is None:
            return True
        resolved = path.resolve()
        return any(
            resolved == allowed or allowed in resolved.parents
            for allowed in self._allowed_paths
        )
    
    async def execute(self, **kwargs: Any) -> CapabilityResult:
        path_str = kwargs.get("path")
        if not path_str:
            return CapabilityResult.fail("Missing required parameter: path")
        
        try:
            path = Path(path_str)
            
            if not self._is_path_allowed(path):
                return CapabilityResult.fail(f"Path not allowed: {path}")
            
            if not path.exists():
                return CapabilityResult.fail(f"File not found: {path}")
            
            if not path.is_file():
                return CapabilityResult.fail(f"Not a file: {path}")
            
            content = path.read_text(encoding="utf-8")
            return CapabilityResult.ok(content)
            
        except PermissionError:
            return CapabilityResult.fail(f"Permission denied: {path_str}")
        except Exception as e:
            return CapabilityResult.fail(f"Error reading file: {e}")


class FileSystemWriteCapability(Capability):
    """Write files to the filesystem."""
    
    def __init__(self, allowed_paths: list[str] | None = None):
        self._allowed_paths = [Path(p).resolve() for p in allowed_paths] if allowed_paths else None
    
    @property
    def descriptor(self) -> CapabilityDescriptor:
        restrictions = []
        if self._allowed_paths:
            restrictions.append(f"Limited to: {', '.join(str(p) for p in self._allowed_paths)}")
        
        return CapabilityDescriptor(
            name="fs.write",
            description="Write content to a file (creates parent directories if needed)",
            status=CapabilityStatus.AVAILABLE,
            parameters={
                "path": "str - Path to the file to write",
                "content": "str - Content to write"
            },
            returns="bool - True if successful",
            restrictions=restrictions
        )
    
    def _is_path_allowed(self, path: Path) -> bool:
        if self._allowed_paths is None:
            return True
        resolved = path.resolve()
        return any(
            resolved == allowed or allowed in resolved.parents
            for allowed in self._allowed_paths
        )
    
    async def execute(self, **kwargs: Any) -> CapabilityResult:
        path_str = kwargs.get("path")
        content = kwargs.get("content")
        
        if not path_str:
            return CapabilityResult.fail("Missing required parameter: path")
        if content is None:
            return CapabilityResult.fail("Missing required parameter: content")
        
        try:
            path = Path(path_str)
            
            if not self._is_path_allowed(path):
                return CapabilityResult.fail(f"Path not allowed: {path}")
            
            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)
            
            path.write_text(str(content), encoding="utf-8")
            return CapabilityResult.ok(True)
            
        except PermissionError:
            return CapabilityResult.fail(f"Permission denied: {path_str}")
        except Exception as e:
            return CapabilityResult.fail(f"Error writing file: {e}")


class FileSystemListCapability(Capability):
    """List directory contents."""
    
    def __init__(self, allowed_paths: list[str] | None = None):
        self._allowed_paths = [Path(p).resolve() for p in allowed_paths] if allowed_paths else None
    
    @property
    def descriptor(self) -> CapabilityDescriptor:
        restrictions = []
        if self._allowed_paths:
            restrictions.append(f"Limited to: {', '.join(str(p) for p in self._allowed_paths)}")
        
        return CapabilityDescriptor(
            name="fs.list",
            description="List contents of a directory",
            status=CapabilityStatus.AVAILABLE,
            parameters={"path": "str - Path to the directory"},
            returns="list[dict] - List of {name, is_dir, size} entries",
            restrictions=restrictions
        )
    
    def _is_path_allowed(self, path: Path) -> bool:
        if self._allowed_paths is None:
            return True
        resolved = path.resolve()
        return any(
            resolved == allowed or allowed in resolved.parents
            for allowed in self._allowed_paths
        )
    
    async def execute(self, **kwargs: Any) -> CapabilityResult:
        path_str = kwargs.get("path")
        if not path_str:
            return CapabilityResult.fail("Missing required parameter: path")
        
        try:
            path = Path(path_str)
            
            if not self._is_path_allowed(path):
                return CapabilityResult.fail(f"Path not allowed: {path}")
            
            if not path.exists():
                return CapabilityResult.fail(f"Directory not found: {path}")
            
            if not path.is_dir():
                return CapabilityResult.fail(f"Not a directory: {path}")
            
            entries = []
            for entry in path.iterdir():
                entries.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size": entry.stat().st_size if entry.is_file() else None
                })
            
            return CapabilityResult.ok(entries)
            
        except PermissionError:
            return CapabilityResult.fail(f"Permission denied: {path_str}")
        except Exception as e:
            return CapabilityResult.fail(f"Error listing directory: {e}")
