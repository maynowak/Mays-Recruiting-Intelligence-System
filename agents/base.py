from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


class AgentBase(ABC):
    """
    Base class for all agents in the Ground Zero platform.
    
    All agents must inherit from this class and implement the required methods.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the agent.
        
        Args:
            config: Agent configuration from environment or parameters
        """
        self.config = config or {}
        self.name = self.__class__.__name__
    
    @abstractmethod
    def process_work(self, work_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a work item and return the result.
        
        Args:
            work_item: Work item to process
            
        Returns:
            Result dictionary with:
                - success: bool
                - data: Optional result data
                - error: Optional error message
        """
        pass
    
    @abstractmethod
    def validate_work(self, work_item: Dict[str, Any]) -> bool:
        """
        Validate a work item before processing.
        
        Args:
            work_item: Work item to validate
            
        Returns:
            True if valid, False otherwise
        """
        pass
    
    @abstractmethod
    def get_status(self, work_id: str, tenant_id: str) -> Dict[str, Any]:
        """
        Get the status of a work item.
        
        Args:
            work_id: Work item ID
            tenant_id: Tenant ID
            
        Returns:
            Status dictionary
        """
        pass
    
    def handle_error(self, error: Exception, work_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an error during processing.
        
        Args:
            error: The exception that occurred
            work_item: The work item being processed
            
        Returns:
            Error result dictionary
        """
        logger.error(f"Error processing work {work_item.get('workId')}: {str(error)}")
        return {
            'success': False,
            'error': {
                'message': str(error),
                'type': type(error).__name__,
                'workId': work_item.get('workId')
            }
        }
    
    def get_retry_delay(self, attempt: int, base_delay: float = 1.0) -> float:
        """
        Calculate exponential backoff delay.
        
        Args:
            attempt: Current attempt number
            base_delay: Base delay in seconds
            
        Returns:
            Delay in seconds
        """
        import random
        delay = base_delay * (2 ** (attempt - 1))
        jitter = random.uniform(0, 0.1)
        return delay + jitter


class WorkItemStatus:
    """Constants for work item statuses."""
    CREATED = 'CREATED'
    QUEUED = 'QUEUED'
    RUNNING = 'RUNNING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    RETRY = 'RETRY'
    DEAD_LETTER = 'DEAD_LETTER'
    CANCELLED = 'CANCELLED'
    EXPIRED = 'EXPIRED'


class WorkItem:
    """WorkItem data model."""
    
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self._validate()
    
    def _validate(self):
        """Validate required fields."""
        required = ['workId', 'type', 'tenantId', 'idempotencyKey']
        for field in required:
            if field not in self.data:
                raise ValueError(f"Missing required field: {field}")
    
    @property
    def work_id(self) -> str:
        return self.data['workId']
    
    @property
    def work_type(self) -> str:
        return self.data['type']
    
    @property
    def tenant_id(self) -> str:
        return self.data['tenantId']
    
    @property
    def idempotency_key(self) -> str:
        return self.data['idempotencyKey']
    
    @property
    def status(self) -> str:
        return self.data.get('status', WorkItemStatus.CREATED)
    
    def to_dict(self) -> Dict[str, Any]:
        return self.data.copy()


def create_lambda_handler(agent_class, config: Optional[Dict[str, Any]] = None):
    """
    Factory function to create a Lambda handler for an agent.
    
    Args:
        agent_class: The agent class to use
        config: Optional configuration for the agent
        
    Returns:
        Lambda handler function
    """
    agent = agent_class(config)
    
    def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        results = []
        
        for record in event.get('Records', []):
            try:
                body = json.loads(record['body'])
                work_item = body if isinstance(body, dict) else json.loads(body)
                
                result = agent.process_work(work_item)
                results.append({'workId': work_item.get('workId'), 'result': result})
                
            except Exception as e:
                results.append({
                    'workId': record.get('messageId'),
                    'error': str(e)
                })
        
        return {
            'statusCode': 200,
            'body': json.dumps({'processed': len(event.get('Records', [])), 'results': results})
        }
    
    return handler