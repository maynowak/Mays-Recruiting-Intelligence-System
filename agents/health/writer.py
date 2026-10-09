"""Health State Writer Lambda"""

import json
import os
from datetime import datetime, timezone, timedelta
import boto3

s3 = boto3.client('s3')
bucket = os.environ.get('HEALTH_BUCKET', 'test-bucket')

def lambda_handler(event, context):
    try:
        # Validate event
        detail = event.get('detail', {})
        alarm_name = detail.get('alarmName')
        state_value = detail.get('state', {}).get('value')
        if not alarm_name or not state_value:
            return {'statusCode': 400}
        
        # Map alarm to component
        component_id = alarm_name
        component_type = 'cloudwatch_alarm'
        
        # Derive status
        status_map = {
            'OK': 'ALIVE',
            'ALARM': 'DOWN',
            'INSUFFICIENT_DATA': 'UNKNOWN'
        }
        status = status_map.get(state_value, 'UNKNOWN')
        
        now = datetime.now(timezone.utc)
        valid_until = now + timedelta(minutes=5)
        
        state = {
            'componentId': component_id,
            'componentType': component_type,
            'status': status,
            'observedAt': now.isoformat(),
            'validUntil': valid_until.isoformat(),
            'source': 'eventbridge'
        }
        
        key = f"components/{component_type}/{component_id}.json"
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(state),
            ContentType='application/json'
        )
        
        return {'statusCode': 200}
    except Exception as e:
        print(f"Error: {e}")
        return {'statusCode': 500}
