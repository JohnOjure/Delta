"""Optimization Engine.

Analyzes audit logs to identify performance bottlenecks and reliability issues.
Suggests self-improvement tasks to the agent.
"""

import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any
from collections import defaultdict
import statistics

@dataclass
class OptimizationSuggestion:
    target_type: str  # "extension", "workflow", "system"
    target_name: str
    issue: str        # "slow_execution", "high_failure_rate"
    severity: str     # "low", "medium", "high"
    data: Dict[str, Any]
    suggested_action: str

class OptimizationEngine:
    """Analyzes agent performance and suggests improvements."""
    
    def __init__(self, log_dir: str | Path = None):
        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            self.log_dir = Path.home() / ".delta" / "audit"
        self.log_file = self.log_dir / "audit.jsonl"
        
    def analyze_performance(self) -> List[OptimizationSuggestion]:
        """Analyze audit logs and generate suggestions."""
        if not self.log_file.exists():
            return []
            
        events = []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line))
        except Exception as e:
            print(f"Error reading audit log: {e}")
            return []
            
        suggestions = []
        
        # 1. Analyze Extension Performance
        suggestions.extend(self._analyze_extensions(events))
        
        return suggestions
        
    def _analyze_extensions(self, events: List[dict]) -> List[OptimizationSuggestion]:
        """Analyze extension execution metrics."""
        ext_stats = defaultdict(lambda: {"durations": [], "failures": 0, "total": 0})
        
        for e in events:
            if e.get("action_type") == "execution" and e.get("details"):
                ext_name = e["details"].get("extension")
                if not ext_name:
                    continue
                    
                stats = ext_stats[ext_name]
                stats["total"] += 1
                
                if e.get("status") == "failure":
                    stats["failures"] += 1
                
                dur = e.get("duration_ms", 0)
                if dur > 0:
                    stats["durations"].append(dur)
        
        suggestions = []
        
        for name, stats in ext_stats.items():
            # Check Failure Rate
            if stats["total"] >= 3:
                fail_rate = stats["failures"] / stats["total"]
                if fail_rate > 0.3: # >30% failure
                    suggestions.append(OptimizationSuggestion(
                        target_type="extension",
                        target_name=name,
                        issue="high_failure_rate",
                        severity="high",
                        data={"failure_rate": fail_rate, "total_runs": stats["total"]},
                        suggested_action=f"Refactor extension '{name}' to improve reliability. Failure rate is {fail_rate:.1%}."
                    ))
            
            # Check Performance
            if stats["durations"]:
                avg_dur = statistics.mean(stats["durations"])
                if avg_dur > 2000: # > 2 seconds
                     suggestions.append(OptimizationSuggestion(
                        target_type="extension",
                        target_name=name,
                        issue="slow_execution",
                        severity="medium",
                        data={"avg_duration_ms": avg_dur},
                        suggested_action=f"Optimize extension '{name}'. Average execution time is {avg_dur:.0f}ms."
                    ))
                    
        return suggestions
