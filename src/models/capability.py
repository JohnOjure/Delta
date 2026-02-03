"""Capability data models."""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class CapabilityStatus(str, Enum):
    """Status of a capability in the current environment."""
    AVAILABLE = "available"
    RESTRICTED = "restricted"
    UNAVAILABLE = "unavailable"


class CapabilityDescriptor(BaseModel):
    """Describes a capability that can be provided to extensions.
    
    This is the metadata about a capability, not the implementation.
    Used by the agent to understand what it can do.
    """
    name: str = Field(..., description="Unique capability name, e.g., 'fs.read'")
    description: str = Field(..., description="Human-readable description of what this capability does")
    status: CapabilityStatus = Field(default=CapabilityStatus.AVAILABLE)
    parameters: dict[str, str] = Field(
        default_factory=dict,
        description="Parameter name -> type description"
    )
    returns: str = Field(default="Any", description="Return type description")
    restrictions: list[str] = Field(
        default_factory=list,
        description="Any restrictions on this capability (e.g., 'read-only', 'rate-limited')"
    )

    def to_prompt_string(self) -> str:
        """Format this capability for inclusion in LLM prompts."""
        params = ", ".join(f"{k}: {v}" for k, v in self.parameters.items())
        status_note = f" [{self.status.value}]" if self.status != CapabilityStatus.AVAILABLE else ""
        restrictions_note = f" (Restrictions: {', '.join(self.restrictions)})" if self.restrictions else ""
        return f"- {self.name}({params}) -> {self.returns}{status_note}{restrictions_note}\n  {self.description}"


class CapabilityResult(BaseModel):
    """Result of executing a capability."""
    success: bool
    value: Any = None
    error: str | None = None
    
    @classmethod
    def ok(cls, value: Any) -> "CapabilityResult":
        return cls(success=True, value=value)
    
    @classmethod
    def fail(cls, error: str) -> "CapabilityResult":
        return cls(success=False, error=error)
