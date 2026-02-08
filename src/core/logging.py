"""Structured logging for Delta Agent.

Provides JSON-formatted logs with file and console output.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from logging.handlers import RotatingFileHandler


class JSONFormatter(logging.Formatter):
    """Format log records as JSON."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, "component"):
            log_data["component"] = record.component
        if hasattr(record, "goal"):
            log_data["goal"] = record.goal
        if hasattr(record, "extension"):
            log_data["extension"] = record.extension
        if hasattr(record, "capability"):
            log_data["capability"] = record.capability
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "success"):
            log_data["success"] = record.success
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add any other extra fields
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)
        
        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """Colored console formatter for human-readable output."""
    
    COLORS = {
        "DEBUG": "\033[36m",    # Cyan
        "INFO": "\033[32m",     # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",    # Red
        "CRITICAL": "\033[35m", # Magenta
    }
    RESET = "\033[0m"
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        
        # Format timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Build prefix
        prefix = f"{color}[{timestamp}] {record.levelname:8}{self.RESET}"
        
        # Add component if present
        if hasattr(record, "component"):
            prefix += f" [{record.component}]"
        
        # Format message
        message = record.getMessage()
        
        # Add extra context on same line if brief
        extras = []
        if hasattr(record, "extension"):
            extras.append(f"ext={record.extension}")
        if hasattr(record, "capability"):
            extras.append(f"cap={record.capability}")
        if hasattr(record, "duration_ms"):
            extras.append(f"time={record.duration_ms:.0f}ms")
        
        if extras:
            message += f" ({', '.join(extras)})"
        
        return f"{prefix} {message}"


class DeltaLogger:
    """Logger wrapper with convenience methods for Delta-specific logging."""
    
    def __init__(self, name: str, logger: logging.Logger):
        self._name = name
        self._logger = logger
    
    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self._log(logging.CRITICAL, message, **kwargs)
    
    def _log(self, level: int, message: str, **kwargs):
        """Log with extra context fields."""
        extra = {}
        
        # Known fields become record attributes
        for key in ["component", "goal", "extension", "capability", "duration_ms", "success"]:
            if key in kwargs:
                extra[key] = kwargs.pop(key)
        
        # Remaining fields go into extra_data
        if kwargs:
            extra["extra_data"] = kwargs
        
        self._logger.log(level, message, extra=extra)
    
    # Convenience methods for common Delta operations
    
    def goal_started(self, goal: str):
        self.info(f"Goal started: {goal}", component="agent", goal=goal)
    
    def goal_completed(self, goal: str, success: bool, duration_ms: float):
        level = logging.INFO if success else logging.WARNING
        self._logger.log(
            level,
            f"Goal {'completed' if success else 'failed'}: {goal}",
            extra={"component": "agent", "goal": goal, "success": success, "duration_ms": duration_ms}
        )
    
    def extension_created(self, name: str, version: str):
        self.info(f"Extension created: {name} v{version}", component="registry", extension=name)
    
    def extension_executed(self, name: str, success: bool, duration_ms: float):
        self.info(
            f"Extension executed: {name}",
            component="executor",
            extension=name,
            success=success,
            duration_ms=duration_ms
        )
    
    def capability_used(self, name: str, success: bool, duration_ms: float):
        self.debug(
            f"Capability used: {name}",
            component="capability",
            capability=name,
            success=success,
            duration_ms=duration_ms
        )
    
    def api_call(self, model: str, tokens: Optional[int] = None, duration_ms: Optional[float] = None):
        self.debug(
            f"API call to {model}",
            component="gemini",
            extra_data={"model": model, "tokens": tokens, "duration_ms": duration_ms}
        )


# Global logger registry
_loggers: dict[str, DeltaLogger] = {}
_initialized = False


def setup_logging(
    level: str = "INFO",
    format_type: str = "json",
    log_dir: Optional[Path] = None,
    file_enabled: bool = True,
    console_enabled: bool = True
) -> None:
    """Initialize the logging system.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: "json" or "text"
        log_dir: Directory for log files
        file_enabled: Write logs to file
        console_enabled: Write logs to console
    """
    global _initialized
    
    if _initialized:
        return
    
    # Get root logger
    root = logging.getLogger("delta")
    root.setLevel(getattr(logging, level.upper()))
    root.handlers.clear()
    
    # Console handler
    if console_enabled:
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.DEBUG)
        
        if format_type == "json":
            console.setFormatter(JSONFormatter())
        else:
            console.setFormatter(ColoredFormatter())
        
        root.addHandler(console)
    
    # File handler
    if file_enabled and log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "delta.log"
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JSONFormatter())
        root.addHandler(file_handler)
    
    _initialized = True


def get_logger(name: str = "delta") -> DeltaLogger:
    """Get a Delta logger instance."""
    if name not in _loggers:
        logger = logging.getLogger(f"delta.{name}")
        _loggers[name] = DeltaLogger(name, logger)
    return _loggers[name]


# Default convenience logger
def debug(message: str, **kwargs): get_logger().debug(message, **kwargs)
def info(message: str, **kwargs): get_logger().info(message, **kwargs)
def warning(message: str, **kwargs): get_logger().warning(message, **kwargs)
def error(message: str, **kwargs): get_logger().error(message, **kwargs)
def critical(message: str, **kwargs): get_logger().critical(message, **kwargs)
