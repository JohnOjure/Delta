"""Configuration manager for Delta Agent.

Handles loading, saving, and validating user settings.
"""

import json
import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

# Default configuration path
DEFAULT_CONFIG_DIR = Path.home() / ".delta"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.json"


class UserConfig(BaseModel):
    """User configuration model."""
    api_key: str = Field(..., description="Gemini API Key")
    model_name: str = Field(default="gemini-3-pro-preview", description="Preferred Gemini model")
    user_name: str = Field(default="User", description="User's preferred name")
    usage_limit: int = Field(default=100, description="Daily request limit")
    
    # Advanced settings
    auto_switch_model: bool = Field(default=False, description="Automatically switch models on failure")
    voice_enabled: bool = Field(default=False, description="Enable voice output by default")


class ConfigManager:
    """Manages application configuration."""
    
    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        self._config: Optional[UserConfig] = None
    
    @property
    def config(self) -> UserConfig:
        """Get the current configuration."""
        if self._config is None:
            self.load()
        return self._config
        
    def load(self) -> UserConfig:
        """Load configuration from disk."""
        if not self.config_path.exists():
            return None
            
        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
            self._config = UserConfig(**data)
            return self._config
        except Exception as e:
            print(f"Error loading config: {e}")
            return None
            
    def save(self, config: UserConfig) -> None:
        """Save configuration to disk."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, "w") as f:
            f.write(config.model_dump_json(indent=2))
        
        self._config = config
        
    def exists(self) -> bool:
        """Check if configuration exists."""
        return self.config_path.exists()

    def update(self, **kwargs) -> UserConfig:
        """Update configuration with new values."""
        if self._config is None:
            raise ValueError("Config not loaded")
            
        current_data = self._config.dict()
        current_data.update(kwargs)
        
        new_config = UserConfig(**current_data)
        self.save(new_config)
        return new_config
