import os
import asyncio
from dotenv import load_dotenv
from google import genai

load_dotenv()

async def list_models():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env")
        return

    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1beta'})
    
    print(f"Checking models with API key: {api_key[:10]}...")
    
    try:
        # Await the list call to get the pager/iterator
        models = await client.aio.models.list()
        async for model in models:
            print(f"- {model.name}")
            if "flash" in model.name:
                print(f"  (Flash match found: {model.name})")
    except Exception as e:
        print(f"Error listing models: {e}")

    print("\nAttempting generation with 'gemini-1.5-flash'...")
    try:
        response = await client.aio.models.generate_content(
            model='gemini-1.5-flash',
            contents='Hello, are you working?'
        )
        print(f"Success! Response: {response.text}")
    except Exception as e:
        print(f"Generation failed: {e}")

if __name__ == "__main__":
    asyncio.run(list_models())
