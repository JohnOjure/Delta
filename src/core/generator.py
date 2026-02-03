"""Extension generator - creates new extensions from LLM output."""

from src.models.extension import ExtensionMetadata
from src.vm.sandbox import Sandbox


class ExtensionGenerator:
    """Generates and validates extension code.
    
    Works with the LLM's code generation output to create
    valid, safe extensions.
    """
    
    def __init__(self):
        self._sandbox = Sandbox()
    
    def parse_generation(self, llm_response: dict) -> tuple[ExtensionMetadata, str]:
        """Parse LLM code generation response.
        
        Args:
            llm_response: Dict with name, description, code, etc.
            
        Returns:
            Tuple of (ExtensionMetadata, source_code)
        """
        name = llm_response.get("name", "unnamed_extension")
        description = llm_response.get("description", "No description")
        version = llm_response.get("version", "1.0.0")
        tags = llm_response.get("tags", [])
        code = llm_response.get("code", "")
        
        # Extract required capabilities from code
        required_caps = self._extract_capabilities_from_code(code)
        
        metadata = ExtensionMetadata(
            name=name,
            version=version,
            description=description,
            required_capabilities=required_caps,
            tags=tags
        )
        
        return metadata, code
    
    def _extract_capabilities_from_code(self, source_code: str) -> list[str]:
        """Extract capability names from extension_main parameters."""
        import ast
        
        try:
            tree = ast.parse(source_code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "extension_main":
                    params = [arg.arg for arg in node.args.args]
                    # Convert fs_read -> fs.read
                    return [p.replace("_", ".") for p in params]
            
            return []
        except:
            return []
    
    def validate(self, source_code: str) -> tuple[bool, list[str]]:
        """Validate extension code.
        
        Checks:
        - Syntax correctness
        - RestrictedPython compliance
        - Has extension_main function
        
        Returns:
            Tuple of (is_valid, list of issues)
        """
        return self._sandbox.validate_code(source_code)
    
    def fix_common_issues(self, source_code: str) -> str:
        """Attempt to fix common issues in generated code.
        
        This is a best-effort cleanup for LLM-generated code.
        """
        lines = source_code.split("\n")
        fixed_lines = []
        
        for line in lines:
            # Remove markdown code fences if present
            if line.strip().startswith("```"):
                continue
            
            # Remove import statements (not allowed in sandbox)
            if line.strip().startswith("import ") or line.strip().startswith("from "):
                fixed_lines.append(f"# Removed: {line}")
                continue
            
            fixed_lines.append(line)
        
        return "\n".join(fixed_lines)
    
    def create_template(self, capabilities: list[str], description: str) -> str:
        """Create a template extension with the given capabilities.
        
        Useful for helping the LLM understand the expected format.
        """
        params = ", ".join(c.replace(".", "_") for c in capabilities)
        
        return f'''def extension_main({params}):
    """
    {description}
    
    Available capabilities (passed as parameters):
    {chr(10).join(f"    - {c}" for c in capabilities)}
    
    Returns:
        Result dict or value
    """
    # TODO: Implement
    result = {{}}
    
    return result
'''
