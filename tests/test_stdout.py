import asyncio
import unittest
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.vm.executor import Executor
from src.models.extension import ExtensionRecord, ExtensionMetadata

class TestStdoutCapture(unittest.TestCase):
    def test_std_capture(self):
        async def run_test():
            # Create a simple executor without limits
            executor = Executor(unrestricted=True)
            
            # Simple extension that prints
            # Note: We wrap it in proper main structure for the loader
            code = """
def extension_main():
    print("This is intercepted stdout")
    print("Line 2")
    return "Existing Return Value"
"""
            record = ExtensionRecord(
                metadata=ExtensionMetadata(name="test_stdout", description="", version="1.0", required_capabilities=[]),
                source_code=code
            )
            
            result = await executor.execute(record, {})
            
            print(f"Success: {result.success}")
            if result.error:
                print(f"Error: {result.error}")
            print(f"Value: {result.value}")
            print(f"Output: {result.output}")
            
            self.assertTrue(result.success)
            self.assertEqual(result.value, "Existing Return Value")
            self.assertIn("This is intercepted stdout", result.output)
            self.assertIn("Line 2", result.output)
            
        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()
