"""Partner Application Registry – authoritative binding between Cognito M2M client and RIS APIProfile."""

import os
from typing import Any, Callable, Dict, Optional

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
            'tenantId': {'S': tenant_id},
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
    """Resolve the unique ACTIVE partner application for a Cognito client ID.

    Deterministic rules (never query order):

    1. If a ``CLIENT#<clientId>`` reservation exists, it is authoritative.
       Only its ``reservedForApplicationId`` may be returned, and only when
       that base record is ACTIVE, has the same ``cognitoClientId`` and (when
       the reservation stores one) the same ``tenantId``.
    2. Without a reservation, exactly one ACTIVE base record may exist for the
       client. Zero or multiple ACTIVE records are not resolvable.
    3. Historical INACTIVE records never block a valid ACTIVE binding.

    GSI ``gsi-client`` is only a locator and is eventually consistent, so every
    candidate is re-read from the base table with ``ConsistentRead=True``. Any
    error fails closed with ``None``.
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

        def unmarshal(value):
            if 'S' in value:
                return value['S']
            if 'N' in value:
                return int(value['N'])
            return value

        def get_attr(item, name):
            raw = item.get(name)
            if not isinstance(raw, dict) or not raw:
                return None
            return unmarshal(raw)

        def get_base(application_id):
            return dynamodb.get_item(
                TableName=table_name,
                Key={'applicationId': {'S': application_id}},
                ConsistentRead=True,
            ).get('Item')

        reservation = get_base(CLIENT_RESERVATION_PREFIX + client_id)
        reserved_for = None
        if reservation is not None:
            if get_attr(reservation, 'cognitoClientId') != client_id:
                return None
            reserved_for = get_attr(reservation, 'reservedForApplicationId')
            if not reserved_for:
                return None
            owner = get_base(reserved_for)
            if not owner:
                return None
            if get_attr(owner, 'cognitoClientId') != client_id:
                return None
            if get_attr(owner, 'status') != 'ACTIVE':
                return None
            reservation_tenant = get_attr(reservation, 'tenantId')
            if reservation_tenant and reservation_tenant != get_attr(
                    owner, 'tenantId'):
                return None

        # Collect every locator for this client. The reservation item is not a
        # partner record and is skipped; the base reads below are authoritative.
        start_key = None
        candidate_ids = set()
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
            for item in response.get('Items', []):
                application_id = get_attr(item, 'applicationId')
                if not application_id:
                    continue
                if application_id.startswith(CLIENT_RESERVATION_PREFIX):
                    continue
                candidate_ids.add(application_id)
            start_key = response.get('LastEvaluatedKey')
            if not start_key:
                break

        if reserved_for:
            # Include the reservation owner even while the GSI is catching up.
            candidate_ids.add(reserved_for)

        active = {}
        for application_id in candidate_ids:
            item = get_base(application_id)
            if not item:
                continue
            if get_attr(item, 'cognitoClientId') != client_id:
                continue
            if get_attr(item, 'status') != 'ACTIVE':
                continue
            active[application_id] = item

        if len(active) != 1:
            return None
        resolved_id, resolved = next(iter(active.items()))
        if reserved_for and resolved_id != reserved_for:
            return None
        return {k: unmarshal(v) for k, v in resolved.items()}
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
    expected_tenant: Optional[str] = None,
    release_reservation: bool = False,
    dependency_check: Optional[Callable[[Optional[str]], bool]] = None,
) -> Dict[str, Any]:
    """Set a Partner Application to INACTIVE.

    The historical partner record is never deleted: it remains as an INACTIVE
    audit record. By default the client-ID reservation also remains, so a
    deactivated client ID cannot be silently rebound.

    ``release_reservation=True`` explicitly releases the client-ID reservation
    so a new partner can bind the same client later. It requires a
    ``dependency_check`` callable that receives the partner's ``apiProfileId``
    and returns True when active credentials/entitlements (or another usage
    dependency) still exist. Release is then refused. The reservation delete is
    conditional on this application being its owner, so a concurrent rebind or
    a foreign reservation is never released. The operation is idempotent: an
    already-absent reservation is reported as released.
    """
    if not application_id:
        raise PartnerRegistryError("application_id required")
    if application_id.startswith(CLIENT_RESERVATION_PREFIX):
        raise PartnerRegistryError(
            "refusing to modify a client-ID reservation item")
    if release_reservation and not callable(dependency_check):
        raise PartnerRegistryError(
            "dependency_check is required to release a reservation")
    try:
        if dynamodb_client is None:
            import boto3
            table_name = table_name or os.getenv('RIS_PARTNER_APPLICATIONS_TABLE')
            if not table_name:
                raise PartnerRegistryError("Table name not configured")
            dynamodb = boto3.client('dynamodb', region_name=os.getenv('AWS_REGION', 'eu-central-1'))
        else:
            dynamodb = dynamodb_client

        partner = dynamodb.get_item(
            TableName=table_name,
            Key={'applicationId': {'S': application_id}},
            ConsistentRead=True,
        ).get('Item')
        if not partner:
            raise PartnerRegistryError("partner application not found")

        partner_tenant = partner.get('tenantId', {}).get('S')
        if expected_tenant is not None:
            if not expected_tenant:
                raise PartnerRegistryError("expected_tenant must not be empty")
            if partner_tenant != expected_tenant:
                raise PartnerRegistryError("partner tenant scope mismatch")

        client_id = partner.get('cognitoClientId', {}).get('S')
        api_profile_id = partner.get('apiProfileId', {}).get('S')

        if release_reservation:
            if dependency_check(api_profile_id):
                raise PartnerRegistryError(
                    "active dependencies prevent reservation release")
            if not client_id:
                raise PartnerRegistryError(
                    "partner has no cognitoClientId to release")
            reservation_key = CLIENT_RESERVATION_PREFIX + client_id
            reservation = dynamodb.get_item(
                TableName=table_name,
                Key={'applicationId': {'S': reservation_key}},
                ConsistentRead=True,
            ).get('Item')
            if reservation:
                owner = reservation.get(
                    'reservedForApplicationId', {}).get('S')
                if owner != application_id:
                    raise PartnerRegistryError(
                        "client reservation belongs to another application")

        values = {':s': {'S': 'INACTIVE'}}
        condition = 'attribute_exists(applicationId)'
        if expected_tenant is not None:
            values[':t'] = {'S': expected_tenant}
            condition += ' AND tenantId = :t'
        dynamodb.update_item(
            TableName=table_name,
            Key={'applicationId': {'S': application_id}},
            UpdateExpression='SET #s = :s',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues=values,
            ConditionExpression=condition,
            ReturnValues='ALL_NEW',
        )

        result = {'applicationId': application_id, 'status': 'INACTIVE'}
        if release_reservation:
            reservation_key = CLIENT_RESERVATION_PREFIX + client_id
            released = False
            try:
                dynamodb.delete_item(
                    TableName=table_name,
                    Key={'applicationId': {'S': reservation_key}},
                    ConditionExpression=(
                        'reservedForApplicationId = :app AND '
                        'cognitoClientId = :client AND #s = :reserved'
                    ),
                    ExpressionAttributeNames={'#s': 'status'},
                    ExpressionAttributeValues={
                        ':app': {'S': application_id},
                        ':client': {'S': client_id},
                        ':reserved': {'S': 'RESERVED'},
                    },
                )
                released = True
            except Exception:
                current = dynamodb.get_item(
                    TableName=table_name,
                    Key={'applicationId': {'S': reservation_key}},
                    ConsistentRead=True,
                ).get('Item')
                if current is None:
                    released = True  # idempotent: already released
                else:
                    owner = current.get(
                        'reservedForApplicationId', {}).get('S')
                    if owner and owner != application_id:
                        raise PartnerRegistryError(
                            "client reservation belongs to another application")
                    raise PartnerRegistryError(
                        "failed to release client reservation")
            result['reservationReleased'] = released
        return result
    except PartnerRegistryError:
        raise
    except Exception as e:
        raise PartnerRegistryError(f"Failed to deactivate partner application: {e}")

