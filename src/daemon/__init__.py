# Delta Daemon Module
"""Provides background service functionality for Delta agent."""

from .service import DeltaService
from .manager import ServiceManager

__all__ = ["DeltaService", "ServiceManager"]
