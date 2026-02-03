"""Extension data models."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class ExtensionMetadata(BaseModel):
    """Metadata for an extension module.
    
    This is what the agent generates along with the code.
    """
    name: str = Field(..., description="Unique extension name")
    version: str = Field(default="1.0.0", description="Semantic version")
    description: str = Field(..., description="What this extension does")
    required_capabilities: list[str] = Field(
        default_factory=list,
        description="List of capability names this extension needs"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for searching/categorizing"
    )


class ExtensionRecord(BaseModel):
    """Full extension record as stored in the database."""
    id: int | None = None
    metadata: ExtensionMetadata
    source_code: str = Field(..., description="The actual Python source code")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    execution_count: int = Field(default=0, description="Number of times executed")
    last_executed_at: datetime | None = None
    last_result: Any = None
    last_error: str | None = None
    
    def to_prompt_string(self) -> str:
        """Format for inclusion in LLM prompts."""
        caps = ", ".join(self.metadata.required_capabilities) or "none"
        return (
            f"### {self.metadata.name} (v{self.metadata.version})\n"
            f"**Description:** {self.metadata.description}\n"
            f"**Required Capabilities:** {caps}\n"
            f"**Executions:** {self.execution_count}\n"
        )
