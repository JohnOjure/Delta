import asyncio
import unittest
import os
import sys
from pathlib import Path

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.memory import ConversationManager

class TestConversationContext(unittest.TestCase):
    def setUp(self):
        self.db_path = Path("test_memory.db")
        if self.db_path.exists():
            os.remove(self.db_path)
            
    def tearDown(self):
        if self.db_path.exists():
            os.remove(self.db_path)

    def test_formatting(self):
        async def run_test():
            cm = ConversationManager(self.db_path)
            
            # Add messages
            await cm.add_message("user", "Hello")
            await cm.add_message("assistant", "Hi there")
            await cm.add_message("tool", "Command executed successfully")
            await cm.add_message("system", "System warning")
            
            # Get context
            context = await cm.get_recent_context(limit=10)
            
            print(f"\nContext Output:\n{context}")
            
            # Verify
            self.assertIn("User: Hello", context)
            self.assertIn("Delta: Hi there", context)
            self.assertIn("Tool Output: Command executed successfully", context)
            self.assertIn("System: System warning", context)
            
        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()
