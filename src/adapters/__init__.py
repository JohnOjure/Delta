"""Adapters package - environment-specific interfaces."""

from .base import BaseAdapter
from .desktop import DesktopAdapter

__all__ = ["BaseAdapter", "DesktopAdapter"]
