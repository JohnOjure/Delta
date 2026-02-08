
import asyncio
import time
import pytest
from src.core.agent import Agent, AgentResult
from src.core.gemini_client import GeminiClient
from src.adapters.base import BaseAdapter
from src.extensions.registry import ExtensionRegistry
from unittest.mock import MagicMock, AsyncMock

# Mock Adapter and Registry to isolate Agent logic
class MockAdapter(BaseAdapter):
    async def initialize(self):
        pass
    async def shutdown(self):
        pass
    def get_available_capabilities(self):
        return {}
    def get_environment_info(self):
        return MagicMock(to_prompt_string=lambda: "Mock Environment")
    def get_resource_limits(self):
        return {}

@pytest.mark.asyncio
async def test_needle_in_haystack():
    """
    Test the Agent's ability to retrieve a specific fact buried in a long context.
    Methods assessed: Plan generation and detailed response.
    """
    # 1. Setup
    adapter = MockAdapter()
    registry = MagicMock(spec=ExtensionRegistry)
    registry.list_all = AsyncMock(return_value=[])
    
    # We need a real or simulated Gemini Client. 
    # Since we can't easily mock the LLM's "intelligence" without an actual API call or complex mock,
    # we will use the real GeminiClient but we need to ensure the environment has the key.
    # If not, we'll have to skip or mock the response. 
    # For this "Agent Evaluation", let's assume valid config or mock the response to simulate *success* 
    # if we want to test the *infrastructure* of the test, but the prompt asks for a report on *its* response.
    # So we should try to use the real one if possible, or mock the `plan` method if we want to purely test the *harness*.
    
    # Try to verify if we can instantiate the client.
    from src.config import get_config
    config = get_config()
    api_key = config.api.gemini_api_key
    
    if not api_key:
        pytest.skip("Gemini Client Init failed (missing key)")

    try:
        client = GeminiClient(api_key=api_key)
    except Exception as e:
        pytest.skip(f"Gemini Client Init failed: {e}")

    agent = Agent(adapter, client, registry)

    # 2. The Needle and the Haystack
    needle = "The secret code is 789123."
    haystack_filler = "This is irrelevant information. " * 500
    goal = f"Here is some context: {haystack_filler} {needle} {haystack_filler}. What is the secret code?"

    # 3. Execution
    start_time = time.time()
    try:
        # We expect the agent to PLAN to answer this.
        # Since we don't have tools, it should answer directly or via reflection.
        result = await agent.run(goal)
    except Exception as e:
        pytest.fail(f"Agent crashed: {e}")
    
    end_time = time.time()
    latency = end_time - start_time

    # 4. Verification
    print(f"\n[Logic Test] Latency: {latency:.2f}s")
    print(f"[Logic Test] Response: {result.response}")

    # It should succeed
    assert result.success, "Agent failed to complete the goal."
    
    # It should find the needle
    assert "789123" in result.response or "789123" in result.message, "Agent failed to retrieve the needle."

if __name__ == "__main__":
    # Manually run if executed as script
    asyncio.run(test_needle_in_haystack())
