
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, "/home/fluxx/Workspace/Delta")

from src.core.gemini_client import GeminiClient
from src.config import get_config

async def test_api():
    print("🔵 Testing Real API Connectivity...")
    
    config = get_config()
    api_key = config.api.gemini_api_key
    
    if not api_key:
        print("❌ Error: GEMINI_API_KEY not found in environment or .env")
        return
        
    print(f"  🔑 API Key found (starts with {api_key[:4]}...)")
    print(f"  🤖 Configured Model: {config.api.gemini_model}")
    
    client = GeminiClient(api_key=api_key, model=config.api.gemini_model)
    
    print("\n📨 Sending request to Gemini...")
    try:
        response = await client.generate("Hello! Please confirm which model version you are.", retries=0)
        print("\n✅ Response Received:")
        print(f"--------------------------------------------------")
        print(response)
        print(f"--------------------------------------------------")
        print("🎉 SUCCESS: Model accepted and responded.")
        
    except Exception as e:
        print(f"\n❌ REQUEST FAILED: {e}")
        print("\nPossible causes:")
        print("1. Invalid Model Name")
        print("2. API Key does not have access to this model")
        print("3. Network/Connection issues")

if __name__ == "__main__":
    asyncio.run(test_api())
