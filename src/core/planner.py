"""Planner - decomposes goals into actionable steps."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.models.extension import ExtensionRecord


class ActionType(str, Enum):
    """Types of actions the agent can take."""
    EXECUTE_EXTENSION = "execute_extension"
    CREATE_EXTENSION = "create_extension"
    USE_CAPABILITY = "use_capability"
    REFLECT = "reflect"
    COMPLETE = "complete"
    FAIL = "fail"


@dataclass
class PlanStep:
    """A single step in a plan."""
    action: ActionType
    details: str
    extension_name: str | None = None
    capabilities_needed: list[str] | None = None
    params: dict | None = None  # Parameters for use_capability action


@dataclass
class Plan:
    """A complete plan to achieve a goal."""
    goal: str
    analysis: str
    steps: list[PlanStep]
    required_capabilities: list[str]
    new_extensions_needed: list[str]


class Planner:
    """Converts LLM plan output into structured Plan objects.
    
    Also provides utility methods for plan analysis.
    """
    
    def parse_plan(self, llm_response: dict) -> Plan:
        """Parse LLM plan response into a Plan object."""
        steps = []
        
        for step_data in llm_response.get("steps", []):
            action_str = step_data.get("action", "reflect")
            
            # Map string to enum
            try:
                action = ActionType(action_str)
            except ValueError:
                action = ActionType.REFLECT
            
            steps.append(PlanStep(
                action=action,
                details=step_data.get("details", ""),
                extension_name=step_data.get("extension_name"),
                capabilities_needed=step_data.get("capabilities_needed"),
                params=step_data.get("params")
            ))
        
        return Plan(
            goal=llm_response.get("goal", ""),
            analysis=llm_response.get("analysis", ""),
            steps=steps,
            required_capabilities=llm_response.get("required_capabilities", []),
            new_extensions_needed=llm_response.get("new_extensions_needed", [])
        )
    
    def find_matching_extension(
        self,
        task_description: str,
        available_extensions: list[ExtensionRecord]
    ) -> ExtensionRecord | None:
        """Find an existing extension that might handle a task.
        
        This is a simple keyword-based search. The LLM can do better,
        but this is useful for quick lookups.
        """
        task_words = set(task_description.lower().split())
        
        best_match = None
        best_score = 0
        
        for ext in available_extensions:
            # Score based on keyword overlap
            ext_words = set(
                ext.metadata.name.lower().replace("_", " ").split() +
                ext.metadata.description.lower().split() +
                ext.metadata.tags
            )
            
            overlap = len(task_words & ext_words)
            
            if overlap > best_score:
                best_score = overlap
                best_match = ext
        
        # Only return if there's meaningful overlap
        return best_match if best_score >= 2 else None
    
    def check_capabilities_available(
        self,
        required: list[str],
        available: list[str]
    ) -> tuple[bool, list[str]]:
        """Check if required capabilities are available.
        
        Returns:
            Tuple of (all_available, missing_capabilities)
        """
        missing = [cap for cap in required if cap not in available]
        return len(missing) == 0, missing
