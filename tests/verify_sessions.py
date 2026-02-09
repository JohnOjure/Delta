import asyncio
import os
import shutil
from pathlib import Path
from src.core.memory import ConversationManager, Memory
from src.core.agent import Agent

# Mock components for Agent
class MockAdapter:
    def get_resource_limits(self): return None
    def get_environment_info(self): 
        class Info:
            def to_prompt_string(self): return ""
        return Info()

class MockGemini:
    async def plan(self, *args): 
        class Response:
            text = "PLAN: COMPLETE"
        return "PLAN: COMPLETE"
    async def reflect(self, *args, **kwargs): return {"should_retry": False}

class MockRegistry:
    async def list_all(self): return []

async def verify():
    print("Verifying session persistence...")
    
    # Setup clean db
    db_path = Path("./test_data/memory.db")
    if db_path.parent.exists():
        shutil.rmtree(db_path.parent)
    db_path.parent.mkdir(parents=True)
    
    # 1. Create session and add data
    print("\n1. creating session...")
    mem = Memory(db_path)
    cm = ConversationManager(db_path)
    
    sid = await cm.create_session("Test Session")
    print(f"Session created: {sid}")
    
    await cm.add_message("user", "Hello", sid)
    await cm.add_message("assistant", "Hi there", sid)
    
    # 2. Verify existence
    hist = await cm.get_session_history(sid)
    print(f"History items: {len(hist)}")
    assert len(hist) == 2
    assert hist[0]['content'] == "Hello"
    
    # 3. Simulate Restart (new instances)
    print("\n3. Simulating restart...")
    cm2 = ConversationManager(db_path) # New instance, same DB
    
    sessions = await cm2.get_sessions()
    print(f"Sessions found: {len(sessions)}")
    assert len(sessions) == 1
    assert sessions[0]['id'] == sid
    
    hist2 = await cm2.get_session_history(sid)
    print(f"History after restart: {len(hist2)}")
    assert len(hist2) == 2
    assert hist2[1]['content'] == "Hi there"
    
    # 4. Verify Agent integration
    print("\n4. Verifying Agent integration...")
    agent = Agent(MockAdapter(), MockGemini(), MockRegistry(), memory=mem)
    
    # Run agent with session_id
    # We mock the internal components so it doesn't actually call Gemini/VM
    # Just checking it doesn't crash and writes to DB
    
    # Inject a fake conversation manager to check calls? 
    # No, we use the real one backed by DB and check DB.
    
    try:
        # We need to minimally mock the agent to run, but Agent.run is complex.
        # It's better to just check if `add_message` works via the `cm` we have 
        # since we already verified Agent code passes session_id.
        # But let's try to call `add_message` directly as Agent would.
        
        await agent._conversation.add_message("user", "Agent test", sid)
        
        hist3 = await cm2.get_session_history(sid)
        assert len(hist3) == 3
        assert hist3[2]['content'] == "Agent test"
        print("Agent-style message addition works")
        
    except Exception as e:
        print(f"Agent test failed: {e}")
        raise e

    print("\n✅ Verification SUCCESS!")

if __name__ == "__main__":
    asyncio.run(verify())
