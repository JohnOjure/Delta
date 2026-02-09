import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(".")))

from src.extensions.registry import ExtensionRegistry
from src.vm.executor import Executor
from src.adapters.desktop import DesktopAdapter

from src.core.config import ConfigManager

async def run():
    print("Testing Extension Execution...")
    
    # Load config for API key
    manager = ConfigManager()
    config = manager.load()
    if not config or not config.api_key:
        print("Error: No API key found in config. Please set up Delta first.")
        return

    data_dir = "data"
    if os.path.exists("/home/fluxx/Workspace/Delta/data"):
        data_dir = "/home/fluxx/Workspace/Delta/data"
        
    registry = ExtensionRegistry(f"{data_dir}/extensions.db")
    
    # We need an adapter for capabilities
    adapter = DesktopAdapter(api_key=config.api_key)
    
    executor = Executor(adapter)
    
    ext = await registry.get_by_name("resource_asset_auditor")
    if not ext:
        print("Extension not found!")
        return

    print(f"Executing {ext.metadata.name}...")
    try:
        result = await executor.execute(ext.source_code, ext.metadata.required_capabilities)
        print("\n--- Execution Result ---")
        print(f"Success: {result.success}")
        print(f"Output Payload: {result.output}") # This is what TeeIO captured
        print(f"Return Value: {result.value}")
    except Exception as e:
        print(f"Execution failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())
