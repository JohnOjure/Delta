"""Custom exceptions for Delta Agent.

Provides user-friendly error messages and structured error handling.
"""

from typing import Optional, Any


class DeltaError(Exception):
    """Base exception for all Delta errors.
    
    Provides:
    - User-friendly message
    - Technical details for debugging
    - Suggested fixes when applicable
    """
    
    def __init__(
        self,
        message: str,
        details: Optional[str] = None,
        suggestion: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        self.message = message
        self.details = details
        self.suggestion = suggestion
        self.cause = cause
        super().__init__(message)
    
    def format_user_friendly(self) -> str:
        """Format error for display to user."""
        parts = [f"❌ {self.message}"]
        
        if self.details:
            parts.append(f"   Details: {self.details}")
        
        if self.suggestion:
            parts.append(f"   💡 Try: {self.suggestion}")
        
        return "\n".join(parts)
    
    def __str__(self) -> str:
        return self.format_user_friendly()


class ConfigError(DeltaError):
    """Configuration-related errors."""
    
    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        suggestion = kwargs.pop("suggestion", None)
        if not suggestion and config_key:
            suggestion = f"Set the {config_key} environment variable or add it to .env"
        super().__init__(message, suggestion=suggestion, **kwargs)
        self.config_key = config_key


class APIError(DeltaError):
    """API-related errors (Gemini, etc.)."""
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        suggestion = kwargs.pop("suggestion", None)
        if not suggestion:
            if status_code == 429:
                suggestion = f"Rate limited. Wait {retry_after or 60} seconds and try again"
            elif status_code == 401:
                suggestion = "Check your API key is valid and has not expired"
            elif status_code == 403:
                suggestion = "Your API key may not have access to this model"
        
        super().__init__(message, suggestion=suggestion, **kwargs)
        self.status_code = status_code
        self.retry_after = retry_after


class ExecutionError(DeltaError):
    """Errors during extension execution."""
    
    def __init__(
        self,
        message: str,
        extension_name: Optional[str] = None,
        traceback: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", None)
        if not details and extension_name:
            details = f"Extension: {extension_name}"
        
        super().__init__(message, details=details, **kwargs)
        self.extension_name = extension_name
        self.traceback = traceback


class CapabilityError(DeltaError):
    """Errors related to capabilities."""
    
    def __init__(
        self,
        message: str,
        capability_name: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", None)
        if not details:
            parts = []
            if capability_name:
                parts.append(f"Capability: {capability_name}")
            if operation:
                parts.append(f"Operation: {operation}")
            if parts:
                details = ", ".join(parts)
        
        super().__init__(message, details=details, **kwargs)
        self.capability_name = capability_name
        self.operation = operation


class SandboxError(DeltaError):
    """Sandbox-related security errors."""
    
    def __init__(
        self,
        message: str,
        blocked_operation: Optional[str] = None,
        **kwargs
    ):
        suggestion = kwargs.pop("suggestion", None)
        if not suggestion:
            suggestion = "The operation was blocked for security. Use allowed capabilities instead."
        
        super().__init__(message, suggestion=suggestion, **kwargs)
        self.blocked_operation = blocked_operation


class TimeoutError(DeltaError):
    """Execution timeout errors."""
    
    def __init__(
        self,
        message: str,
        timeout_seconds: Optional[float] = None,
        **kwargs
    ):
        suggestion = kwargs.pop("suggestion", None)
        if not suggestion:
            suggestion = "Consider breaking the task into smaller steps"
        
        details = kwargs.pop("details", None)
        if not details and timeout_seconds:
            details = f"Timeout after {timeout_seconds}s"
        
        super().__init__(message, details=details, suggestion=suggestion, **kwargs)
        self.timeout_seconds = timeout_seconds


class ValidationError(DeltaError):
    """Input validation errors."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs
    ):
        details = kwargs.pop("details", None)
        if not details and field:
            details = f"Field: {field}"
            if value is not None:
                details += f", Value: {repr(value)[:50]}"
        
        super().__init__(message, details=details, **kwargs)
        self.field = field
        self.value = value


class ExtensionError(DeltaError):
    """Extension-related errors."""
    
    def __init__(
        self,
        message: str,
        extension_name: Optional[str] = None,
        version: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", None)
        if not details:
            parts = []
            if extension_name:
                parts.append(f"Extension: {extension_name}")
            if version:
                parts.append(f"Version: {version}")
            if parts:
                details = ", ".join(parts)
        
        super().__init__(message, details=details, **kwargs)
        self.extension_name = extension_name
        self.version = version


def format_exception_chain(error: Exception, max_depth: int = 5) -> str:
    """Format an exception chain for display.
    
    Handles nested exceptions and provides clean output.
    """
    lines = []
    current = error
    depth = 0
    
    while current and depth < max_depth:
        if isinstance(current, DeltaError):
            lines.append(current.format_user_friendly())
        else:
            lines.append(f"❌ {type(current).__name__}: {current}")
        
        current = getattr(current, "__cause__", None) or getattr(current, "cause", None)
        depth += 1
        
        if current:
            lines.append("   Caused by:")
    
    return "\n".join(lines)
