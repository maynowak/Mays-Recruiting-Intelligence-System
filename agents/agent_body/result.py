"""
Agent Result Handler

Standardizes result formatting for agent execution.
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentResultHandler:
    """
    Handles result formatting and validation.
    """

    @staticmethod
    def success(
        work_id: str,
        data: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a success result."""
        result = {'success': True}
        if data is not None:
            result['data'] = data
        if metrics:
            result['metrics'] = metrics
        return result

    @staticmethod
    def error(
        work_id: str,
        message: str,
        error_type: str = "ERROR",
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create an error result."""
        result = {
            'success': False,
            'error': {
                'message': message,
                'type': error_type,
                'workId': work_id
            }
        }
        if details:
            result['error']['details'] = details
        return result

    @staticmethod
    def format_response(result: Dict[str, Any], work_id: str) -> Dict[str, Any]:
        """Format result for API response."""
        response = {'result': result}
        if 'metrics' in result:
            response['workId'] = work_id
        return response