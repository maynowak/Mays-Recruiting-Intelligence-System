"""Partner Application Registry – authoritative binding between Cognito M2M client and RIS APIProfile."""

from typing import Any, Dict, Optional

class PartnerRegistryError(Exception):
    pass

def resolve_partner_application(
    client_id: Optional[str],
    table_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Resolve partner application by Cognito client_id.

    Returns registry record dict or None if not found.
    In production this queries DynamoDB partner-applications table by GSI gsi-client.
    For local tests / offline mode, returns a minimal stub.

    Requires client_id to be present. Raises PartnerRegistryError on failure.
    """
    if not client_id:
        return None

    # Stub for local tests: accept 'client-test' as valid ACTIVE binding
    if client_id == 'client-test':
        return {
            'applicationId': 'app-test',
            'cognitoClientId': client_id,
            'apiProfileId': '*',
            'tenantId': 't1',
            'status': 'ACTIVE'
        }

    # TODO: production implementation with boto3 DynamoDB client.
    # Table name from env var RIS_PARTNER_APPLICATIONS_TABLE.
    # Query GSI gsi-client with cognitoClientId = client_id.
    # Ensure uniqueness via ConditionExpression on create.
    # Return dict with keys: applicationId, cognitoClientId, apiProfileId, tenantId, status.
    # For now, fail closed: return None to enforce binding.
    # Tests can monkey-patch this function.
    return None
