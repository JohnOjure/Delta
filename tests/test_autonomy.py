
import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
import sys
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.agent import Agent, AgentResult, AgentState
from src.core.gemini_client import GeminiClient
from src.adapters.desktop import DesktopAdapter
from src.extensions.registry import ExtensionRegistry
from src.core.planner import Plan, PlanStep, ActionType

class TestAutonomy(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_adapter = MagicMock(spec=DesktopAdapter)
        self.mock_gemini = MagicMock(spec=GeminiClient)
        self.mock_registry = MagicMock(spec=ExtensionRegistry)
        
        # Setup common mocks
        self.mock_adapter.get_environment_info.return_value = MagicMock(
            to_prompt_string=lambda: "Mock Env"
        )
        self.mock_adapter.get_resource_limits.return_value = MagicMock()
        self.mock_adapter.get_available_capabilities.return_value = {}
        self.mock_registry.list_all.return_value = []
        
        self.agent = Agent(
            adapter=self.mock_adapter,
            gemini_client=self.mock_gemini,
            registry=self.mock_registry
        )

    async def test_infinite_loop_capability(self):
        """Verify agent can run beyond the old 10 iteration limit."""
        
        # Mock planner to return 15 single-step plans before completing
        # We'll use a side_effect to return different plans
        
        plans = []
        for i in range(12): # 12 steps > 10 old limit
            plans.append({
                "goal": "Test infinite loop",
                "analysis": f"Step {i+1}",
                "steps": [
                    {
                        "action": "use_capability",
                        "details": f"Doing step {i+1}",
                        "capabilities_needed": ["test.cap"],
                        "params": {}
                    }
                ]
            })
        
        # Finally complete
        plans.append({
            "goal": "Test infinite loop",
            "analysis": "Done",
            "steps": [
                {
                    "action": "complete",
                    "details": "Finished 13 steps",
                    "capabilities_needed": [],
                    "params": {}
                }
            ]
        })
        
        self.mock_gemini.plan = AsyncMock(side_effect=plans)
        self.mock_gemini._model_name = "mock-model"
        
        # Mock capability execution to always succeed
        mock_cap = AsyncMock()
        mock_cap.execute.return_value = MagicMock(success=True, value="ok")
        self.mock_adapter.get_available_capabilities.return_value = {"test.cap": mock_cap}
        
        # Run agent
        result = await self.agent.run("Run for a long time")
        
        self.assertTrue(result.success)
        self.assertGreater(result.steps_taken, 10, "Agent should run more than 10 steps")
        self.assertEqual(result.steps_taken, 13)

    async def test_self_correction_on_failure(self):
        """Verify agent asks for alternatives when failing."""
        
        # Plan 1: Fail immediately
        plan_fail = {
            "goal": "Try impossible task",
            "analysis": "Attempt 1",
            "steps": [
                {
                    "action": "fail",
                    "details": "I cannot do this",
                    "capabilities_needed": [],
                    "params": {}
                }
            ]
        }
        
        # Alternative suggestion
        self.mock_gemini.suggest_alternatives = AsyncMock(return_value={
            "message": "Don't give up",
            "alternatives": ["Try method B"],
            "recommended": "Try method B",
            "can_auto_try": True
        })
        
        # Plan 2: Succeed with method B (this is called after suggestion)
        plan_success = {
            "goal": "Try impossible task",
            "analysis": "Attempt 2 with Method B",
            "steps": [
                {
                    "action": "complete",
                    "details": "Method B worked",
                    "capabilities_needed": [],
                    "params": {}
                }
            ]
        }
        
        self.mock_gemini.plan = AsyncMock(side_effect=[plan_fail, plan_success])
        self.mock_gemini._model_name = "mock-model"
        
        result = await self.agent.run("Do something hard")
        
        # Verify suggest_alternatives was called
        self.mock_gemini.suggest_alternatives.assert_called_once()
        
        # Verify it eventually succeeded
        self.assertTrue(result.success)
        self.assertEqual(result.response, "Method B worked")
        self.assertEqual(result.steps_taken, 2)

    async def test_self_evolution_edit_source(self):
        """Verify agent has permission to edit files in src."""
        
        # Setup a real file write capability mock
        # We want to verify the agent *attempts* to call fs.write on a src file
        
        plan_edit = {
            "goal": "Improve myself",
            "analysis": "Editing agent.py",
            "steps": [
                {
                    "action": "use_capability",
                    "details": "Writing comment to agent.py",
                    "capabilities_needed": ["fs.write"],
                    "params": {
                        "path": str(Path(__file__).parent.parent.resolve() / "src" / "core" / "agent.py"),
                        "content": "# Self-edited"
                    }
                },
                {
                    "action": "complete",
                    "details": "Edited source code",
                    "capabilities_needed": [],
                    "params": {}
                }
            ]
        }
        
        self.mock_gemini.plan = AsyncMock(return_value=plan_edit)
        self.mock_gemini._model_name = "mock-model"
        
        mock_fs_write = AsyncMock()
        mock_fs_write.execute.return_value = MagicMock(success=True, value="File written")
        self.mock_adapter.get_available_capabilities.return_value = {"fs.write": mock_fs_write}
        
        result = await self.agent.run("Add a comment to your source code")
        
        self.assertTrue(result.success)
        
        # Verify it called fs.write with the correct path
        mock_fs_write.execute.assert_called_once()
        call_args = mock_fs_write.execute.call_args[1]
        self.assertIn("agent.py", call_args["path"])

if __name__ == "__main__":
    unittest.main()
