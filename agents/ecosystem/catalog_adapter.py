"""
Agent Catalog Adapter

Bridges the persistent DynamoDB agent_catalog to the runtime AgentRegistry.

This adapter provides:
- Reading agent definitions from DynamoDB
- Converting to AgentDescriptor format
- Populating the runtime registry
- Supporting tenant-specific agent visibility

Usage:
    from agents.ecosystem.catalog_adapter import CatalogAdapter
    
    adapter = CatalogAdapter(table_name='agent-catalog')
    agent_ids = adapter.scan_all_agent_ids()
    
    for agent_id in agent_ids:
        descriptor = adapter.get_descriptor(agent_id)
        if descriptor:
            registry.register(agent_id, descriptor)
"""

import logging
import os
from typing import Dict, List, Optional, Any

from agents.ecosystem.agent_status import normalize_agent_status
from agents.ecosystem.registry import AgentDescriptor, ExecutionProfile

logger = logging.getLogger(__name__)


class CatalogAdapter:
    """
    Adapts DynamoDB agent_catalog to AgentRegistry.
    
    Provides methods to read from DynamoDB and convert items
    to AgentDescriptor objects.
    """
    
    def __init__(self, table_name: Optional[str] = None, dynamodb=None):
        """
        Initialize the catalog adapter.
        
        Args:
            table_name: DynamoDB table name (from env if not provided)
            dynamodb: DynamoDB resource (created if not provided)
        """
        self.table_name = table_name or os.environ.get('AGENT_CATALOG_TABLE')
        self._dynamodb = dynamodb
        self._table = None
    
    @property
    def table(self):
        """Lazily get the DynamoDB table."""
        if self._table is None:
            if not self._dynamodb:
                import boto3
                self._dynamodb = boto3.resource('dynamodb')
            self._table = self._dynamodb.Table(self.table_name) if self.table_name else None
        return self._table
    
    def scan_all_agent_ids(self) -> List[str]:
        """
        Get all agent IDs from the catalog.
        
        Returns:
            List of agent IDs
        """
        if not self.table:
            logger.warning("DynamoDB table not configured")
            return []
        
        try:
            response = self.table.scan(
                ProjectionExpression='agentId'
            )
            return [item.get('agentId') for item in response.get('Items', []) if item.get('agentId')]
        except Exception as e:
            logger.error(f"Error scanning agent catalog: {e}")
            return []
    
    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get raw agent data from DynamoDB.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Agent data dict or None
        """
        if not self.table:
            logger.warning("DynamoDB table not configured")
            return None
        
        try:
            response = self.table.get_item(
                Key={'agentId': agent_id},
                ProjectionExpression='agentId, #s, version, capabilities, description, runtime, bodyVersion, config, metadata',
                ExpressionAttributeNames={'#s': 'status'}
            )
            return response.get('Item')
        except Exception as e:
            logger.error(f"Error getting agent {agent_id}: {e}")
            return None
    
    def get_all_agents(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all agents from the catalog.
        
        Returns:
            Dict mapping agent_id to agent data
        """
        if not self.table:
            logger.warning("DynamoDB table not configured")
            return {}
        
        try:
            response = self.table.scan()
            agents = {}
            for item in response.get('Items', []):
                agent_id = item.get('agentId')
                if agent_id:
                    agents[agent_id] = item
            return agents
        except Exception as e:
            logger.error(f"Error scanning agent catalog: {e}")
            return {}


def populate_registry_from_catalog(registry, table_name: Optional[str] = None,
                                   dynamodb=None) -> int:
    """
    Populate an AgentRegistry from the DynamoDB catalog.

    This is the main entry point for initializing the registry.

    Args:
        registry: AgentRegistry instance to populate
        table_name: DynamoDB table name (optional)
        dynamodb: optional DynamoDB resource; when omitted the adapter
            creates its own (unchanged production behaviour). Injected
            in tests so the read path can be verified without AWS.

    Returns:
        Number of agents registered
    """
    from agents.ecosystem.registry import AgentDescriptor, AgentStatus, ExecutionProfile
    
    adapter = CatalogAdapter(table_name, dynamodb=dynamodb)
    agents = adapter.get_all_agents()
    
    count = 0
    for agent_id, agent_data in agents.items():
        try:
            descriptor = _convert_to_descriptor(agent_data)
            if descriptor:
                registry.register(agent_id, descriptor)
                count += 1
        except Exception as e:
            logger.error(f"Error registering agent {agent_id}: {e}")
    
    logger.info(f"Populated registry with {count} agents from catalog")
    return count


def _convert_to_descriptor(agent_data: Dict[str, Any]) -> Optional[AgentDescriptor]:
    """
    Convert DynamoDB item to an AgentDescriptor.

    Args:
        agent_data: Raw agent data from DynamoDB

    Returns:
        AgentDescriptor, or None when the item has no agentId or its
        status is unknown/None/empty (fail-closed: blocked agents are
        never registered).
    """
    if not agent_data or not agent_data.get('agentId'):
        return None
    
    # Central status decision (fail-closed): unknown / None / empty
    # values are NOT registered (blocked), never defaulted to ACTIVE.
    # Persisted DDB values stay untouched — normalization only.
    status = normalize_agent_status(agent_data.get('status'))
    if status is None:
        logger.warning(
            "Skipping agent %s: unsupported status %r (fail-closed)",
            agent_data.get('agentId'), agent_data.get('status'))
        return None
    
    return AgentDescriptor(
        agent_id=agent_data['agentId'],
        name=agent_data.get('name', agent_data['agentId']),
        version=agent_data.get('version', '1.0.0'),
        status=status,
        capabilities=agent_data.get('capabilities', []),
        supported_bodies=agent_data.get('supported_bodies', ['1.0.0']),
        supported_runtimes=agent_data.get('supported_runtimes', ['python3.14']),
        execution_profile=ExecutionProfile.LAMBDA,
        risk_level=agent_data.get('risk_level', 'low'),
        description=agent_data.get('description', ''),
        metadata=agent_data.get('metadata', {}),
    )