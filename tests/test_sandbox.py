"""Tests for Sandbox."""

import pytest
from src.vm.sandbox import Sandbox, SandboxError


class TestSandbox:
    """Test suite for Sandbox execution."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sandbox = Sandbox()
    
    def test_execute_simple_code(self):
        """Test executing simple code with extension_main."""
        code = """
def extension_main():
    return 1 + 1
"""
        result, _ = self.sandbox.execute(code, {})
        assert result == 2
    
    def test_execute_with_return(self):
        """Test code that returns a dict."""
        code = """
def extension_main():
    return {"value": 42}
"""
        result, _ = self.sandbox.execute(code, {})
        assert result == {"value": 42}
    
    def test_execute_with_bindings(self):
        """Test executing code with capability bindings."""
        code = """
def extension_main(my_cap):
    return my_cap()
"""
        call_count = [0]
        def mock_capability():
            call_count[0] += 1
            return "mocked"
        
        result, _ = self.sandbox.execute(code, {"my_cap": mock_capability})
        
        assert call_count[0] == 1
        assert result == "mocked"
    
    def test_validate_valid_code(self):
        """Test validating correct extension code."""
        code = """
def extension_main(fs_read):
    content = fs_read(path="test.txt")
    return {"content": content}
"""
        is_valid, issues = self.sandbox.validate_code(code)
        assert is_valid
        assert len(issues) == 0
    
    def test_validate_missing_extension_main(self):
        """Test validation fails without extension_main."""
        code = """
def other_function():
    return 42
"""
        is_valid, issues = self.sandbox.validate_code(code)
        assert not is_valid
        assert any("extension_main" in issue.lower() for issue in issues)
    
    def test_validate_syntax_error(self):
        """Test validation catches syntax errors."""
        code = """
def extension_main(:
    return 42
"""
        is_valid, issues = self.sandbox.validate_code(code)
        assert not is_valid
        assert any("syntax" in issue.lower() for issue in issues)
    
    def test_blocked_import(self):
        """Test that imports are blocked or cause validation issues."""
        code = """
import os

def extension_main():
    return os.listdir(".")
"""
        # RestrictedPython handles import blocking
        is_valid, issues = self.sandbox.validate_code(code)
        # Either validation fails or execution should fail
        if is_valid:
            # If validation passes, try execution - it should fail
            with pytest.raises(SandboxError):
                self.sandbox.execute(code, {})
    
    def test_blocked_builtins(self):
        """Test that dangerous builtins are blocked."""
        code = """
def extension_main():
    return eval("1+1")
"""
        # Should either fail validation or raise error on execution
        is_valid, issues = self.sandbox.validate_code(code)
        if is_valid:
            # If validation passes, execution should fail
            with pytest.raises(SandboxError):
                self.sandbox.execute(code, {})
    
    def test_allowed_safe_operations(self):
        """Test that safe operations are allowed."""
        code = """
def extension_main():
    data = {"key": "value"}
    items = [1, 2, 3]
    text = "hello".upper()
    return {
        "dict": data,
        "list": items,
        "string": text,
        "math": 10 * 5
    }
"""
        is_valid, _ = self.sandbox.validate_code(code)
        assert is_valid
        
        result, _ = self.sandbox.execute(code, {})
        
        assert result["dict"] == {"key": "value"}
        assert result["list"] == [1, 2, 3]
        assert result["string"] == "HELLO"
        assert result["math"] == 50
