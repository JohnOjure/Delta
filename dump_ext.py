import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.dirname(".")))

from src.extensions.registry import ExtensionRegistry
from src.core.config import ConfigManager

async def dump_extension():
    data_dir = "data"
    if os.path.exists("/home/fluxx/Workspace/Delta/data"):
        data_dir = "/home/fluxx/Workspace/Delta/data"
            
    registry = ExtensionRegistry(f"{data_dir}/extensions.db")
    
    # Just get all and print their dict representation if possible
    try:
        extensions = await registry.list_all()
        print(f"Found {len(extensions)} extensions")
        
        for ext in extensions:
            # ExtensionRecord has metadata field which contains name
            if hasattr(ext, 'metadata'):
                name = ext.metadata.name
                source = ext.source_code
            else:
                # Fallback if structure is different
                d = ext.dict() if hasattr(ext, 'dict') else ext.__dict__
                name = d.get('metadata', {}).get('name')
                source = d.get('source_code')
                
            print(f"Name: {name}")
            if name and ("resource" in name or "asset" in name):
                print(f"--- SOURCE of {name} ---")
                print(source)
                print("--- END SOURCE ---")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(dump_extension())
