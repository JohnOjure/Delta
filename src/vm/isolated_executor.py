"""Subprocess-based executor for true isolation.

This module provides process-based execution with:
- True memory limits via resource.setrlimit
- CPU time limits
- Proper timeout enforcement
- Isolated address space
"""

import asyncio
import json
import multiprocessing
import os
import resource
import sys
import traceback
from typing import Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class IsolatedResult:
    """Result from isolated execution."""
    success: bool
    value: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0
    memory_used_mb: float = 0
    output: str = ""


def _set_resource_limits(cpu_seconds: float, memory_mb: int):
    """Set resource limits for the current process."""
    # CPU time limit
    cpu_limit = int(cpu_seconds)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit + 1))
    
    # Memory limit
    memory_bytes = memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    
    # No core dumps
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    
    # Limit number of processes (prevent fork bombs)
    resource.setrlimit(resource.RLIMIT_NPROC, (10, 10))


def _execute_in_subprocess(
    source_code: str,
    bindings_json: str,
    cpu_seconds: float,
    memory_mb: int,
    result_queue: multiprocessing.Queue
):
    """Execute code in an isolated subprocess.
    
    This function runs in a separate process with resource limits.
    """
    import time
    start = time.time()
    
    try:
        # Set resource limits
        _set_resource_limits(cpu_seconds, memory_mb)
        
        # Deserialize bindings (note: capabilities can't be passed directly)
        # For full capability support, we'd need IPC
        bindings = json.loads(bindings_json) if bindings_json else {}
        
        # Create restricted globals
        safe_builtins = {
            'abs': abs, 'all': all, 'any': any, 'bool': bool,
            'dict': dict, 'enumerate': enumerate, 'filter': filter,
            'float': float, 'frozenset': frozenset, 'int': int,
            'isinstance': isinstance, 'issubclass': issubclass,
            'iter': iter, 'len': len, 'list': list, 'map': map,
            'max': max, 'min': min, 'next': next, 'range': range,
            'repr': repr, 'reversed': reversed, 'round': round,
            'set': set, 'slice': slice, 'sorted': sorted, 'str': str,
            'sum': sum, 'tuple': tuple, 'type': type, 'zip': zip,
            'print': lambda *args, **kwargs: None,  # Capture print
            'True': True, 'False': False, 'None': None,
        }
        
        exec_globals = {"__builtins__": safe_builtins}
        exec_globals.update(bindings)
        exec_locals = {}
        
        # Compile and execute
        code = compile(source_code, "<extension>", "exec")
        exec(code, exec_globals, exec_locals)
        
        # Look for result
        result = exec_locals.get("result", exec_globals.get("result"))
        
        # If there's extension_main, call it
        if "extension_main" in exec_locals or "extension_main" in exec_globals:
            main_func = exec_locals.get("extension_main") or exec_globals.get("extension_main")
            result = main_func()
        
        elapsed = (time.time() - start) * 1000
        
        # Get memory usage
        usage = resource.getrusage(resource.RUSAGE_SELF)
        memory_mb = usage.ru_maxrss / 1024  # KB to MB
        
        # Serialize result
        try:
            result_json = json.dumps(result)
        except:
            result_json = json.dumps(str(result))
        
        result_queue.put({
            "success": True,
            "value": result_json,
            "execution_time_ms": elapsed,
            "memory_used_mb": memory_mb
        })
        
    except MemoryError:
        result_queue.put({
            "success": False,
            "error": f"Memory limit exceeded ({memory_mb}MB)"
        })
    except Exception as e:
        result_queue.put({
            "success": False,
            "error": f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        })


class IsolatedExecutor:
    """Executor that runs code in isolated subprocesses.
    
    Provides true isolation with:
    - Separate process = separate address space
    - Resource limits via setrlimit
    - Timeout via process termination
    """
    
    def __init__(
        self,
        cpu_time_seconds: float = 30.0,
        memory_mb: int = 128,
        timeout_seconds: float = 60.0
    ):
        self._cpu_seconds = cpu_time_seconds
        self._memory_mb = memory_mb
        self._timeout = timeout_seconds
    
    async def execute(
        self,
        source_code: str,
        bindings: dict = None
    ) -> IsolatedResult:
        """Execute code in an isolated subprocess.
        
        Args:
            source_code: Python code to execute
            bindings: Simple JSON-serializable bindings
            
        Returns:
            IsolatedResult with execution outcome
        """
        start = datetime.utcnow()
        
        # Serialize bindings (capabilities not supported - use regular executor for those)
        try:
            bindings_json = json.dumps(bindings or {})
        except:
            bindings_json = "{}"
        
        # Create result queue
        result_queue = multiprocessing.Queue()
        
        # Create subprocess
        process = multiprocessing.Process(
            target=_execute_in_subprocess,
            args=(source_code, bindings_json, self._cpu_seconds, self._memory_mb, result_queue)
        )
        
        try:
            process.start()
            
            # Wait for result with timeout
            loop = asyncio.get_event_loop()
            
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: result_queue.get(timeout=self._timeout)),
                    timeout=self._timeout
                )
            except (asyncio.TimeoutError, Exception):
                # Process didn't complete in time
                process.terminate()
                process.join(timeout=1)
                if process.is_alive():
                    process.kill()
                
                return IsolatedResult(
                    success=False,
                    error=f"Execution timed out after {self._timeout}s",
                    execution_time_ms=(datetime.utcnow() - start).total_seconds() * 1000
                )
            
            # Process completed
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000
            
            if result.get("success"):
                value = result.get("value")
                try:
                    value = json.loads(value)
                except:
                    pass
                
                return IsolatedResult(
                    success=True,
                    value=value,
                    execution_time_ms=result.get("execution_time_ms", elapsed),
                    memory_used_mb=result.get("memory_used_mb", 0)
                )
            else:
                return IsolatedResult(
                    success=False,
                    error=result.get("error", "Unknown error"),
                    execution_time_ms=elapsed
                )
        
        finally:
            # Cleanup
            if process.is_alive():
                process.terminate()
                process.join(timeout=1)
                if process.is_alive():
                    process.kill()
    
    async def execute_with_capabilities(
        self,
        source_code: str,
        capabilities: dict
    ) -> IsolatedResult:
        """Execute code that needs capabilities.
        
        Note: True capability support requires IPC between processes.
        For now, this wraps the code to simulate capability calls.
        
        For full capability support, use the regular Executor class.
        """
        # For extensions that need real capabilities, fall back to regular executor
        # This isolated executor is best for compute-heavy, untrusted code
        return IsolatedResult(
            success=False,
            error="Capability support not available in isolated executor. Use regular Executor."
        )
    
    def validate(self, source_code: str) -> tuple[bool, list[str]]:
        """Validate source code for common issues."""
        issues = []
        
        # Check for syntax errors
        try:
            compile(source_code, "<extension>", "exec")
        except SyntaxError as e:
            issues.append(f"Syntax error: {e}")
            return False, issues
        
        # Check for dangerous patterns
        dangerous = ["import os", "import subprocess", "import sys", "__import__", "eval(", "exec("]
        for pattern in dangerous:
            if pattern in source_code:
                issues.append(f"Dangerous pattern: {pattern}")
        
        # Check for extension_main
        if "extension_main" not in source_code:
            issues.append("Missing extension_main function")
        
        return len(issues) == 0, issues
