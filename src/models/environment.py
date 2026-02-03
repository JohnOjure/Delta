"""Environment and resource limit models."""

from enum import Enum
from pydantic import BaseModel, Field

from .capability import CapabilityDescriptor


class Platform(str, Enum):
    """Supported platforms."""
    DESKTOP = "desktop"
    BROWSER = "browser"
    CLOUD = "cloud"
    MOBILE = "mobile"


class ResourceLimits(BaseModel):
    """Resource limits for extension execution."""
    cpu_time_seconds: float = Field(default=30.0, description="Max CPU time per execution")
    memory_mb: int = Field(default=256, description="Max memory in megabytes")
    output_size_bytes: int = Field(default=1_000_000, description="Max output size")
    network_requests: int | None = Field(default=None, description="Max network requests (None = unlimited)")


class EnvironmentInfo(BaseModel):
    """Information about the current execution environment.
    
    Reported by the adapter to the agent core.
    """
    platform: Platform
    capabilities: dict[str, CapabilityDescriptor] = Field(
        default_factory=dict,
        description="Available capabilities and their status"
    )
    limits: ResourceLimits = Field(default_factory=ResourceLimits)
    working_directory: str = Field(..., description="Current working directory")
    extra: dict = Field(
        default_factory=dict,
        description="Platform-specific extra information"
    )
    
    def to_prompt_string(self) -> str:
        """Format for inclusion in LLM prompts."""
        caps_str = "\n".join(c.to_prompt_string() for c in self.capabilities.values())
        return (
            f"## Current Environment\n"
            f"**Platform:** {self.platform.value}\n"
            f"**Working Directory:** {self.working_directory}\n"
            f"**Resource Limits:**\n"
            f"  - CPU Time: {self.limits.cpu_time_seconds}s\n"
            f"  - Memory: {self.limits.memory_mb}MB\n\n"
            f"## Available Capabilities\n{caps_str}"
        )
