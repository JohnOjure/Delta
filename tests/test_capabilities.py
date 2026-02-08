"""Tests for capabilities."""

import pytest
import pytest_asyncio
from pathlib import Path
import tempfile

from src.models.capability import CapabilityResult, CapabilityStatus


class TestFilesystemCapabilities:
    """Tests for filesystem capabilities."""
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.mark.asyncio
    async def test_fs_read(self, temp_dir):
        """Test reading a file."""
        from src.capabilities.filesystem import FileSystemReadCapability
        
        # Create a test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")
        
        cap = FileSystemReadCapability(allowed_paths=[str(temp_dir)])
        result = await cap.execute(path=str(test_file))
        
        assert result.success
        assert result.value == "Hello, World!"
    
    @pytest.mark.asyncio
    async def test_fs_read_nonexistent(self, temp_dir):
        """Test reading a file that doesn't exist."""
        from src.capabilities.filesystem import FileSystemReadCapability
        
        cap = FileSystemReadCapability(allowed_paths=[str(temp_dir)])
        result = await cap.execute(path=str(temp_dir / "nonexistent.txt"))
        
        assert not result.success
        assert result.error is not None
    
    @pytest.mark.asyncio
    async def test_fs_write(self, temp_dir):
        """Test writing a file."""
        from src.capabilities.filesystem import FileSystemWriteCapability
        
        cap = FileSystemWriteCapability(allowed_paths=[str(temp_dir)])
        result = await cap.execute(path=str(temp_dir / "output.txt"), content="Test content")
        
        assert result.success
        
        # Verify file was written
        written = (temp_dir / "output.txt").read_text()
        assert written == "Test content"
    
    @pytest.mark.asyncio
    async def test_fs_list(self, temp_dir):
        """Test listing directory contents."""
        from src.capabilities.filesystem import FileSystemListCapability
        
        # Create some test files
        (temp_dir / "file1.txt").write_text("1")
        (temp_dir / "file2.txt").write_text("2")
        (temp_dir / "subdir").mkdir()
        
        cap = FileSystemListCapability(allowed_paths=[str(temp_dir)])
        result = await cap.execute(path=str(temp_dir))
        
        assert result.success
        names = [entry["name"] for entry in result.value]
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "subdir" in names
    
    @pytest.mark.asyncio  
    async def test_path_traversal_blocked(self, temp_dir):
        """Test that path traversal is blocked."""
        from src.capabilities.filesystem import FileSystemReadCapability
        
        cap = FileSystemReadCapability(allowed_paths=[str(temp_dir)])
        result = await cap.execute(path="/etc/passwd")
        
        # Should fail because /etc/passwd is not in allowed_paths
        assert not result.success


class TestStorageCapabilities:
    """Tests for key-value storage capabilities."""
    
    @pytest.fixture
    def temp_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "storage.db"
    
    @pytest.mark.asyncio
    async def test_storage_set_get(self, temp_db):
        """Test setting and getting a value."""
        from src.capabilities.storage import StorageBase, StorageSetCapability, StorageGetCapability
        
        storage = StorageBase(temp_db)
        set_cap = StorageSetCapability(storage)
        get_cap = StorageGetCapability(storage)
        
        # Set a value
        result = await set_cap.execute(key="test_key", value="test_value")
        assert result.success
        
        # Get it back
        result = await get_cap.execute(key="test_key")
        assert result.success
        assert result.value == "test_value"
    
    @pytest.mark.asyncio
    async def test_storage_get_nonexistent(self, temp_db):
        """Test getting a key that doesn't exist."""
        from src.capabilities.storage import StorageBase, StorageGetCapability
        
        storage = StorageBase(temp_db)
        cap = StorageGetCapability(storage)
        result = await cap.execute(key="nonexistent")
        
        assert result.success
        assert result.value is None
    
    @pytest.mark.asyncio
    async def test_storage_delete(self, temp_db):
        """Test deleting a key."""
        from src.capabilities.storage import (
            StorageBase,
            StorageSetCapability, 
            StorageGetCapability, 
            StorageDeleteCapability
        )
        
        storage = StorageBase(temp_db)
        set_cap = StorageSetCapability(storage)
        get_cap = StorageGetCapability(storage)
        del_cap = StorageDeleteCapability(storage)
        
        # Set, delete, then try to get
        await set_cap.execute(key="to_delete", value="temp")
        await del_cap.execute(key="to_delete")
        result = await get_cap.execute(key="to_delete")
        
        assert result.value is None


class TestNetworkCapabilities:
    """Tests for network capabilities."""
    
    @pytest.mark.asyncio
    async def test_net_fetch_descriptor(self):
        """Test that network capability has correct descriptor."""
        from src.capabilities.network import NetworkFetchCapability
        
        cap = NetworkFetchCapability()
        desc = cap.descriptor
        
        assert desc.name == "net.fetch"
        # Parameters is a dict, check for 'url' key
        assert "url" in desc.parameters
