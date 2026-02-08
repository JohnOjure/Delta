"""Tests for Executor."""

import pytest
import pytest_asyncio
from pathlib import Path

from src.vm.executor import Executor, ExecutionResult
from src.models.environment import ResourceLimits
from src.models.extension import ExtensionMetadata, ExtensionRecord


@pytest.fixture
def executor():
    """Create an executor with default limits."""
    return Executor(ResourceLimits(cpu_time_seconds=5.0))


@pytest.fixture
def make_extension():
    """Factory for creating extension records."""
    def _make(name: str, code: str, capabilities: list[str] = None):
        return ExtensionRecord(
            metadata=ExtensionMetadata(
                name=name,
                version="1.0.0",
                description=f"Test extension: {name}",
                required_capabilities=capabilities or [],
                tags=[]
            ),
            source_code=code,
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            execution_count=0
        )
    return _make


@pytest.mark.asyncio
async def test_execute_simple_extension(executor, make_extension):
    """Test executing a simple extension."""
    code = """
def extension_main():
    return {"message": "Hello from extension!"}
"""
    extension = make_extension("simple", code)
    
    result = await executor.execute(extension, {})
    
    assert result.success
    assert result.value == {"message": "Hello from extension!"}


@pytest.mark.asyncio
async def test_execute_with_capability(executor, make_extension):
    """Test executing extension that uses a capability."""
    code = """
def extension_main(fs_read):
    content = fs_read(path="test.txt")
    return {"content": content}
"""
    extension = make_extension("with_cap", code, ["fs.read"])
    
    # Mock capability - just a function that returns the expected value
    def mock_fs_read(**kwargs):
        return "file contents"
    
    result = await executor.execute(extension, {"fs.read": mock_fs_read})
    
    assert result.success
    assert result.value == {"content": "file contents"}


@pytest.mark.asyncio
async def test_execute_missing_capability(executor, make_extension):
    """Test execution fails when required capability is missing."""
    code = """
def extension_main(fs_read):
    return fs_read(path="test.txt")
"""
    extension = make_extension("missing_cap", code, ["fs.read"])
    
    result = await executor.execute(extension, {})  # No capabilities provided
    
    assert not result.success
    assert "missing" in result.error.lower() or "capability" in result.error.lower()


@pytest.mark.asyncio
async def test_execute_with_error(executor, make_extension):
    """Test handling of extension that raises an error."""
    code = """
def extension_main():
    raise ValueError("Test error")
"""
    extension = make_extension("error", code)
    
    result = await executor.execute(extension, {})
    
    assert not result.success
    assert "error" in result.error.lower()


@pytest.mark.asyncio
async def test_execute_raw_code(executor):
    """Test executing raw code with extension_main."""
    code = """
def extension_main():
    return 1 + 2 + 3
"""
    result = await executor.execute_raw(code)
    
    assert result.success
    assert result.value == 6


@pytest.mark.asyncio
async def test_execution_timeout():
    """Test that long-running code times out."""
    executor = Executor(ResourceLimits(cpu_time_seconds=0.5))
    
    code = """
def extension_main():
    # This would run forever without timeout
    while True:
        pass
"""
    result = await executor.execute_raw(code)
    
    # Should timeout
    assert not result.success
    assert "timeout" in result.error.lower() or "time" in result.error.lower()


def test_validate_code(executor):
    """Test code validation."""
    valid_code = """
def extension_main():
    return 42
"""
    is_valid, issues = executor.validate(valid_code)
    assert is_valid
    
    # Code without extension_main should be invalid
    invalid_code = """
def some_other_function():
    return 42
"""
    is_valid, issues = executor.validate(invalid_code)
    assert not is_valid


@pytest.mark.asyncio
async def test_execution_time_tracking(executor, make_extension):
    """Test that execution time is tracked."""
    code = """
def extension_main():
    total = 0
    for i in range(1000):
        total += i
    return total
"""
    extension = make_extension("timed", code)
    
    result = await executor.execute(extension, {})
    
    assert result.success
    assert result.execution_time_ms > 0
