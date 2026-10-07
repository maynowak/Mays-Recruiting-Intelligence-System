"""
Agent Monitor

Provides observability for agent execution.
"""

import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime
from functools import wraps

logger = logging.getLogger(__name__)

from agents.timeutil import utcnow_naive_iso



class AgentMonitor:
    """
    Monitors agent execution with metrics and logging.
    """

    def __init__(self):
        self._metrics = {}

    def record(self, work_id: str, agent_id: Optional[str] = None, duration_ms: float = 0, success: bool = True):
        """Record execution metrics."""
        self._metrics[work_id] = {
            'workId': work_id,
            'agentId': agent_id,
            'durationMs': duration_ms,
            'success': success,
            'timestamp': utcnow_naive_iso()
        }

    def wrap(self, func):
        """Decorator to wrap agent functions with monitoring."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            work_id = kwargs.get('work_id') or (args[0].get('workId') if args else None)
            
            try:
                result = func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                success = result.get('success', True)
                self.record(work_id, duration_ms=duration, success=success)
                return result
            except Exception as e:
                duration = (time.time() - start) * 1000
                self.record(work_id, duration_ms=duration, success=False)
                raise
        return wrapper

    def get_metrics(self, work_id: Optional[str] = None) -> Dict[str, Any]:
        """Get recorded metrics."""
        if work_id:
            return self._metrics.get(work_id, {})
        return self._metrics


# Global monitor instance
_monitor = AgentMonitor()


def get_monitor() -> AgentMonitor:
    """Get the global monitor instance."""
    return _monitor