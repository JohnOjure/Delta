"""Base adapter interface.

Adapters are the only layer that touches the real world.
Each environment (desktop, browser, cloud, mobile) has its own adapter.
"""

from abc import ABC, abstractmethod

from src.models.environment import EnvironmentInfo, ResourceLimits
from src.capabilities.base import Capability


class BaseAdapter(ABC):
    """Abstract base class for environment adapters.
    
    An adapter is responsible for:
    - Reporting the current environment to the agent
    - Providing available capabilities
    - Enforcing platform-specific policies
    - Translating abstract actions to real ones
    """
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the adapter.
        
        Called once at startup to set up any required resources.
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up adapter resources.
        
        Called when the agent is shutting down.
        """
        pass
    
    @abstractmethod
    def get_environment_info(self) -> EnvironmentInfo:
        """Get information about the current environment.
        
        Returns:
            EnvironmentInfo describing the platform, capabilities, and limits
        """
        pass
    
    @abstractmethod
    def get_available_capabilities(self) -> dict[str, Capability]:
        """Get all capabilities available in this environment.
        
        Returns:
            Dict mapping capability name (e.g., "fs.read") to Capability instance
        """
        pass
    
    @abstractmethod
    def get_resource_limits(self) -> ResourceLimits:
        """Get resource limits for this environment.
        
        Returns:
            ResourceLimits describing CPU, memory, and other constraints
        """
        pass
    
    def get_capability(self, name: str) -> Capability | None:
        """Get a specific capability by name.
        
        Args:
            name: Capability name (e.g., "fs.read")
            
        Returns:
            Capability instance or None if not available
        """
        return self.get_available_capabilities().get(name)
