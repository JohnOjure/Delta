"""Executor - manages extension execution with resource limits.

This module handles:
- Running extensions in isolated contexts
- Enforcing timeouts
- Capturing output and results
- Error handling
"""

import asyncio
import traceback
from typing import Any
from dataclasses import dataclass
from datetime import datetime

from src.models.extension import ExtensionRecord
from src.models.environment import ResourceLimits
from src.capabilities.base import Capability
from src.extensions.loader import ExtensionLoader
from .sandbox import Sandbox, SandboxError


@dataclass
class ExecutionResult:
    """Result of executing an extension."""
    success: bool
    value: Any = None
    error: str | None = None
    execution_time_ms: float = 0
    output: str = ""
    

class ExecutionTimeout(Exception):
    """Raised when execution exceeds time limit."""
    pass


class Executor:
    """Executes extensions in the sandbox with resource limits.
    
    This is the bridge between the agent and the sandbox.
    It handles:
    - Loading extensions
    - Setting up capabilities
    - Enforcing resource limits
    - Capturing results
    """
    
    def __init__(self, limits: ResourceLimits | None = None, unrestricted: bool = True):
        self._limits = limits or ResourceLimits()
        self._unrestricted = unrestricted
        self._sandbox = Sandbox(unrestricted=unrestricted)
        self._loader = ExtensionLoader()
    
    async def execute(
        self,
        extension: ExtensionRecord,
        available_capabilities: dict[str, Capability]
    ) -> ExecutionResult:
        """Execute an extension with the given capabilities.
        
        Args:
            extension: The extension to execute
            available_capabilities: Capabilities from the adapter
            
        Returns:
            ExecutionResult with success/failure and value/error
        """
        start_time = datetime.utcnow()
        
        try:
            # Prepare extension (validate + create bindings)
            source_code, bindings, missing = self._loader.prepare_for_execution(
                extension, available_capabilities
            )
            
            if missing:
                return ExecutionResult(
                    success=False,
                    error=f"Missing required capabilities: {missing}"
                )
            
            # Run in sandbox with timeout
            result = await self._execute_with_timeout(source_code, bindings)
            
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return ExecutionResult(
                success=True,
                value=result,
                execution_time_ms=execution_time
            )
            
        except SandboxError as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time
            )
        except ExecutionTimeout:
            return ExecutionResult(
                success=False,
                error=f"Execution timed out after {self._limits.cpu_time_seconds}s"
            )
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            return ExecutionResult(
                success=False,
                error=f"Unexpected error: {type(e).__name__}: {e}\n{traceback.format_exc()}",
                execution_time_ms=execution_time
            )
    
    async def _execute_with_timeout(
        self,
        source_code: str,
        bindings: dict[str, Any]
    ) -> Any:
        """Execute code with a timeout using process isolation.
        
        Uses multiprocessing to run code in a separate process that can be
        terminated if it exceeds the timeout. This works for CPU-bound code
        like infinite loops, unlike thread-based approaches.
        """
        import multiprocessing
        import queue
        
        def _run_in_process(result_queue, source_code, bindings, unrestricted):
            """Function to run in the separate process."""
            try:
                # Create a new Sandbox instance in this process
                # (can't share the parent's instance due to pickling)
                from .sandbox import Sandbox
                sandbox = Sandbox(unrestricted=unrestricted)
                result = sandbox.execute(source_code, bindings)
                result_queue.put(("success", result))
            except Exception as e:
                import traceback
                result_queue.put(("error", f"{type(e).__name__}: {e}\n{traceback.format_exc()}"))
        
        # Create a queue for inter-process communication
        result_queue = multiprocessing.Queue()
        
        # Start the process
        process = multiprocessing.Process(
            target=_run_in_process,
            args=(result_queue, source_code, bindings, self._unrestricted)
        )
        process.start()
        
        # Wait for the process with timeout
        process.join(timeout=self._limits.cpu_time_seconds)
        
        if process.is_alive():
            # Process is still running - timeout occurred
            process.terminate()
            process.join(timeout=1.0)  # Give it a second to terminate gracefully
            if process.is_alive():
                process.kill()  # Force kill if terminate didn't work
            raise ExecutionTimeout()
        
        # Process completed - get the result
        try:
            status, result = result_queue.get_nowait()
            if status == "success":
                return result
            else:
                raise SandboxError(result)
        except queue.Empty:
            # Process exited without putting anything in the queue
            raise SandboxError("Process terminated without returning a result")
    
    def validate(self, source_code: str) -> tuple[bool, list[str]]:
        """Validate extension source code.
        
        Returns:
            Tuple of (is_valid, list of issues)
        """
        return self._sandbox.validate_code(source_code)
    
    async def execute_raw(
        self,
        source_code: str,
        capability_bindings: dict[str, Any] = None
    ) -> ExecutionResult:
        """Execute raw source code (not from registry).
        
        Used for one-off execution during development/testing.
        """
        start_time = datetime.utcnow()
        
        try:
            result = await self._execute_with_timeout(
                source_code, 
                capability_bindings or {}
            )
            
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return ExecutionResult(
                success=True,
                value=result,
                execution_time_ms=execution_time
            )
            
        except SandboxError as e:
            return ExecutionResult(success=False, error=str(e))
        except ExecutionTimeout:
            return ExecutionResult(
                success=False,
                error=f"Execution timed out after {self._limits.cpu_time_seconds}s"
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Unexpected error: {type(e).__name__}: {e}"
            )
