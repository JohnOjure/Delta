"""Centralized configuration for Delta Agent.

This module provides typed, validated configuration loaded from
environment variables and .env files.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()


@dataclass
class APIConfig:
    """API configuration."""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-pro-preview"
    
    def __post_init__(self):
        if not self.gemini_api_key:
            self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")


@dataclass
class ExecutionConfig:
    """Execution and sandbox configuration."""
    max_iterations: int = 10
    cpu_time_seconds: float = 30.0
    memory_mb: int = 128
    timeout_seconds: float = 300.0
    
    def __post_init__(self):
        self.max_iterations = int(os.getenv("DELTA_MAX_ITERATIONS", self.max_iterations))
        self.cpu_time_seconds = float(os.getenv("DELTA_CPU_TIME", self.cpu_time_seconds))
        self.memory_mb = int(os.getenv("DELTA_MEMORY_MB", self.memory_mb))
        self.timeout_seconds = float(os.getenv("DELTA_TIMEOUT", self.timeout_seconds))


@dataclass
class PathConfig:
    """Path configuration."""
    data_dir: Path = field(default_factory=lambda: Path("./data"))
    extensions_db: Path = field(default_factory=lambda: Path("./data/extensions.db"))
    memory_db: Path = field(default_factory=lambda: Path("./data/memory.db"))
    logs_dir: Path = field(default_factory=lambda: Path("./data/logs"))
    
    def __post_init__(self):
        base = os.getenv("DELTA_DATA_DIR")
        if base:
            self.data_dir = Path(base)
            self.extensions_db = self.data_dir / "extensions.db"
            self.memory_db = self.data_dir / "memory.db"
            self.logs_dir = self.data_dir / "logs"
        
        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class WebConfig:
    """Web server configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    def __post_init__(self):
        self.host = os.getenv("DELTA_WEB_HOST", self.host)
        self.port = int(os.getenv("DELTA_WEB_PORT", self.port))
        self.debug = os.getenv("DELTA_DEBUG", "false").lower() == "true"


@dataclass
class LogConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "json"  # "json" or "text"
    file_enabled: bool = True
    console_enabled: bool = True
    
    def __post_init__(self):
        self.level = os.getenv("DELTA_LOG_LEVEL", self.level).upper()
        self.format = os.getenv("DELTA_LOG_FORMAT", self.format).lower()
        self.file_enabled = os.getenv("DELTA_LOG_FILE", "true").lower() == "true"
        self.console_enabled = os.getenv("DELTA_LOG_CONSOLE", "true").lower() == "true"


@dataclass
class Config:
    """Main configuration container."""
    api: APIConfig = field(default_factory=APIConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    web: WebConfig = field(default_factory=WebConfig)
    log: LogConfig = field(default_factory=LogConfig)
    
    def validate(self) -> list[str]:
        """Validate configuration and return list of issues."""
        issues = []
        
        if not self.api.gemini_api_key:
            issues.append("GEMINI_API_KEY is required but not set")
        
        if self.execution.max_iterations < 1:
            issues.append("max_iterations must be at least 1")
        
        if self.execution.cpu_time_seconds <= 0:
            issues.append("cpu_time_seconds must be positive")
        
        return issues
    
    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        return len(self.validate()) == 0


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def reset_config() -> None:
    """Reset the global configuration (useful for testing)."""
    global _config
    _config = None
