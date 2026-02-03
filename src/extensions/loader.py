"""Extension loader - dynamic loading and preparation of extensions."""

from typing import Any

from src.models.extension import ExtensionRecord
from src.capabilities.base import Capability


class ExtensionLoader:
    """Loads and prepares extensions for execution.
    
    This is responsible for:
    - Validating extension source code
    - Preparing capability bindings
    - Creating executable modules
    """
    
    def __init__(self):
        pass
    
    def validate_source(self, source_code: str) -> tuple[bool, str]:
        """Validate that source code is syntactically correct.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            compile(source_code, "<extension>", "exec")
            return True, ""
        except SyntaxError as e:
            return False, f"Syntax error at line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, f"Compilation error: {e}"
    
    def extract_required_capabilities(self, source_code: str) -> list[str]:
        """Extract capability names from the extension's main function signature.
        
        Extensions should have a main function like:
            def extension_main(fs_read, fs_write, net_fetch):
                ...
        
        The parameter names map to capabilities (underscores become dots).
        """
        import ast
        
        try:
            tree = ast.parse(source_code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "extension_main":
                    # Extract parameter names
                    params = [arg.arg for arg in node.args.args]
                    # Convert fs_read -> fs.read
                    return [p.replace("_", ".") for p in params]
            
            return []
            
        except Exception:
            return []
    
    def create_capability_bindings(
        self,
        extension: ExtensionRecord,
        available_capabilities: dict[str, Capability]
    ) -> tuple[dict[str, Any], list[str]]:
        """Create bindings from capability names to callable objects.
        
        Args:
            extension: The extension record
            available_capabilities: Available capabilities from the adapter
            
        Returns:
            Tuple of (bindings dict, list of missing capabilities)
        """
        bindings = {}
        missing = []
        
        for cap_name in extension.metadata.required_capabilities:
            if cap_name in available_capabilities:
                # Create a sync wrapper for the capability
                cap = available_capabilities[cap_name]
                
                # Wrapper that converts async to sync
                def make_wrapper(capability):
                    def wrapper(**kwargs):
                        import asyncio
                        result = asyncio.get_event_loop().run_until_complete(
                            capability.execute(**kwargs)
                        )
                        if result.success:
                            return result.value
                        else:
                            raise RuntimeError(f"Capability error: {result.error}")
                    return wrapper
                
                # Use underscores for binding name: fs.read -> fs_read
                binding_name = cap_name.replace(".", "_")
                bindings[binding_name] = make_wrapper(cap)
            else:
                missing.append(cap_name)
        
        return bindings, missing
    
    def prepare_for_execution(
        self,
        extension: ExtensionRecord,
        available_capabilities: dict[str, Capability]
    ) -> tuple[str, dict[str, Any], list[str]]:
        """Prepare an extension for execution.
        
        Returns:
            Tuple of (source_code, capability_bindings, missing_capabilities)
        """
        # Validate source
        is_valid, error = self.validate_source(extension.source_code)
        if not is_valid:
            raise ValueError(f"Invalid extension source: {error}")
        
        # Create bindings
        bindings, missing = self.create_capability_bindings(
            extension, available_capabilities
        )
        
        return extension.source_code, bindings, missing
