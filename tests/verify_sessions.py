import asyncio
import sys
import json
from pathlib import Path

# Add src to path
sys.path.append(str(Path.cwd()))

from src.core.memory import Memory, ConversationManager
from src.config import get_config

async def test_sessions():
    print("Testing Session Management...")
    
    # Setup
    config = get_config()
    db_path = config.paths.data_dir / "memory.db"
    
    # Initialize Manager
    conversation = ConversationManager(db_path)
    
    # 1. Create Session
    print("\n1. Creating Session...")
    session_id = await conversation.create_session("Test Session 1")
    print(f"   Created session ID: {session_id}")
    assert session_id is not None
    
    # 2. Add Messages
    print("\n2. Adding Messages...")
    await conversation.add_message("user", "Hello Delta", session_id)
    await conversation.add_message("assistant", "Hello User", session_id)
    print("   Messages added.")
    
    # 3. Get History
    print("\n3. Retrieving History...")
    history = await conversation.get_session_history(session_id)
    print(f"   History length: {len(history)}")
    for msg in history:
        print(f"   - {msg['type']}: {msg['content']}")
    assert len(history) == 2
    assert history[0]['content'] == "Hello Delta"
    
    # 4. Get Sessions List
    print("\n4. Listing Sessions...")
    sessions = await conversation.get_sessions()
    print(f"   Sessions found: {len(sessions)}")
    found = False
    for s in sessions:
        print(f"   - [{s['id']}] {s['title']}")
        if s['id'] == session_id:
            found = True
    assert found
    
    # 5. Context Retrieval
    print("\n5. Checking Context Retrieval...")
    context = await conversation.get_recent_context(session_id)
    print(f"   Context:\n{context}")
    assert "User: Hello Delta" in context
    assert "Delta: Hello User" in context

    print("\n✅ Session Verification Passed!")

if __name__ == "__main__":
    asyncio.run(test_sessions())
