"""Core safety net extensions.

These extensions are hardcoded and always available, ensuring basic functionality
even if the LLM fails to generate code.
"""

import os
import glob
from pathlib import Path
from typing import List, Dict, Any

def fs_read(path: str) -> str:
    """Read a file from the filesystem.
    
    Args:
        path: Absolute path to the file.
        
    Returns:
        Content of the file.
    """
    try:
        return Path(path).read_text()
    except Exception as e:
        return f"Error reading file {path}: {str(e)}"

def fs_write(path: str, content: str) -> str:
    """Write content to a file.
    
    Args:
        path: Absolute path to the file.
        content: Content to write.
        
    Returns:
        Success message or error.
    """
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file {path}: {str(e)}"

def fs_list(path: str) -> List[str]:
    """List files in a directory.
    
    Args:
        path: Directory path.
        
    Returns:
        List of filenames.
    """
    try:
        return [p.name for p in Path(path).iterdir()]
    except Exception as e:
        return [f"Error listing directory {path}: {str(e)}"]

def fs_search(pattern: str, path: str = ".") -> List[str]:
    """Search for files matching a pattern.
    
    Args:
        pattern: Glob pattern (e.g., "*.py").
        path: Root directory to search.
        
    Returns:
        List of matching file paths.
    """
    try:
        search_path = Path(path)
        return [str(p) for p in search_path.rglob(pattern)]
    except Exception as e:
        return [f"Error searching files: {str(e)}"]

# Registry of core extensions
CORE_EXTENSIONS = [
    {
        "name": "fs_read",
        "description": "Read content of a file from the local filesystem.",
        "code": """
def extension_main(path: str, **kwargs) -> str:
    from pathlib import Path
    try:
        return Path(path).read_text()
    except Exception as e:
        return f"Error reading file {path}: {str(e)}"
""",
        "required_capabilities": ["filesystem"]
    },
    {
        "name": "fs_write",
        "description": "Write text content to a file, creating directories if needed.",
        "code": """
def extension_main(path: str, content: str, **kwargs) -> str:
    from pathlib import Path
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file {path}: {str(e)}"
""",
        "required_capabilities": ["filesystem"]
    },
    {
        "name": "fs_list",
        "description": "List all files and directories in a specific path.",
        "code": """
def extension_main(path: str, **kwargs) -> list[str]:
    from pathlib import Path
    try:
        return [p.name for p in Path(path).iterdir()]
    except Exception as e:
        return [f"Error listing directory {path}: {str(e)}"]
""",
        "required_capabilities": ["filesystem"]
    },
    {
        "name": "fs_search",
        "description": "Recursively search for files matching a glob pattern.",
        "code": """
def extension_main(pattern: str, path: str = ".", **kwargs) -> list[str]:
    from pathlib import Path
    try:
        search_path = Path(path)
        return [str(p) for p in search_path.rglob(pattern)]
    except Exception as e:
        return [f"Error searching files: {str(e)}"]
""",
        "required_capabilities": ["filesystem"]
    },
    {
        "name": "system_stats",
        "description": "Get current system statistics (CPU, Memory, Disk).",
        "code": """
def extension_main(**kwargs) -> dict:
    import psutil
    import shutil
    
    total, used, free = shutil.disk_usage("/")
    
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory": {
            "total": psutil.virtual_memory().total,
            "available": psutil.virtual_memory().available,
            "percent": psutil.virtual_memory().percent,
            "used": psutil.virtual_memory().used,
            "free": psutil.virtual_memory().free
        },
        "disk": {
            "total": total,
            "used": used,
            "free": free,
            "percent": (used / total) * 100
        }
    }
""",
        "required_capabilities": ["system"]
    }
]
