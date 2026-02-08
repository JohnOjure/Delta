"""Desktop adapter - local machine environment.

Provides full access to local filesystem, network, and storage.
This is the most capable adapter, used for development and local execution.
"""

import os
import platform
from pathlib import Path

from src.models.environment import EnvironmentInfo, ResourceLimits, Platform
from src.models.capability import CapabilityDescriptor
from src.capabilities.base import Capability
from src.capabilities.filesystem import (
    FileSystemReadCapability,
    FileSystemWriteCapability,
    FileSystemListCapability,
)
from src.capabilities.network import NetworkFetchCapability
from src.capabilities.storage import (
    StorageBase,
    StorageGetCapability,
    StorageSetCapability,
    StorageDeleteCapability,
)
from src.capabilities.shell import ShellCapability, PythonExecCapability
from src.capabilities.system import SystemCapability

from .base import BaseAdapter


class DesktopAdapter(BaseAdapter):
    """Adapter for local desktop/development environment.
    
    Provides:
    - Full filesystem access (configurable)
    - Unrestricted network access
    - SQLite-backed key-value storage
    """
    
    def __init__(
        self,
        api_key: str,
        working_directory: str | Path | None = None,
        data_directory: str | Path | None = None,
        allowed_paths: list[str] | None = None,
        allowed_domains: list[str] | None = None,
        resource_limits: ResourceLimits | None = None,
        enable_shell: bool = True,
        power_mode: bool = True,  # Default to True as requested
    ):
        """Initialize the desktop adapter.
        
        Args:
            working_directory: Working directory for the agent (default: cwd)
            data_directory: Where to store data/extensions (default: working_dir/data)
            allowed_paths: Restrict filesystem to these paths (default: None = all)
            allowed_domains: Restrict network to these domains (default: None = all)
            resource_limits: Custom resource limits (default: generous limits)
        """
        self._api_key = api_key
        self._working_dir = Path(working_directory or os.getcwd()).resolve()
        self._data_dir = Path(data_directory or self._working_dir / "data").resolve()
        self._allowed_paths = allowed_paths
        self._allowed_domains = allowed_domains
        self._enable_shell = enable_shell
        self._power_mode = power_mode
        self._limits = resource_limits or ResourceLimits(
            cpu_time_seconds=60.0,
            memory_mb=512,
        )
        
        # Storage backend (shared between storage capabilities)
        self._storage: StorageBase | None = None
        
        # Capabilities (created during initialize)
        self._capabilities: dict[str, Capability] = {}
    
    async def initialize(self) -> None:
        """Set up the desktop environment."""
        # Ensure directories exist
        self._data_dir.mkdir(parents=True, exist_ok=True)
        
        # Create storage backend
        db_path = self._data_dir / "delta.db"
        self._storage = StorageBase(db_path)
        
        # Create capabilities
        self._capabilities = {
            # Filesystem
            "fs.read": FileSystemReadCapability(self._allowed_paths),
            "fs.write": FileSystemWriteCapability(self._allowed_paths),
            "fs.list": FileSystemListCapability(self._allowed_paths),
            "filesystem": FileSystemReadCapability(self._allowed_paths),  # Alias for core extensions
            
            # Network
            "net.fetch": NetworkFetchCapability(
                allowed_domains=self._allowed_domains,
                timeout=30.0
            ),
            
            # Storage
            "storage.get": StorageGetCapability(self._storage),
            "storage.set": StorageSetCapability(self._storage),
            "storage.delete": StorageDeleteCapability(self._storage),
        }
        


        # Vision capability (optional - requires mss)
        try:
            from src.capabilities.vision import VisionCapability
            self._capabilities["vision.capture_screen"] = VisionCapability()
        except ImportError:
            pass  # mss not installed
        
        # System capability
        self._capabilities["system"] = SystemCapability()
        
        # Shell capabilities (if enabled)
        if self._enable_shell:
            shell_cap = ShellCapability(
                api_key=self._api_key,
                working_directory=str(self._working_dir),
                power_mode=self._power_mode
            )
            self._capabilities["shell.exec"] = shell_cap
            self._capabilities["python.exec"] = PythonExecCapability(shell_cap)
    
    async def shutdown(self) -> None:
        """Clean up resources."""
        # Nothing to clean up currently
        pass
    
    def get_environment_info(self) -> EnvironmentInfo:
        """Get desktop environment information."""
        caps = {
            name: cap.descriptor 
            for name, cap in self._capabilities.items()
        }
        
        return EnvironmentInfo(
            platform=Platform.DESKTOP,
            capabilities=caps,
            limits=self._limits,
            working_directory=str(self._working_dir),
            extra={
                "os": platform.system(),
                "os_version": platform.version(),
                "python_version": platform.python_version(),
                "machine": platform.machine(),
                "data_directory": str(self._data_dir),
            }
        )
    
    def get_available_capabilities(self) -> dict[str, Capability]:
        """Get all available capabilities."""
        return self._capabilities.copy()
    
    def get_resource_limits(self) -> ResourceLimits:
        """Get resource limits."""
        return self._limits
