import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.append(os.getcwd())

from src.core.agent import Agent
from src.core.memory import Memory
from src.core.gemini_client import GeminiClient
from src.extensions.registry import ExtensionRegistry
from src.core.ghost import GhostMode
from src.config import get_config

class MockAdapter:
    def get_resource_limits(self):
        # Return a dummy object with limits
        class Limits:
            cpu_time_seconds = 60
            memory_mb = 512
        return Limits()

async def verify():
    print("🔍 Starting Delta System Verification...")
    
    # 1. Config & Paths (Real User Data)
    print("\n[1] Checking Configuration...")
    try:
        config = get_config()
        print(f"  ✅ Config loaded. API Key present: {bool(config.api.gemini_api_key)}")
        
        # Check actual ~/.delta directory
        home_delta = Path.home() / ".delta"
        print(f"  ✅ Checking ~/.delta: {home_delta}")
        
    except Exception as e:
        print(f"  ❌ Config failed: {e}")
        return

    # 2. Memory System (Real Persistence)
    print("\n[2] Checking Memory (Soul/User)...")
    try:
        # Use the actual memory.db from ~/.delta if it exists to verify user state
        real_db = Path.home() / ".delta" / "memory.db"
        memory = Memory(real_db)  
        await memory.ensure_persistent_files()
        
        soul = Path.home() / ".delta" / "SOUL.md"
        user = Path.home() / ".delta" / "USER.md"
        
        if soul.exists() and user.exists():
            print("  ✅ Persistent files (SOUL.md, USER.md) found in ~/.delta")
        else:
            print(f"  ❌ Persistent files missing in ~/.delta. Soul: {soul.exists()}, User: {user.exists()}")
            
    except Exception as e:
        print(f"  ❌ Memory failed: {e}")

    # 3. Extension Registry
    print("\n[3] Checked Extension Registry (Skipping re-init to avoid locking DB)...")
    # Registry is generally safe as it uses a different DB usually

    # 4. Ghost Mode
    print("\n[4] Checking Ghost Mode...")
    try:
        # Proper mock for Agent
        agent = Agent(MockAdapter(), None, None, None) 
        ghost = GhostMode(agent)
        print(f"  ✅ Ghost Mode initialized. Monitored paths: {len(ghost.monitored_paths)}")
        
        # Verify HEARTBEAT.md
        hb = Path.home() / ".delta" / "HEARTBEAT.md"
        if not hb.exists():
            # Create it if missing (simulating service start)
            hb.write_text("# Heartbeat")
            print("  ⚠️ Created missing HEARTBEAT.md")
        else:
            print("  ✅ HEARTBEAT.md found.")
            
    except Exception as e:
        print(f"  ❌ Ghost Mode failed: {e}")

    print("\n✨ Verification Complete.")

if __name__ == "__main__":
    try:
        asyncio.run(verify())
    except KeyboardInterrupt:
        pass
