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
from src.core.memory import Memory
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
    response: str = ""  # Actual LLM response content
    data: Any = None
    extensions_created: list[str] = None
    steps_taken: int = 0
    requires_approval: bool = False
    proposed_alternative: dict = None


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
        memory: Memory | None = None,
        max_iterations: int = 10,
        on_status: callable = None
    ):
        """Initialize the agent.
        
        Args:
            adapter: Environment adapter providing capabilities
            gemini_client: Gemini API client for reasoning
            registry: Extension registry for storage
            memory: Persistent memory for learning
            max_iterations: Max steps before giving up on a goal
            on_status: Optional callback for status updates (async)
        """
        self._adapter = adapter
        self._gemini = gemini_client
        self._registry = registry
        self._memory = memory
        self._max_iterations = max_iterations
        self._on_status = on_status
        
        # Components
        self._executor = Executor(adapter.get_resource_limits())
        self._planner = Planner()
        self._generator = ExtensionGenerator()
        self._introspector = ExtensionIntrospector()
        
        # State
        self._state = AgentState.IDLE
        self._current_goal: str | None = None
        self._iteration = 0
    
    async def _emit_status(self, activity: str, details: str = ""):
        """Emit status update to callback."""
        if self._on_status:
            await self._on_status({
                "state": self._state.value,
                "activity": activity,
                "details": details,
                "iteration": self._iteration
            })
    
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
        
        print(f"\n[Goal] {goal}\n")
        
        try:
            # Get environment info for context
            env_info = self._adapter.get_environment_info()
            env_str = env_info.to_prompt_string()
            
            # Inject Persistent Memory (Soul & User)
            if self._memory:
                try:
                    await self._memory.ensure_persistent_files()
                    soul = await self._memory.get_identity()
                    user = await self._memory.get_user_profile()
                    
                    if soul:
                        env_str += f"\n\n## Agent Identity (SOUL)\n{soul}"
                    if user:
                        env_str += f"\n\n## User Context\n{user}"
                        
                except Exception as e:
                    print(f"  [Memory] Failed to load persistent context: {e}")
            
            # Get existing extensions
            extensions = await self._registry.list_all()
            ext_str = "\n".join(e.to_prompt_string() for e in extensions) or "None"
            
            # Get relevant learnings from memory (SELF-EVOLUTION)
            learnings_str = ""
            if self._memory:
                try:
                    learnings = await self._memory.get_learnings_for_task(goal)
                    if learnings:
                        learnings_str = "\n## Past Learnings (Use These!)\n"
                        for l in learnings:
                            learnings_str += f"- {l.content}\n"
                        print(f"  [Memory] Retrieved {len(learnings)} relevant learnings")
                except Exception as e:
                    print(f"  [Memory] Failed to retrieve learnings: {e}")
            
            # Intelligent Adaptive Loop
            # We set a high safety limit, but the real control comes from the agent's decisions
            # and the user's ability to stop it.
            safety_limit = 1000  # Effectively infinite for most tasks
            consecutive_failures = 0
            
            while self._iteration < safety_limit:
                self._iteration += 1
                print(f"[Iteration {self._iteration}]")
                
                # 1. Plan
                self._state = AgentState.PLANNING
                print("  Planning...")
                await self._emit_status("Thinking", "Analyzing your request and planning approach...")
                
                # Inject learnings into planning context
                context_ext_str = ext_str
                if learnings_str:
                    context_ext_str = ext_str + "\n" + learnings_str
                
                try:
                    plan_response = await self._gemini.plan(goal, env_str, context_ext_str)
                    plan = self._planner.parse_plan(plan_response)
                except Exception as e:
                    # Intelligent Model Switching
                    error_str = str(e).lower()
                    if "404" in error_str or "not found" in error_str or "429" in error_str or "resource" in error_str:
                        print(f"  [!] Model Error: {e}")
                        
                        current_model = self._gemini._model_name
                        available = self._gemini.get_available_models()
                        
                        # Find next model
                        if current_model in available:
                            idx = available.index(current_model)
                            next_idx = (idx + 1) % len(available)
                            next_model = available[next_idx]
                            
                            # Auto-switch
                            print(f"  [i] Auto-Switching to {next_model} to recover...")
                            await self._emit_status("Recovering", f"Switching to {next_model}")
                            self._gemini.switch_model(next_model)
                            continue 
                        
                    raise e
                
                print(f"  Plan: {plan.analysis[:100]}...")
                await self._emit_status("Planning", plan.analysis[:500])
                
                # 2. Execute each step
                for step in plan.steps:
                    self._state = AgentState.EXECUTING
                    
                    if step.action == ActionType.COMPLETE:
                        print("  Goal completed.")
                        await self._emit_status("Completed", "Goal accomplished.")
                        # For Q&A, the actual answer is in step.details (per planning prompt)
                        # Only fall back to analysis if details is empty or generic
                        answer = step.details if step.details and step.details not in ["Goal accomplished", ""] else plan.analysis
                        return AgentResult(
                            success=True,
                            message="Goal accomplished",
                            response=answer,
                            extensions_created=extensions_created,
                            steps_taken=self._iteration
                        )
                    
                    elif step.action == ActionType.FAIL:
                        print(f"  Cannot complete: {step.details}")
                        await self._emit_status("Failed", step.details)
                        
                        # Intelligent Failure Recovery
                        consecutive_failures += 1
                        if consecutive_failures >= 3:
                            # If we're stuck in a loop of failures, ask for help
                            return AgentResult(
                                success=False,
                                message=f"Stuck after {consecutive_failures} consecutive failures: {step.details}",
                                response=plan.analysis,
                                extensions_created=extensions_created,
                                steps_taken=self._iteration
                            )
                        
                        # Ask for alternatives
                        alternatives = await self._gemini.suggest_alternatives(
                            original_goal=goal,
                            failed_approach=step.details,
                            errors_encountered=[step.details]
                        )
                        
                        if alternatives.get("can_auto_try") and alternatives.get("recommended"):
                            print(f"  [Auto-Recovery] Trying alternative: {alternatives['recommended']}")
                            await self._emit_status("Recovering", f"Trying alternative: {alternatives['recommended']}")
                            # Continue loop, next planning phase will use this context
                            # We inject the alternative as a "learning" for the next plan
                            learnings_str += f"\n- Alternative approach suggested: {alternatives['recommended']}\n"
                            continue
                        
                        return AgentResult(
                            success=False,
                            message=step.details,
                            response=plan.analysis,
                            extensions_created=extensions_created,
                            steps_taken=self._iteration
                        )
                    
                    elif step.action == ActionType.CREATE_EXTENSION:
                        print(f"  Creating extension: {step.details[:50]}...")
                        await self._emit_status("Building", f"Creating extension: {step.details[:50]}...")
                        
                        # Generate extension code
                        caps = step.capabilities_needed or plan.required_capabilities
                        caps_str = "\n".join(
                            c.to_prompt_string() 
                            for c in env_info.capabilities.values()
                            if c.name in caps
                        )
                        
                        max_attempts = 30  # Increased persistence
                        attempt = 0
                        extension_valid = False
                        all_errors = []  # Track all errors for learning
                        
                        while attempt < max_attempts and not extension_valid:
                            attempt += 1
                            print(f"    Attempt {attempt}/{max_attempts}...")
                            await self._emit_status("Building", f"Generating code (Attempt {attempt}/{max_attempts})...")
                            
                            # Generate/regenerate extension
                            if attempt == 1:
                                gen_response = await self._gemini.generate_extension(
                                    step.details, caps, caps_str
                                )
                            else:
                                # Regenerate with feedback from previous attempt
                                enhanced_desc = f"""{step.details}

PREVIOUS ATTEMPT FAILED. Issues:
{validation_result.get('reason', 'Unknown')}

Suggestions:
{validation_result.get('suggestions', 'Ensure the extension returns actual data, not empty results.')}

Make sure to:
1. Actually extract/process the data, don't just return success
2. Validate that results are not empty before returning
3. Return the actual data in the result"""
                                gen_response = await self._gemini.generate_extension(
                                    enhanced_desc, caps, caps_str
                                )
                            
                            metadata, code = self._generator.parse_generation(gen_response)
                            
                            # Syntax validation
                            is_valid, issues = self._generator.validate(code)
                            if not is_valid:
                                print(f"    Syntax issues: {issues}")
                                await self._emit_status("Fixing", f"Syntax error in generated code...")
                                code = self._generator.fix_common_issues(code)
                                is_valid, issues = self._generator.validate(code)
                            
                            if not is_valid:
                                print(f"    Failed syntax validation, retrying...")
                                validation_result = {"reason": f"Syntax errors: {issues}", "suggestions": "Fix syntax errors"}
                                all_errors.append(f"Syntax error: {issues}")
                                continue
                            
                            # Create temporary record for testing (not saved to DB)
                            from src.models.extension import ExtensionRecord
                            temp_record = ExtensionRecord(
                                metadata=metadata,
                                source_code=code
                            )
                            
                            # Test execution
                            print(f"    Testing {metadata.name}...")
                            await self._emit_status("Testing", f"Verifying {metadata.name}...")
                            exec_result = await self._executor.execute(
                                temp_record,
                                self._adapter.get_available_capabilities()
                            )
                            
                            if not exec_result.success:
                                print(f"    Execution failed: {exec_result.error}")
                                validation_result = {"reason": f"Execution error: {exec_result.error}", "suggestions": "Fix the runtime error"}
                                all_errors.append(f"Execution error: {exec_result.error}")
                                continue
                            
                            print(f"    Test result: {str(exec_result.value)[:150]}")
                            
                            # LLM validation - does result actually achieve the goal?
                            validation_result = await self._gemini.validate_extension_result(
                                original_goal=goal,
                                extension_description=step.details,
                                execution_result=exec_result.value
                            )
                            
                            print(f"    Validation: {'PASS' if validation_result.get('valid') else 'FAIL'} - {validation_result.get('reason', '')[:80]}")
                            
                            if validation_result.get('valid'):
                                extension_valid = True
                            else:
                                print(f"    Suggestions: {validation_result.get('suggestions', '')[:100]}")
                                all_errors.append(f"Validation failed: {validation_result.get('reason', 'Unknown')}")
                        
                        if extension_valid:
                            # NOW register the validated extension
                            record = await self._registry.register(metadata, code)
                            extensions_created.append(metadata.name)
                            print(f"    Registered: {metadata.name} (validated)")
                            await self._emit_status("Success", f"Created extension: {metadata.name}")
                            
                            # Record the successful execution
                            await self._registry.record_execution(
                                metadata.name,
                                result=exec_result.value,
                                error=None
                            )
                            
                            # Update extensions list
                            extensions = await self._registry.list_all()
                            ext_str = "\n".join(e.to_prompt_string() for e in extensions)
                        else:
                            # All attempts failed - ask LLM for alternative approaches
                            print(f"    Failed after {max_attempts} attempts. Finding alternatives...")
                            
                            alternatives = await self._gemini.suggest_alternatives(
                                original_goal=goal,
                                failed_approach=step.details,
                                errors_encountered=all_errors[-5:]  # Last 5 errors
                            )
                            
                            alt_msg = alternatives.get('message', 'Could not complete this task.')
                            suggestions = alternatives.get('alternatives', [])
                            recommended = alternatives.get('recommended', suggestions[0] if suggestions else "None")
                            
                            print(f"    Alternatives: {suggestions}")
                            print(f"    Recommended: {recommended}")
                            
                            # ASK FOR APPROVAL instead of failing
                            return AgentResult(
                                success=False, # Temporarily False until approved
                                message=f"I couldn't complete the task with the current approach. I have an alternative plan.",
                                response=f"{alt_msg}\n\n**Recommended Alternative:**\n{recommended}\n\n**Other Options:**\n" + "\n".join(f"- {s}" for s in suggestions[:3]),
                                extensions_created=extensions_created,
                                steps_taken=self._iteration,
                                requires_approval=True,
                                proposed_alternative={
                                    "original_goal": goal,
                                    "alternative_plan": recommended,
                                    "context": f"Failed approach: {step.details}"
                                }
                            )
                    
                    elif step.action == ActionType.EXECUTE_EXTENSION:
                        ext_name = step.extension_name or step.details.split()[0]
                        print(f"  Executing: {ext_name}")
                        await self._emit_status("Executing", f"Running extension: {ext_name}...")
                        
                        extension = await self._registry.get_by_name(ext_name)
                        if not extension:
                            print(f"    Extension not found: {ext_name}")
                            await self._emit_status("Error", f"Extension not found: {ext_name}")
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
                            print(f"    Result: {str(result.value)[:100]}...")
                        else:
                            print(f"    Error: {result.error}")
                            await self._emit_status("Error", f"Execution failed: {result.error}")
                            
                            # Reflect on failure
                            # Reflect on failure with VISUAL context
                            self._state = AgentState.REFLECTING
                            
                            # Capture screen for debugging
                            image_data = None
                            try:
                                vision = self._adapter.get_available_capabilities().get("vision.capture_screen")
                                if vision:
                                    vis_result = await vision.execute()
                                    if vis_result.success:
                                        image_data = vis_result.value.get("image_data")
                                        print("    Captured screenshot for debugging")
                            except Exception as e:
                                print(f"    Failed to capture debug screenshot: {e}")

                            reflection = await self._gemini.reflect(
                                f"Executed {ext_name}",
                                result.error,
                                was_success=False,
                                image_data=image_data
                            )
                            print(f"    Reflection: {reflection.get('assessment', '')[:100]}...")
                    
                    elif step.action == ActionType.USE_CAPABILITY:
                        # Direct capability invocation
                        details_str = step.details if isinstance(step.details, str) else str(step.details)
                        
                        # Parse capability name
                        cap_name = None
                        
                        # Check if capabilities_needed is specified
                        if step.capabilities_needed:
                            cap_name = step.capabilities_needed[0]
                        else:
                            # Try to extract from details
                            for available_cap in self._adapter.get_available_capabilities().keys():
                                if available_cap in details_str:
                                    cap_name = available_cap
                                    break
                        
                        if not cap_name:
                            print(f"    Could not determine capability from: {details_str[:50]}")
                            continue
                        
                        print(f"  Using capability: {cap_name}")
                        await self._emit_status("Action", f"Using capability: {cap_name}...")
                        
                        # Get the capability
                        capabilities = self._adapter.get_available_capabilities()
                        if cap_name not in capabilities:
                            print(f"    Capability not available: {cap_name}")
                            continue
                        
                        capability = capabilities[cap_name]
                        
                        # Get parameters - prioritize step.params from LLM
                        cap_params = {}
                        if step.params and isinstance(step.params, dict):
                            cap_params = step.params
                        elif isinstance(step.details, dict):
                            # Legacy: extract from details dict
                            cap_params = {k: v for k, v in step.details.items() 
                                         if k not in ['action', 'capability']}
                        elif cap_name.startswith('fs.') and not cap_params:
                            # Default for filesystem operations
                            cap_params = {'path': '.'}
                        
                        print(f"    Params: {cap_params}")
                        
                        # Execute the capability directly
                        result = await capability.execute(**cap_params)
                        
                        if result.success:
                            value = result.value
                            if isinstance(value, list):
                                print(f"    Result ({len(value)} items):")
                                for item in value[:20]:
                                    print(f"       - {item}")
                                if len(value) > 20:
                                    print(f"       ... and {len(value) - 20} more")
                            else:
                                print(f"    Result: {str(value)[:200]}")
                        else:
                            print(f"    Error: {result.error}")
                    
                    elif step.action == ActionType.REFLECT:
                        self._state = AgentState.REFLECTING
                        details_str = step.details if isinstance(step.details, str) else str(step.details)
                        print(f"  Reflecting: {details_str[:50]}...")
                
                # If we got here, plan didn't explicitly complete
                # Ask if we should continue
                self._state = AgentState.REFLECTING
                reflection = await self._gemini.reflect(
                    f"Completed iteration {self._iteration} of plan",
                    f"Executed {len(plan.steps)} steps",
                    was_success=True
                )
                
                if not reflection.get("should_retry", True):
                    # Store learning from success (SELF-EVOLUTION)
                    if self._memory:
                        try:
                            await self._memory.learn(
                                task=goal,
                                outcome="success",
                                lesson=f"Successfully completed using extensions: {extensions_created or 'none'}. Approach: {plan.analysis[:200]}"
                            )
                            print(f"  [Memory] Stored success learning")
                        except Exception as e:
                            print(f"  [Memory] Failed to store learning: {e}")
                    
                    return AgentResult(
                        success=True,
                        message="Plan executed",
                        extensions_created=extensions_created,
                        steps_taken=self._iteration
                    )
            
            # Max iterations reached
            return AgentResult(
                success=False,
                message=f"Safety limit ({safety_limit} iterations) reached. Task unusually long.",
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
