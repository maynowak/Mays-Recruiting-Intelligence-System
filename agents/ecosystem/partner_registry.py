"""Partner Application Registry – authoritative binding between Cognito M2M client and RIS APIProfile."""

import os
from typing import Any, Dict, Optional

class PartnerRegistryError(Exception):
    pass

CLIENT_RESERVATION_PREFIX = "CLIENT#"


def create_partner_application(
    application_id: str,
    cognito_client_id: str,
    api_profile_id: str,
    tenant_id: str,
    table_name: Optional[str] = None,
    dynamodb_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Create partner application with atomic uniqueness of BOTH applicationId
    and cognitoClientId.

    Uses DynamoDB TransactWriteItems with two conditional Put operations:

      1. The application record (PK = applicationId) guarded by
         `attribute_not_exists(applicationId)`.
      2. A client-ID reservation item (PK = "CLIENT#<cognitoClientId>")
         guarded by `attribute_not_exists(applicationId)`.

    Both writes succeed or both fail, so a Cognito client ID can never be
    bound to two applications even under concurrent registration.

    A separate item per cognitoClientId is required because DynamoDB GSIs do
    NOT enforce uniqueness. Reserving the client ID as a real primary key is
    the only way to get a database-level uniqueness guarantee while staying in
    the existing table and keeping `resolve_partner_application` unchanged.

    Raises PartnerRegistryError on conflict or failure.
    """
    if not application_id or not cognito_client_id:
        raise PartnerRegistryError("application_id and cognito_client_id required")
    # `CLIENT#` is the reserved primary-key namespace for client-ID reservation
    # items. An applicationId inside that namespace would be indistinguishable
    # from a reservation, would be invisible to resolve/list, and would burn a
    # client ID. Reject it instead of corrupting the registry.
    if application_id.startswith(CLIENT_RESERVATION_PREFIX):
        raise PartnerRegistryError(
            "application_id must not start with the reserved prefix "
            f"{CLIENT_RESERVATION_PREFIX!r}")
    try:
        if dynamodb_client is None:
            import boto3
            table_name = table_name or os.getenv('RIS_PARTNER_APPLICATIONS_TABLE')
            if not table_name:
                raise PartnerRegistryError("Table name not configured")
            dynamodb = boto3.client('dynamodb', region_name=os.getenv('AWS_REGION', 'eu-central-1'))
        else:
            dynamodb = dynamodb_client

        application_item = {
            'applicationId': {'S': application_id},
            'cognitoClientId': {'S': cognito_client_id},
            'apiProfileId': {'S': api_profile_id},
            'tenantId': {'S': tenant_id},
            'status': {'S': 'ACTIVE'}
        }
        reservation_item = {
            'applicationId': {'S': CLIENT_RESERVATION_PREFIX + cognito_client_id},
            'cognitoClientId': {'S': cognito_client_id},
            'reservedForApplicationId': {'S': application_id},
            'status': {'S': 'RESERVED'}
        }

        dynamodb.transact_write_items(
            TransactItems=[
                {
                    'Put': {
                        'TableName': table_name,
                        'Item': application_item,
                        'ConditionExpression': 'attribute_not_exists(applicationId)'
                    }
                },
                {
                    'Put': {
                        'TableName': table_name,
                        'Item': reservation_item,
                        'ConditionExpression': 'attribute_not_exists(applicationId)'
                    }
                }
            ]
        )
        return {'applicationId': application_id,
                'cognitoClientId': cognito_client_id,
                'status': 'ACTIVE'}
    except Exception as e:
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

        # Step 1: locate the application via GSI gsi-client.
        # GSI results for a client ID contain BOTH the application record and
        # the "CLIENT#<clientId>" reservation item, so a single-item page would
        # be non-deterministic. Page through until a real record is found.
        #
        # DynamoDB GSIs support EVENTUAL CONSISTENCY ONLY. ConsistentRead on a
        # GSI query does not make the index current, so a deactivated partner
        # can still appear here for the propagation window. That is exactly why
        # this function does NOT trust the GSI result as authoritative - see
        # step 2 below.
        start_key = None
        items = []
        while True:
            request: Dict[str, Any] = {
                'TableName': table_name,
                'IndexName': 'gsi-client',
                'KeyConditionExpression': 'cognitoClientId = :cid',
                'ExpressionAttributeValues': {':cid': {'S': client_id}},
                'Limit': 10,
            }
            if start_key:
                request['ExclusiveStartKey'] = start_key
            response = dynamodb.query(**request)
            items.extend(response.get('Items', []))
            start_key = response.get('LastEvaluatedKey')
            if not start_key:
                break
        # Reservation items (PK = "CLIENT#<clientId>") share the cognitoClientId
        # attribute and therefore also appear in gsi-client. Skip them so the
        # caller always receives the real application record.
        for item in items:
            raw_id = item.get('applicationId', {})
            if isinstance(raw_id, dict) and 'S' in raw_id:
                if raw_id['S'].startswith(CLIENT_RESERVATION_PREFIX):
                    continue
            elif isinstance(raw_id, str) and raw_id.startswith(CLIENT_RESERVATION_PREFIX):
                continue
            # unmarshal and return
            def unmarshal(v):
                if 'S' in v:
                    return v['S']
                if 'N' in v:
                    return int(v['N'])
                return v
            application_id = unmarshal(item.get('applicationId', {}))

            # Step 2: re-read the application from the BASE table.
            #
            # The GSI result is only a locator. Because GSI reads are always
            # eventually consistent, an application deactivated moments ago can
            # still be returned here as ACTIVE. A base-table GetItem IS
            # strongly consistent, so this second read is what actually makes
            # revocation take effect immediately on the authorization hot path.
            #
            # If the base read disagrees with the index, the index is stale and
            # the authoritative answer is "not resolvable".
            authoritative = dynamodb.get_item(
                TableName=table_name,
                Key={'applicationId': {'S': application_id}},
                ConsistentRead=True,
            ).get('Item')
            if not authoritative:
                return None
            return {k: unmarshal(v) for k, v in authoritative.items()}
        return None
    except Exception:
        # Fail closed
        return None


def _is_reservation(item: Dict[str, Any]) -> bool:
    raw = item.get('applicationId')
    value = raw.get('S') if isinstance(raw, dict) else raw
    return isinstance(value, str) and value.startswith(CLIENT_RESERVATION_PREFIX)


def list_partner_applications(
    table_name: Optional[str] = None,
    dynamodb_client: Optional[Any] = None,
) -> list:
    """List all real Partner Application records.

    Reservation items (PK = "CLIENT#<clientId>") are internal bookkeeping and
    are never exposed through listing.
    """
    try:
        if dynamodb_client is None:
            import boto3
            table_name = table_name or os.getenv('RIS_PARTNER_APPLICATIONS_TABLE')
            if not table_name:
                return []
            dynamodb = boto3.client('dynamodb', region_name=os.getenv('AWS_REGION', 'eu-central-1'))
        else:
            dynamodb = dynamodb_client

        records = []
        start_key = None
        while True:
            request: Dict[str, Any] = {'TableName': table_name}
            if start_key:
                request['ExclusiveStartKey'] = start_key
            response = dynamodb.scan(**request)
            for item in response.get('Items', []):
                if _is_reservation(item):
                    continue
                records.append({
                    k: (list(v.values())[0] if isinstance(v, dict) and v else v)
                    for k, v in item.items()
                })
            start_key = response.get('LastEvaluatedKey')
            if not start_key:
                break
        return records
    except Exception:
        return []


def deactivate_partner_application(
    application_id: str,
    table_name: Optional[str] = None,
    dynamodb_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Set a Partner Application to INACTIVE.

    The client-ID reservation item is intentionally left in place so a
    deactivated client ID can never be silently rebound to a different
    application.
    """
    if not application_id:
        raise PartnerRegistryError("application_id required")
    if application_id.startswith(CLIENT_RESERVATION_PREFIX):
        raise PartnerRegistryError(
            "refusing to modify a client-ID reservation item")
    try:
        if dynamodb_client is None:
            import boto3
            table_name = table_name or os.getenv('RIS_PARTNER_APPLICATIONS_TABLE')
            if not table_name:
                raise PartnerRegistryError("Table name not configured")
            dynamodb = boto3.client('dynamodb', region_name=os.getenv('AWS_REGION', 'eu-central-1'))
        else:
            dynamodb = dynamodb_client

        dynamodb.update_item(
            TableName=table_name,
            Key={'applicationId': {'S': application_id}},
            UpdateExpression='SET #s = :s',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={':s': {'S': 'INACTIVE'}},
            ConditionExpression='attribute_exists(applicationId)',
            ReturnValues='ALL_NEW',
        )
        return {'applicationId': application_id, 'status': 'INACTIVE'}
    except Exception as e:
        raise PartnerRegistryError(f"Failed to deactivate partner application: {e}")

