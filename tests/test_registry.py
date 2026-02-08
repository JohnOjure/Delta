"""Tests for ExtensionRegistry."""

import pytest
import pytest_asyncio
from pathlib import Path

from src.extensions.registry import ExtensionRegistry
from src.models.extension import ExtensionMetadata


@pytest.mark.asyncio
async def test_register_extension(temp_db: Path, sample_extension_code: str):
    """Test registering a new extension."""
    registry = ExtensionRegistry(temp_db)
    
    metadata = ExtensionMetadata(
        name="test_ext",
        version="1.0.0",
        description="Test extension",
        required_capabilities=["fs.read"],
        tags=["test"]
    )
    
    record = await registry.register(metadata, sample_extension_code)
    
    assert record is not None
    assert record.metadata.name == "test_ext"
    assert record.metadata.version == "1.0.0"
    assert record.source_code == sample_extension_code


@pytest.mark.asyncio
async def test_get_extension_by_name(temp_db: Path, sample_extension_code: str):
    """Test retrieving an extension by name."""
    registry = ExtensionRegistry(temp_db)
    
    metadata = ExtensionMetadata(
        name="retrieval_test",
        version="1.0.0",
        description="Test",
        required_capabilities=[],
        tags=[]
    )
    
    await registry.register(metadata, sample_extension_code)
    
    # Retrieve it
    result = await registry.get_by_name("retrieval_test")
    
    assert result is not None
    assert result.metadata.name == "retrieval_test"


@pytest.mark.asyncio
async def test_get_nonexistent_extension(temp_db: Path):
    """Test retrieving an extension that doesn't exist."""
    registry = ExtensionRegistry(temp_db)
    
    result = await registry.get_by_name("nonexistent")
    
    assert result is None


@pytest.mark.asyncio
async def test_list_all_extensions(temp_db: Path, sample_extension_code: str):
    """Test listing all extensions."""
    registry = ExtensionRegistry(temp_db)
    
    # Register multiple extensions
    for i in range(3):
        metadata = ExtensionMetadata(
            name=f"ext_{i}",
            version="1.0.0",
            description=f"Extension {i}",
            required_capabilities=[],
            tags=[]
        )
        await registry.register(metadata, sample_extension_code)
    
    # List all
    extensions = await registry.list_all()
    
    assert len(extensions) == 3
    names = [e.metadata.name for e in extensions]
    assert "ext_0" in names
    assert "ext_1" in names
    assert "ext_2" in names


@pytest.mark.asyncio
async def test_update_extension(temp_db: Path, sample_extension_code: str):
    """Test updating an existing extension."""
    registry = ExtensionRegistry(temp_db)
    
    metadata = ExtensionMetadata(
        name="update_test",
        version="1.0.0",
        description="Original",
        required_capabilities=[],
        tags=[]
    )
    
    await registry.register(metadata, sample_extension_code)
    
    # Update with new version
    updated_metadata = ExtensionMetadata(
        name="update_test",
        version="2.0.0",
        description="Updated",
        required_capabilities=[],
        tags=[]
    )
    
    await registry.register(updated_metadata, "def extension_main(): return 'v2'")
    
    # Retrieve and verify
    result = await registry.get_by_name("update_test")
    
    assert result.metadata.version == "2.0.0"
    assert result.metadata.description == "Updated"


@pytest.mark.asyncio
async def test_search_extensions(temp_db: Path, sample_extension_code: str):
    """Test searching extensions by query."""
    registry = ExtensionRegistry(temp_db)
    
    # Register extensions with different descriptions
    metadata1 = ExtensionMetadata(
        name="file_reader",
        version="1.0.0",
        description="Reads files from disk",
        required_capabilities=["fs.read"],
        tags=["file", "read"]
    )
    await registry.register(metadata1, sample_extension_code)
    
    metadata2 = ExtensionMetadata(
        name="web_fetcher",
        version="1.0.0",
        description="Fetches data from web",
        required_capabilities=["net.fetch"],
        tags=["web", "http"]
    )
    await registry.register(metadata2, sample_extension_code)
    
    # Search for file-related
    results = await registry.search("file read")
    
    assert len(results) >= 1
    assert any(r.metadata.name == "file_reader" for r in results)


@pytest.mark.asyncio
async def test_record_execution(temp_db: Path, sample_extension_code: str):
    """Test recording extension execution."""
    registry = ExtensionRegistry(temp_db)
    
    metadata = ExtensionMetadata(
        name="exec_test",
        version="1.0.0",
        description="Test",
        required_capabilities=[],
        tags=[]
    )
    await registry.register(metadata, sample_extension_code)
    
    # Record successful execution
    await registry.record_execution("exec_test", result={"success": True})
    
    # Record failed execution
    await registry.record_execution("exec_test", error="Test error")
    
    # Verify execution count updated
    result = await registry.get_by_name("exec_test")
    assert result.execution_count >= 2
