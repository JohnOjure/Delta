"""Pytest configuration and shared fixtures."""

import sys
from pathlib import Path

# Add project root to Python path so 'src' module is findable
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import tempfile
from typing import Generator
import pytest
import pytest_asyncio


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_db(temp_dir: Path) -> Path:
    """Create a path for a temporary database."""
    return temp_dir / "test.db"


@pytest.fixture
def sample_extension_code() -> str:
    """Sample valid extension code."""
    return '''
def extension_main(fs_read):
    """Sample extension that reads a file."""
    content = fs_read(path="test.txt")
    return {"content": content, "length": len(content)}
'''


@pytest.fixture
def invalid_extension_code() -> str:
    """Sample invalid extension code (uses imports)."""
    return '''
import os

def extension_main():
    return os.listdir(".")
'''


@pytest.fixture
def mock_capability():
    """Create a mock capability for testing."""
    from src.models.capability import CapabilityResult, CapabilityStatus
    
    class MockCapability:
        def __init__(self, name: str, return_value=None):
            self.name = name
            self.calls = []
            self._return_value = return_value
        
        async def execute(self, **kwargs):
            self.calls.append(kwargs)
            return CapabilityResult(
                status=CapabilityStatus.SUCCESS,
                value=self._return_value or f"mock result for {self.name}"
            )
        
        @property
        def descriptor(self):
            from src.models.capability import CapabilityDescriptor
            return CapabilityDescriptor(
                name=self.name,
                description=f"Mock {self.name} capability",
                parameters=[]
            )
    
    return MockCapability


@pytest.fixture
def sample_extension_metadata():
    """Create sample extension metadata."""
    from src.models.extension import ExtensionMetadata
    return ExtensionMetadata(
        name="test_extension",
        version="1.0.0",
        description="A test extension",
        required_capabilities=["fs.read"],
        tags=["test", "sample"]
    )
