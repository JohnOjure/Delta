"""Agent - the main reasoning and action loop.

This is Layer 1: the "mind" of the system.
It reasons about goals, plans actions, generates extensions,
and reflects on results.
"""

import asyncio
from dataclasses import dataclass
from typing import Any
from enum import Enum

from src.adapters.base import BaseAdapter
from src.extensions.registry import ExtensionRegistry
from src.extensions.introspection import ExtensionIntrospector
from src.vm.executor import Executor
from .gemini_client import GeminiClient
from .planner import Planner, Plan, ActionType, PlanStep
from .generator import ExtensionGenerator


class AgentState(str, Enum):
    """Current state of the agent."""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    WAITING = "waiting"


@dataclass
class AgentResult:
    """Result of an agent task."""
    success: bool
    message: str
    data: Any = None
    extensions_created: list[str] = None
    steps_taken: int = 0


class Agent:
    """The Delta agent - a self-extensible AI system.
    
    The agent:
    1. Receives goals from the user
    2. Plans how to achieve them using available capabilities
    3. Creates new extensions when needed
    4. Executes extensions to accomplish tasks
    5. Reflects on results and improves
    
    All intelligence comes from the Gemini LLM.
    All actions go through the sandboxed VM.
    All capabilities come from the environment adapter.
    """
    
    def __init__(
        self,
        adapter: BaseAdapter,
        gemini_client: GeminiClient,
        registry: ExtensionRegistry,
        max_iterations: int = 10
    ):
        """Initialize the agent.
        
        Args:
            adapter: Environment adapter providing capabilities
            gemini_client: Gemini API client for reasoning
            registry: Extension registry for storage
            max_iterations: Max steps before giving up on a goal
        """
        self._adapter = adapter
        self._gemini = gemini_client
        self._registry = registry
        self._max_iterations = max_iterations
        
        # Components
        self._executor = Executor(adapter.get_resource_limits())
        self._planner = Planner()
        self._generator = ExtensionGenerator()
        self._introspector = ExtensionIntrospector()
        
        # State
        self._state = AgentState.IDLE
        self._current_goal: str | None = None
        self._iteration = 0
    
    @property
    def state(self) -> AgentState:
        """Current agent state."""
        return self._state
    
    async def run(self, goal: str) -> AgentResult:
        """Run the agent to accomplish a goal.
        
        This is the main entry point. The agent will:
        1. Plan how to achieve the goal
        2. Execute the plan step by step
        3. Create extensions as needed
        4. Reflect and adapt
        
        Args:
            goal: Natural language description of what to accomplish
            
        Returns:
            AgentResult with success/failure and details
        """
        self._current_goal = goal
        self._iteration = 0
        extensions_created = []
        
        print(f"\n🎯 Goal: {goal}\n")
        
        try:
            # Get environment info for context
            env_info = self._adapter.get_environment_info()
            env_str = env_info.to_prompt_string()
            
            # Get existing extensions
            extensions = await self._registry.list_all()
            ext_str = "\n".join(e.to_prompt_string() for e in extensions) or "None"
            
            while self._iteration < self._max_iterations:
                self._iteration += 1
                print(f"📍 Iteration {self._iteration}/{self._max_iterations}")
                
                # 1. Plan
                self._state = AgentState.PLANNING
                print("  🧠 Planning...")
                
                plan_response = await self._gemini.plan(goal, env_str, ext_str)
                plan = self._planner.parse_plan(plan_response)
                
                print(f"  📋 Plan: {plan.analysis[:100]}...")
                
                # 2. Execute each step
                for step in plan.steps:
                    self._state = AgentState.EXECUTING
                    
                    if step.action == ActionType.COMPLETE:
                        print("  ✅ Goal completed!")
                        return AgentResult(
                            success=True,
                            message="Goal accomplished",
                            extensions_created=extensions_created,
                            steps_taken=self._iteration
                        )
                    
                    elif step.action == ActionType.FAIL:
                        print(f"  ❌ Cannot complete: {step.details}")
                        return AgentResult(
                            success=False,
                            message=step.details,
                            extensions_created=extensions_created,
                            steps_taken=self._iteration
                        )
                    
                    elif step.action == ActionType.CREATE_EXTENSION:
                        print(f"  🔧 Creating extension: {step.details[:50]}...")
                        
                        # Generate extension code
                        caps = step.capabilities_needed or plan.required_capabilities
                        caps_str = "\n".join(
                            c.to_prompt_string() 
                            for c in env_info.capabilities.values()
                            if c.name in caps
                        )
                        
                        gen_response = await self._gemini.generate_extension(
                            step.details, caps, caps_str
                        )
                        
                        metadata, code = self._generator.parse_generation(gen_response)
                        
                        # Validate
                        is_valid, issues = self._generator.validate(code)
                        if not is_valid:
                            print(f"    ⚠️ Validation issues: {issues}")
                            code = self._generator.fix_common_issues(code)
                            is_valid, issues = self._generator.validate(code)
                        
                        if is_valid:
                            # Register extension
                            record = await self._registry.register(metadata, code)
                            extensions_created.append(metadata.name)
                            print(f"    ✅ Created: {metadata.name}")
                            
                            # Update extensions list
                            extensions = await self._registry.list_all()
                            ext_str = "\n".join(e.to_prompt_string() for e in extensions)
                        else:
                            print(f"    ❌ Failed to create valid extension")
                    
                    elif step.action == ActionType.EXECUTE_EXTENSION:
                        ext_name = step.extension_name or step.details.split()[0]
                        print(f"  ▶️ Executing: {ext_name}")
                        
                        extension = await self._registry.get_by_name(ext_name)
                        if not extension:
                            print(f"    ❌ Extension not found: {ext_name}")
                            continue
                        
                        result = await self._executor.execute(
                            extension,
                            self._adapter.get_available_capabilities()
                        )
                        
                        # Record execution
                        await self._registry.record_execution(
                            ext_name,
                            result=result.value if result.success else None,
                            error=result.error
                        )
                        
                        if result.success:
                            print(f"    ✅ Result: {str(result.value)[:100]}...")
                        else:
                            print(f"    ❌ Error: {result.error}")
                            
                            # Reflect on failure
                            self._state = AgentState.REFLECTING
                            reflection = await self._gemini.reflect(
                                f"Executed {ext_name}",
                                result.error,
                                was_success=False
                            )
                            print(f"    💭 Reflection: {reflection.get('assessment', '')[:100]}...")
                    
                    elif step.action == ActionType.REFLECT:
                        self._state = AgentState.REFLECTING
                        print(f"  💭 Reflecting: {step.details[:50]}...")
                
                # If we got here, plan didn't explicitly complete
                # Ask if we should continue
                self._state = AgentState.REFLECTING
                reflection = await self._gemini.reflect(
                    f"Completed iteration {self._iteration} of plan",
                    f"Executed {len(plan.steps)} steps",
                    was_success=True
                )
                
                if not reflection.get("should_retry", True):
                    return AgentResult(
                        success=True,
                        message="Plan executed",
                        extensions_created=extensions_created,
                        steps_taken=self._iteration
                    )
            
            # Max iterations reached
            return AgentResult(
                success=False,
                message=f"Max iterations ({self._max_iterations}) reached",
                extensions_created=extensions_created,
                steps_taken=self._iteration
            )
            
        except Exception as e:
            import traceback
            return AgentResult(
                success=False,
                message=f"Error: {e}\n{traceback.format_exc()}",
                extensions_created=extensions_created,
                steps_taken=self._iteration
            )
        finally:
            self._state = AgentState.IDLE
            self._current_goal = None
    
    async def list_extensions(self) -> list[dict]:
        """List all registered extensions."""
        extensions = await self._registry.list_all()
        return [
            {
                "name": e.metadata.name,
                "description": e.metadata.description,
                "version": e.metadata.version,
                "capabilities": e.metadata.required_capabilities,
                "executions": e.execution_count
            }
            for e in extensions
        ]
    
    async def get_extension_source(self, name: str) -> str | None:
        """Get the source code of an extension."""
        extension = await self._registry.get_by_name(name)
        if extension:
            return self._introspector.get_source_code(extension)
        return None
    
    async def execute_extension(self, name: str) -> dict:
        """Manually execute an extension by name."""
        extension = await self._registry.get_by_name(name)
        if not extension:
            return {"success": False, "error": f"Extension not found: {name}"}
        
        result = await self._executor.execute(
            extension,
            self._adapter.get_available_capabilities()
        )
        
        await self._registry.record_execution(
            name,
            result=result.value if result.success else None,
            error=result.error
        )
        
        return {
            "success": result.success,
            "value": result.value,
            "error": result.error,
            "execution_time_ms": result.execution_time_ms
        }
