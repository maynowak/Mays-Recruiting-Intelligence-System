"""Status Publisher Lambda – H5a"""

import json
import os
from datetime import datetime, timezone
from agents.health.contract import HealthState, HealthStatus
import boto3

s3_private = boto3.client('s3')
s3_public = boto3.client('s3')

PRIVATE_BUCKET = os.environ.get('HEALTH_PRIVATE_BUCKET', '')
PUBLIC_BUCKET = os.environ.get('HEALTH_PUBLIC_BUCKET', '')
ALLOWLIST = set(os.environ.get('HEALTH_ALLOWLIST', 'api,lambda,dynamodb').split(','))

FORBIDDEN_KEYS = {'source', 'observedAt', 'validUntil'}

def lambda_handler(event, context):
    try:
        # Read private state objects
        prefix = 'components/'
        response = s3_private.list_objects_v2(Bucket=PRIVATE_BUCKET, Prefix=prefix)
        objects = response.get('Contents', [])
        
        public_components = []
        now = datetime.now(timezone.utc)
        min_valid_until = None
        
        for obj in objects:
            key = obj['Key']
            parts = key.split('/')
            if len(parts) < 3:
                continue
            component_type = parts[1]
            if component_type not in ALLOWLIST:
                continue
            
            data = s3_private.get_object(Bucket=PRIVATE_BUCKET, Key=key)
            state_data = json.loads(data['Body'].read())
            
            try:
                observed_at = datetime.fromisoformat(state_data['observedAt'])
                valid_until = datetime.fromisoformat(state_data['validUntil'])
                status = HealthStatus(state_data['status'])
                is_valid = status == HealthStatus.ALIVE and now <= valid_until
            except Exception:
                continue
            
            if is_valid:
                public_components.append({
                    'componentType': component_type,
                    'status': 'OK'
                })
                if min_valid_until is None or valid_until < min_valid_until:
                    min_valid_until = valid_until
        
        # Build public status
        overall_ok = len(public_components) > 0 and all(c['status'] == 'OK' for c in public_components)
        
        if overall_ok and min_valid_until:
            public_valid_until = min_valid_until
        else:
            # Negative status: short freshness window, fail closed quickly
            public_valid_until = now
        
        public_status = {
            'overall': 'OK' if overall_ok else 'NOT_OK',
            'components': public_components,
            'lastUpdate': now.isoformat(),
            'validUntil': public_valid_until.isoformat()
        }
        
        s3_public.put_object(
            Bucket=PUBLIC_BUCKET,
            Key='public-status.json',
            Body=json.dumps(public_status),
            ContentType='application/json',
            CacheControl='no-cache, no-store, must-revalidate'
        )
        
        return {'statusCode': 200}
    except Exception as e:
        print(f"Publisher error: {e}")
        return {'statusCode': 500}
