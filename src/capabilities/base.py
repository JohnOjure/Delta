"""Base capability interface.

Capabilities are the ONLY way extensions can interact with the outside world.
They are:
- Explicit: Extensions must declare what they need
- Auditable: All capability usage is logged
- Revocable: Can be disabled at any time
- Sandboxed: No ambient authority
"""

from abc import ABC, abstractmethod
from typing import Any

from src.models.capability import CapabilityDescriptor, CapabilityResult


class Capability(ABC):
    """Abstract base class for all capabilities.
    
    A capability is an explicit, revocable permission to perform a class of actions.
    Extensions receive capability objects as function arguments - they cannot
    access anything that isn't explicitly provided.
    """
    
    @property
    @abstractmethod
    def descriptor(self) -> CapabilityDescriptor:
        """Return the capability descriptor for this capability."""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs: Any) -> CapabilityResult:
        """Execute this capability with the given arguments.
        
        Returns:
            CapabilityResult with success/failure and value/error
        """
        pass
    
    def __call__(self, **kwargs: Any):
        """Allow calling capability like a function (sync wrapper).
        
        This is a convenience for extensions. Under the hood it's still async.
        """
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self.execute(**kwargs))
    
    @property
    def name(self) -> str:
        """Shortcut to get capability name."""
        return self.descriptor.name
