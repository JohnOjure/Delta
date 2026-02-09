"""Safety and Rollback System.

Ensures system stability by backing up files before modification and 
providing mechanisms to rollback destructive changes.
"""

import shutil
import uuid
import ast
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

class SafetyManager:
    """Manages file safety, backups, and health checks."""
    
    _instance = None
    
    def __init__(self, backup_dir: str | Path = None):
        if backup_dir:
            self.backup_dir = Path(backup_dir)
        else:
            self.backup_dir = Path.home() / ".delta" / "backups"
            
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        # Store active backups for current session
        self._active_backups: Dict[str, Dict[str, str]] = {} 
        
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = SafetyManager()
        return cls._instance
        
    def create_backup(self, paths: List[str | Path]) -> str:
        """Create a backup of specified files.
        
        Args:
            paths: List of file paths to backup.
            
        Returns:
            backup_id: Unique identifier for this backup set.
        """
        backup_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        backup_path = self.backup_dir / backup_id
        backup_path.mkdir()
        
        mapping = {}
        
        for p in paths:
            src = Path(p).resolve()
            if src.exists() and src.is_file():
                # Replicate folder structure in backup to avoid name collisions
                # e.g. src/core/agent.py -> backup/src/core/agent.py
                # But for simplicity, we flatten if names unique, or just hash.
                # Better: keep relative path structure relative to project root? 
                # Or just flat map. Flat map is easier for restore if we track it.
                
                start = Path.cwd()
                try:
                    rel_path = src.relative_to(start)
                except ValueError:
                    # Outside CWD, just use name + hash
                    rel_path = Path(src.name)
                
                dest = backup_path / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                
                shutil.copy2(src, dest)
                mapping[str(src)] = str(dest)
                
        self._active_backups[backup_id] = mapping
        return backup_id
        
    def restore_backup(self, backup_id: str) -> List[str]:
        """Restore files from a backup.
        
        Args:
            backup_id: The ID to restore.
            
        Returns:
            List of restored file paths.
        """
        if backup_id not in self._active_backups:
            # Try to load from disk if not in memory? 
            # For now, simplistic session-based or assumed path structure.
            # If map is lost, we can't easily restore without metadata file.
            # Let's assume restoration happens immediately after failure in same session.
            return []
            
        mapping = self._active_backups[backup_id]
        restored = []
        
        for original_path, backup_path_str in mapping.items():
            try:
                backup_file = Path(backup_path_str)
                target_file = Path(original_path)
                
                if backup_file.exists():
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_file, target_file)
                    restored.append(original_path)
            except Exception as e:
                print(f"Failed to restore {original_path}: {e}")
                
        return restored
        
    def verify_syntax(self, paths: List[str | Path]) -> bool:
        """Check if python files have valid syntax."""
        all_valid = True
        for p in paths:
            path = Path(p)
            if path.suffix == ".py" and path.exists():
                try:
                    ast.parse(path.read_text(encoding="utf-8"))
                except (SyntaxError, Exception):
                    return False
        return True
        
    def check_health(self) -> bool:
        """Run comprehensive system health checks.
        
        Can include:
        1. Syntax check of core modules.
        2. Connectivity check.
        """
        # Minimal check: syntax of CWD python files? Too slow.
        # Just check critical core files.
        critical_files = [
            "src/core/agent.py",
            "src/vm/executor.py",
            "src/core/gemini_client.py"
        ]
        
        # Adjust paths relative to current working dir or known location
        base = Path.cwd()
        to_check = []
        for cf in critical_files:
            p = base / cf
            if p.exists():
                to_check.append(p)
                
        return self.verify_syntax(to_check)
