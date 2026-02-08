
import pytest
import os
import asyncio
from dotenv import load_dotenv
from src.core.gemini_client import GeminiClient

# Load environment variables
load_dotenv()

@pytest.mark.asyncio
async def test_real_gemini_connection():
    """
    Real integration test that hits the Gemini API.
    Requires GEMINI_API_KEY to be set.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("Skipping real integration test: GEMINI_API_KEY not found")

    print(f"\n🔵 Connecting with key: {api_key[:4]}...****")
    
    # Use the configured model from the environment or default
    # We want to test the *actual* model the agent uses
    from src.config import get_config
    config = get_config()
    model = config.api.gemini_model
    
    client = GeminiClient(api_key=api_key, model=model)

    print(f"🤖 Model: {model}")
    
    # Simple generation test
    try:
        response = await client.generate("Reply with exactly 'OK'", retries=1)
        print(f"📨 Response: {response}")
        assert "OK" in response or "ok" in response.lower()
    except Exception as e:
        pytest.fail(f"API Request Failed: {e}")

@pytest.mark.asyncio
async def test_real_tool_generation():
    """
    Test if Gemini can actually generate a valid tool definition (JSON + Python).
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("Skipping real integration test: GEMINI_API_KEY not found")

    from src.config import get_config
    config = get_config()
    client = GeminiClient(api_key=api_key, model=config.api.gemini_model)

    # Test extension generation logic
    description = "A tool that returns the string 'hello world'"
    try:
        result = await client.generate_extension(
            description=description,
            required_capabilities=[],
            available_capabilities="None"
        )
        
        assert isinstance(result, dict)
        assert "name" in result
        assert "code" in result
        assert "def extension_main" in result["code"]
        print("\n✅ Successfully generated extension code via API")
        
    except Exception as e:
        pytest.fail(f"Extension Generation Failed: {e}")
