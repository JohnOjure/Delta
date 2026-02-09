"""Audit Logging System.

Records all autonomous actions for accountability, debugging, and self-improvement.
"""

import json
import time
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

class AuditLogger:
    """Logs agent actions to a persistent audit log."""
    
    _instance = None
    
    def __init__(self, log_dir: str | Path = None):
        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            self.log_dir = Path.home() / ".delta" / "audit"
            
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "audit.jsonl"
        
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = AuditLogger()
        return cls._instance
        
    def log_event(self, 
                  action_type: str, 
                  description: str,
                  status: str,
                  details: dict[str, Any] = None,
                  duration_ms: int = 0):
        """Log a structured event."""
        
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "action_type": action_type,
            "description": description,
            "status": status,
            "duration_ms": duration_ms,
            "details": details or {}
        }
        
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            print(f"Failed to write audit log: {e}")

    def log_execution(self, 
                      extension_name: str, 
                      capabilities: list[str], 
                      result: Any, 
                      success: bool,
                      duration_ms: int):
        """Log an extension execution."""
        self.log_event(
            action_type="execution",
            description=f"Executed extension: {extension_name}",
            status="success" if success else "failure",
            duration_ms=duration_ms,
            details={
                "extension": extension_name,
                "capabilities": capabilities,
                "result_summary": str(result)[:500] if result else "None"
            }
        )

    def log_modification(self, 
                         file_path: str, 
                         backup_path: str,
                         success: bool):
        """Log a file modification."""
        self.log_event(
            action_type="modification",
            description=f"Modified file: {file_path}",
            status="success" if success else "failure",
            details={
                "file": str(file_path),
                "backup": str(backup_path)
            }
        )

    def log_rollback(self, 
                     backup_id: str, 
                     files_restored: list[str]):
        """Log a rollback event."""
        self.log_event(
            action_type="rollback",
            description=f"Rolled back backup {backup_id}",
            status="success",
            details={
                "backup_id": backup_id,
                "files": files_restored
            }
        )
