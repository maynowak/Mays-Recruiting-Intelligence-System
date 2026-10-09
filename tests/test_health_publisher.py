import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import boto3
from agents.health.publisher import lambda_handler


def test_publisher_ok():
    now = datetime.now(timezone.utc)
    # Mock S3 responses
    mock_list = {'Contents': [{'Key': 'components/api/comp1.json'}]}
    mock_get = MagicMock()
    mock_get.read.return_value = json.dumps({
        'componentId': 'comp1',
        'componentType': 'api',
        'status': 'ALIVE',
        'observedAt': now.isoformat(),
        'validUntil': (now + timedelta(minutes=5)).isoformat(),
        'source': 'test'
    }).encode()
    
    with patch('agents.health.publisher.s3_private') as mock_priv, \
         patch('agents.health.publisher.s3_public') as mock_pub, \
         patch('agents.health.publisher.PRIVATE_BUCKET', 'priv'), \
         patch('agents.health.publisher.PUBLIC_BUCKET', 'pub'):
        mock_priv.list_objects_v2.return_value = mock_list
        mock_priv.get_object.return_value = {'Body': mock_get}
        
        result = lambda_handler({}, None)
        assert result['statusCode'] == 200
        mock_pub.put_object.assert_called_once()
        
        # Verify public status sanitized
        call_args = mock_pub.put_object.call_args[1]
        body = json.loads(call_args['Body'])
        assert 'source' not in str(body)
        assert body['overall'] == 'OK'
