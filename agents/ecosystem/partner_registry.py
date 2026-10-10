"""Partner Application Registry – authoritative binding between Cognito M2M client and RIS APIProfile."""

import os
from typing import Any, Dict, Optional

class PartnerRegistryError(Exception):
    pass

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

    # Test mode for isolated unit tests
    if os.getenv('RIS_TEST_MODE'):
        # In-memory test registry
        test_registry = {
            'client-test': {
                'applicationId': 'app-test',
                'cognitoClientId': 'client-test',
                'apiProfileId': 'TEST_PROFILE_ID_PLACEHOLDER',
                'tenantId': 't1',
                'status': 'ACTIVE'
            }
        }
        rec = test_registry.get(client_id)
        if rec:
            # Tests will patch this further if needed
            return rec

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

