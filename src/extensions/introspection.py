"""Extension introspection - read-only access to extension internals."""

import ast
from typing import Any

from src.models.extension import ExtensionRecord


class ExtensionIntrospector:
    """Provides read-only introspection into extensions.
    
    Used by the agent to:
    - Understand existing extensions
    - Debug failures
    - Plan improvements
    """
    
    def get_source_code(self, extension: ExtensionRecord) -> str:
        """Get the source code of an extension."""
        return extension.source_code
    
    def get_functions(self, extension: ExtensionRecord) -> list[dict[str, Any]]:
        """Extract function definitions from an extension.
        
        Returns:
            List of {name, args, docstring, lineno}
        """
        try:
            tree = ast.parse(extension.source_code)
            functions = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append({
                        "name": node.name,
                        "args": [arg.arg for arg in node.args.args],
                        "docstring": ast.get_docstring(node),
                        "lineno": node.lineno,
                        "is_main": node.name == "extension_main"
                    })
            
            return functions
            
        except Exception:
            return []
    
    def get_imports(self, extension: ExtensionRecord) -> list[str]:
        """Extract import statements from an extension.
        
        Note: In sandboxed execution, imports are blocked.
        This is for analysis only.
        """
        try:
            tree = ast.parse(extension.source_code)
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    imports.append(f"{node.module}")
            
            return imports
            
        except Exception:
            return []
    
    def get_execution_history(self, extension: ExtensionRecord) -> dict[str, Any]:
        """Get execution history summary."""
        return {
            "execution_count": extension.execution_count,
            "last_executed_at": str(extension.last_executed_at) if extension.last_executed_at else None,
            "last_result": extension.last_result,
            "last_error": extension.last_error,
            "has_errors": extension.last_error is not None
        }
    
    def analyze_complexity(self, extension: ExtensionRecord) -> dict[str, Any]:
        """Analyze the complexity of an extension.
        
        Returns basic metrics for the agent to understand.
        """
        try:
            tree = ast.parse(extension.source_code)
            
            line_count = len(extension.source_code.split('\n'))
            function_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
            class_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
            
            # Count control flow statements
            loops = sum(1 for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While)))
            conditionals = sum(1 for n in ast.walk(tree) if isinstance(n, ast.If))
            
            return {
                "line_count": line_count,
                "function_count": function_count,
                "class_count": class_count,
                "loop_count": loops,
                "conditional_count": conditionals,
                "estimated_complexity": loops + conditionals + function_count
            }
            
        except Exception:
            return {"error": "Failed to analyze"}
    
    def to_prompt_string(self, extension: ExtensionRecord) -> str:
        """Format extension info for LLM prompts."""
        functions = self.get_functions(extension)
        history = self.get_execution_history(extension)
        complexity = self.analyze_complexity(extension)
        
        funcs_str = "\n".join(
            f"  - {f['name']}({', '.join(f['args'])})"
            + (f": {f['docstring'][:50]}..." if f['docstring'] else "")
            for f in functions
        )
        
        return f"""
### Extension: {extension.metadata.name} (v{extension.metadata.version})
**Description:** {extension.metadata.description}
**Required Capabilities:** {', '.join(extension.metadata.required_capabilities)}
**Tags:** {', '.join(extension.metadata.tags)}

**Functions:**
{funcs_str}

**Execution History:**
- Run {history['execution_count']} times
- Last run: {history['last_executed_at'] or 'Never'}
- Last error: {history['last_error'] or 'None'}

**Complexity:** {complexity.get('estimated_complexity', 'N/A')} ({complexity.get('line_count', 0)} lines)

**Source Code:**
```python
{extension.source_code}
```
"""
