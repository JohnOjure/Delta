
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.agent import Agent, AgentResult
from src.core.gemini_client import GeminiClient
from src.extensions.registry import ExtensionRegistry
from src.adapters.desktop import DesktopAdapter
from src.models.extension import ExtensionMetadata

async def run_verification():
    print("🔵 Starting End-to-End System Verification...")
    
    # Setup Paths
    data_dir = Path("./data_test")
    data_dir.mkdir(exist_ok=True)
    db_path = data_dir / "extensions.db"
    if db_path.exists():
        os.remove(db_path)
        
    print(f"  📂 Test Data Directory: {data_dir}")

    # 1. Mock Adapter
    adapter = DesktopAdapter(api_key="mock_key", data_directory=data_dir)
    await adapter.initialize()
    print("  ✅ Adapter Initialized")

    # 2. Mock Gemini Client
    gemini = MagicMock(spec=GeminiClient)
    gemini.api_key = "mock_key"
    gemini._model_name = "gemini-mock"
    
    # Mock Plan Response - MUST BE A DICT
    gemini.plan = AsyncMock(return_value={
        "goal": "Calculate factorial of 5",
        "analysis": "Need to create a math extension",
        "steps": [
            {
                "action": "create_extension",
                "details": "Create a tool to calculate factorial",
                "capabilities_needed": []
            },
            {
                "action": "execute_extension",
                "extension_name": "factorial_tool",
                "details": "Calculate factorial of 5",
                "params": {"n": 5}
            },
            {
                "action": "complete",
                "details": "Factorial calculated successfully"
            }
        ],
        "required_capabilities": [],
        "new_extensions_needed": []
    })
    
    # Mock Extension Generation Response
    gemini.generate_extension = AsyncMock(return_value="""
```json
{
    "name": "factorial_tool",
    "description": "Calculates factorial of a number",
    "version": "1.0.0",
    "required_capabilities": [],
    "tags": ["math"]
}
```

```python
def extension_main(n=5):
    # Ensure n is int
    try:
        n = int(n)
    except:
        return "Error: Invalid input"
        
    if n < 0:
        return "Error: Negative number"
    if n == 0:
        return 1
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result
```
    """)
    
    # Mock Validation Response
    gemini.validate_extension_result = AsyncMock(return_value={"valid": True, "reason": "Correct"})
    
    # Mock Reflection
    gemini.reflect = AsyncMock(return_value={"assessment": "Success", "should_retry": False})
    
    # Mock Alternatives (just in case)
    gemini.suggest_alternatives = AsyncMock(return_value={
        "message": "Failed", 
        "alternatives": ["Retry"], 
        "recommended": "Retry"
    })
    
    print("  ✅ Gemini Client Mocked")

    # 3. Real Registry & Agent
    registry = ExtensionRegistry(db_path)
    agent = Agent(adapter, gemini, registry)
    
    # MOCK EXECUTOR to avoid multiprocessing/pickling issues with dynamic code in tests
    # The real executor uses multiprocessing which fails with dynamically defined functions/mocks
    agent._executor = MagicMock()
    
    async def mock_execute(extension, caps):
        # execute the code locally
        local_scope = {}
        exec(extension.source_code, {}, local_scope)
        if 'extension_main' in local_scope:
            try:
                # Call with NO arguments as per our updated mock
                val = local_scope['extension_main']() 
                return MagicMock(success=True, value=val, error=None)
            except Exception as e:
                return MagicMock(success=False, value=None, error=str(e))
        return MagicMock(success=False, error="No extension_main")

    agent._executor.execute = AsyncMock(side_effect=mock_execute)
    
    print("  ✅ Agent & Registry Initialized (Executor Mocked)")

    # 4. Run Agent
    print("\n🚀 Running Agent with goal: 'Calculate 5! (factorial)'")
    result = await agent.run("Calculate 5!")
    
    # 5. Assertions
    print("\n📊 Verification Results:")
    
    # Verify Extension Creation
    ext = await registry.get_by_name("factorial_tool")
    if ext:
        print("  ✅ Extension 'factorial_tool' created and registered")
        
        # Verify Execution
        # ExtensionRegistry stores stats in the record, not a separate history log
        if ext.execution_count > 0:
            print(f"  ✅ Extension executed {ext.execution_count} times")
            if ext.last_result == 120:
                print(f"  ✅ Result verified: {ext.last_result}")
            else:
                print(f"  ❌ Result mismatch: Expected 120, got {ext.last_result}")
        else:
            print("  ❌ Extension was NOT executed")
            
    else:
        print("  ❌ Extension creation FAILED")
        if result.success is False:
             print(f"     Reason: {result.message}")


    # Verify Agent Success
    if result.success:
        print("  ✅ Agent reported SUCCESS")
    else:
        print(f"  ❌ Agent reported FAILURE: {result.message}")
        
    # Verify Cleanup
    await adapter.shutdown()
    if db_path.exists():
        os.remove(db_path)
    data_dir.rmdir()
    print("  🧹 Cleanup complete")

if __name__ == "__main__":
    asyncio.run(run_verification())
