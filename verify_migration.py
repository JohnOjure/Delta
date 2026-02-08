
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, "/home/fluxx/Workspace/Delta")

from src.core.gemini_client import GeminiClient
from src.core.config import ConfigManager
from src.config import get_config

def verify_gemini_client():
    print("Checking GeminiClient defaults...")
    # Initialize with dummy key
    client = GeminiClient(api_key="dummy_key")
    
    assert client._model_name == "gemini-3-pro-preview", f"Expected gemini-3-pro-preview, got {client._model_name}"
    print("✅ Default model is gemini-3-pro-preview")
    
    assert client._thinking_model == "gemini-3-pro-preview", f"Expected thinking model gemini-3-pro-preview, got {client._thinking_model}"
    print("✅ Thinking model is gemini-3-pro-preview")
    
    available = client.get_available_models()
    assert "gemini-3-pro-preview" in available, "gemini-3-pro-preview not in available models"
    assert "gemini-1.5-flash" not in available, "gemini-1.5-flash should NOT be available"
    print(f"✅ Available models: {available}")

from src.core.config import UserConfig

def verify_user_config():
    print("\nChecking UserConfig defaults...")
    # Test defaults directly
    config = UserConfig(api_key="test_key")
    
    assert config.model_name == "gemini-3-pro-preview", f"Expected gemini-3-pro-preview, got {config.model_name}"
    print("✅ UserConfig default model is gemini-3-pro-preview")
    
    assert config.auto_switch_model is False, "Auto switch model should be False"
    print("✅ Auto switch model is False")

def verify_daemon_config():
    print("\nChecking Daemon Config...")
    config = get_config()
    assert config.api.gemini_model == "gemini-3-pro-preview", f"Expected gemini-3-pro-preview, got {config.api.gemini_model}"
    print("✅ Daemon default model is gemini-3-pro-preview")

if __name__ == "__main__":
    try:
        verify_gemini_client()
        verify_user_config()
        verify_daemon_config()
        print("\n🎉 ALL VERIFICATIONS PASSED")
    except AssertionError as e:
        print(f"\n❌ VERIFICATION FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)
