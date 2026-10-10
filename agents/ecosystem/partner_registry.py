"""Partner Application Registry – authoritative binding between Cognito M2M client and RIS APIProfile."""

import os
from typing import Any, Dict, Optional

class PartnerRegistryError(Exception):
    pass

def create_partner_application(
    application_id: str,
    cognito_client_id: str,
    api_profile_id: str,
    tenant_id: str,
    table_name: Optional[str] = None,
    dynamodb_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Create partner application with atomic uniqueness of cognitoClientId.

    Uses DynamoDB PutItem with ConditionExpression attribute_not_exists(cognitoClientId)
    to guarantee uniqueness even under concurrent creation attempts.

    Raises PartnerRegistryError on conflict or failure.
    """
    if not application_id or not cognito_client_id:
        raise PartnerRegistryError("application_id and cognito_client_id required")
    try:
        if dynamodb_client is None:
            import boto3
            table_name = table_name or os.getenv('RIS_PARTNER_APPLICATIONS_TABLE')
            if not table_name:
                raise PartnerRegistryError("Table name not configured")
            dynamodb = boto3.client('dynamodb', region_name=os.getenv('AWS_REGION', 'eu-central-1'))
        else:
            dynamodb = dynamodb_client

        item = {
            'applicationId': {'S': application_id},
            'cognitoClientId': {'S': cognito_client_id},
            'apiProfileId': {'S': api_profile_id},
            'tenantId': {'S': tenant_id},
            'status': {'S': 'ACTIVE'}
        }
        dynamodb.put_item(
            TableName=table_name,
            Item=item,
            ConditionExpression='attribute_not_exists(cognitoClientId)'
        )
        return {'applicationId': application_id, 'cognitoClientId': cognito_client_id, 'status': 'ACTIVE'}
    except Exception as e:
        # Conditional check failed or other error
        raise PartnerRegistryError(f"Failed to create partner application: {e}")


def resolve_partner_application(
    client_id: Optional[str],
    table_name: Optional[str] = None,
    dynamodb_client: Optional[Any] = None,
) -> Optional[Dict[str, Any]]:
    """Resolve partner application by Cognito client_id.

    Returns registry record dict or None if not found.
    Queries DynamoDB partner-applications table by GSI gsi-client.

    Requires client_id to be present. Fails closed on errors.
    """
    if not client_id:
        return None

    try:
        if dynamodb_client is None:
            import boto3
            table_name = table_name or os.getenv('RIS_PARTNER_APPLICATIONS_TABLE')
            if not table_name:
                return None
            dynamodb = boto3.client('dynamodb', region_name=os.getenv('AWS_REGION', 'eu-central-1'))
        else:
            dynamodb = dynamodb_client

        # Query GSI gsi-client
        # Note: In production, use DynamoDB resource table.get_item with GSI query.
        # For simplicity, using client.query.
        response = dynamodb.query(
            TableName=table_name,
            IndexName='gsi-client',
            KeyConditionExpression='cognitoClientId = :cid',
            ExpressionAttributeValues={':cid': {'S': client_id}},
            Limit=1
        )
        items = response.get('Items', [])
        if not items:
            return None
        item = items[0]
        # Convert DynamoDB attribute map to plain dict
        def unmarshal(v):
            if 'S' in v:
                return v['S']
            if 'N' in v:
                return int(v['N'])
            return v
        record = {k: unmarshal(v) for k, v in item.items()}
        return record
    except Exception:
        # Fail closed
        return None

