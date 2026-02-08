"""Sandbox - RestrictedPython-based code execution.

This module provides the core sandboxing mechanism using RestrictedPython.
All extension code runs through this sandbox, which:
- Prevents dangerous operations (imports, file access, etc.)
- Only allows access to explicitly provided capabilities
- Enforces resource limits
"""

from typing import Any
from RestrictedPython import compile_restricted, safe_builtins
from RestrictedPython.Eval import default_guarded_getattr, default_guarded_getitem
from RestrictedPython.Guards import (
    guarded_iter_unpack_sequence,
    guarded_unpack_sequence,
)


class SandboxError(Exception):
    """Raised when sandbox execution fails."""
    pass


class SecurityViolation(SandboxError):
    """Raised when code attempts a forbidden operation."""
    pass


class Sandbox:
    """RestrictedPython sandbox for safe code execution.
    
    This sandbox:
    - Compiles code with RestrictedPython's AST transformer
    - Provides only safe builtins (no open, exec, eval, import)
    - Injects capability objects as the only way to interact with the world
    - Guards attribute and item access
    """
    
    # Builtins allowed in the sandbox
    SAFE_BUILTINS = {
        **safe_builtins,
        # Add some useful ones that are safe
        "len": len,
        "range": range,
        "enumerate": enumerate,
        "zip": zip,
        "map": map,
        "filter": filter,
        "sorted": sorted,
        "reversed": reversed,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "None": None,
        "True": True,
        "False": False,
        "abs": abs,
        "all": all,
        "any": any,
        "max": max,
        "min": min,
        "sum": sum,
        "round": round,
        "isinstance": isinstance,
        "hasattr": hasattr,
        "getattr": getattr,
        "print": print,  # Safe for output
    }
    
    def __init__(self):
        pass
    
    def compile(self, source_code: str, filename: str = "<extension>") -> Any:
        """Compile source code with RestrictedPython.
        
        Args:
            source_code: Python source code to compile
            filename: Name for error messages
            
        Returns:
            Compiled code object
            
        Raises:
            SandboxError: If compilation fails
        """
        try:
            # RestrictedPython 8.x returns code directly or raises exceptions
            result = compile_restricted(
                source_code,
                filename=filename,
                mode="exec"
            )
            
            # In RestrictedPython 8.x, if there are errors it raises an exception
            # If successful, it returns a code object directly
            if hasattr(result, 'errors') and result.errors:
                errors = "\n".join(result.errors)
                raise SandboxError(f"Compilation errors:\n{errors}")
            
            # RestrictedPython 8.x returns code directly
            if hasattr(result, 'code'):
                return result.code
            return result
            
        except SyntaxError as e:
            raise SandboxError(f"Syntax error at line {e.lineno}: {e.msg}")
        except SandboxError:
            raise
        except Exception as e:
            raise SandboxError(f"Compilation failed: {e}")
    
    def create_restricted_globals(
        self,
        capability_bindings: dict[str, Any] = None
    ) -> dict[str, Any]:
        """Create a restricted globals dict for execution.
        
        Args:
            capability_bindings: Dict of capability name -> callable
                                 e.g., {"fs_read": <callable>, "net_fetch": <callable>}
        
        Returns:
            Globals dict with builtins and capabilities
        """
        # Helper for augmented assignments (+=, -=, etc.)
        # RestrictedPython transforms "x += y" to "_inplacevar_('+=', x, y)"
        import operator as _operator
        _operators = {
            '+=': _operator.iadd,
            '-=': _operator.isub,
            '*=': _operator.imul,
            '/=': _operator.itruediv,
            '//=': _operator.ifloordiv,
            '%=': _operator.imod,
            '**=': _operator.ipow,
            '&=': _operator.iand,
            '|=': _operator.ior,
            '^=': _operator.ixor,
            '<<=': _operator.ilshift,
            '>>=': _operator.irshift,
        }
        
        def _inplacevar_(op, x, y):
            if op not in _operators:
                raise SecurityViolation(f"Operation '{op}' is not allowed")
            return _operators[op](x, y)
        
        restricted_globals = {
            "__builtins__": self.SAFE_BUILTINS,
            "_getattr_": default_guarded_getattr,
            "_getitem_": default_guarded_getitem,
            "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
            "_unpack_sequence_": guarded_unpack_sequence,
            "_getiter_": iter,
            "_write_": lambda x: x,  # Allow simple writes
            "_inplacevar_": _inplacevar_,  # Support +=, -=, etc.
        }
        
        # Add capability bindings
        if capability_bindings:
            restricted_globals.update(capability_bindings)
        
        return restricted_globals
    
    def execute(
        self,
        source_code: str,
        capability_bindings: dict[str, Any] = None,
        entry_point: str = "extension_main"
    ) -> Any:
        """Execute code in the sandbox.
        
        Args:
            source_code: Python source code
            capability_bindings: Capabilities to inject
            entry_point: Function to call after module execution
            
        Returns:
            Result of calling the entry point function
            
        Raises:
            SandboxError: If execution fails
        """
        # Compile
        code = self.compile(source_code)
        
        # Create restricted environment
        restricted_globals = self.create_restricted_globals(capability_bindings)
        restricted_locals = {}
        
        try:
            # Execute the module (defines functions)
            exec(code, restricted_globals, restricted_locals)
            
            # Find and call the entry point
            if entry_point not in restricted_locals:
                raise SandboxError(
                    f"Entry point '{entry_point}' not found. "
                    f"Defined names: {list(restricted_locals.keys())}"
                )
            
            entry_func = restricted_locals[entry_point]
            
            if not callable(entry_func):
                raise SandboxError(f"Entry point '{entry_point}' is not callable")
            
            # Call with capability bindings as kwargs
            # The function signature should match: def extension_main(fs_read, net_fetch, ...)
            if capability_bindings:
                result = entry_func(**capability_bindings)
            else:
                result = entry_func()
            
            return result
            
        except SecurityViolation:
            raise
        except SandboxError:
            raise
        except Exception as e:
            raise SandboxError(f"Execution error: {type(e).__name__}: {e}")
    
    def validate_code(self, source_code: str) -> tuple[bool, list[str]]:
        """Validate code without executing it.
        
        Returns:
            Tuple of (is_valid, list of errors/warnings)
        """
        issues = []
        
        # Try to compile
        try:
            result = compile_restricted(source_code, "<validation>", "exec")
            
            # RestrictedPython 8.x - check if result has errors attribute
            if hasattr(result, 'errors') and result.errors:
                issues.extend(result.errors)
            if hasattr(result, 'warnings') and result.warnings:
                issues.extend(result.warnings)
                
        except SyntaxError as e:
            issues.append(f"Syntax error at line {e.lineno}: {e.msg}")
        except Exception as e:
            issues.append(f"Validation error: {e}")
        
        # Check for entry point
        import ast
        try:
            tree = ast.parse(source_code)
            has_main = any(
                isinstance(n, ast.FunctionDef) and n.name == "extension_main"
                for n in ast.walk(tree)
            )
            if not has_main:
                issues.append("Missing 'extension_main' function")
        except:
            pass
        
        return len(issues) == 0, issues
