from typing import Any
from .base import Capability
from src.models.capability import CapabilityDescriptor, CapabilityResult

class SystemCapability(Capability):
    """Capability to access system information."""
    
    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="system",
            description="Access system information (CPU, Memory, Disk, etc.)",
            api={} # No specific API exposed to LLM context construction yet, mostly a permission flag for extensions
        )

    async def execute(self, **kwargs: Any) -> CapabilityResult:
        """Execute system capability."""
        # For now, this is just a permission marker.
        # Future: could expose specific system calls here.
        return CapabilityResult(success=True, value="System access granted")
