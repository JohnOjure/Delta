
import asyncio
import sys
import os
from google import genai
from dotenv import load_dotenv

# Load .env from current directory
load_dotenv()

async def list_models():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not found")
        return

    client = genai.Client(api_key=api_key)
    
    print("📋 Listing Available Models starting with 'gemini':")
    try:
        # Await the list call
        models = await client.aio.models.list()
        
        # Iterate over the result
        filtered_models = []
        for m in models:
            if "gemini" in m.name:
                print(f"  - {m.name}")
                filtered_models.append(m.name)
                
        # Heuristic check for Gemini 3
        candidates = [m for m in filtered_models if "gemini-3" in m or "gemini-3" in m]
        if candidates:
            print(f"\n⭐ FOUND GEMINI 3 CANDIDATES: {candidates}")
        else:
            print("\n⚠️ No 'gemini-3' models found. You may need to use 'gemini-2.0-flash-exp' or similar if 3.0 is not yet available in your region/account.")
            
    except Exception as e:
        print(f"❌ Error listing models: {e}")

if __name__ == "__main__":
    asyncio.run(list_models())
