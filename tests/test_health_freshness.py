import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, '/home/dci-student/projects/Mays-Recruiting-Intelligent-System')
from agents.health.publisher import lambda_handler

def test_fresh_alive():
    now = datetime.now(timezone.utc)
    future = now + timedelta(minutes=5)
    mock_list = {'Contents': [{'Key': 'components/api/c1.json'}]}
    mock_get = MagicMock()
    mock_get.read.return_value = json.dumps({
        'componentId': 'c1',
        'componentType': 'api',
        'status': 'ALIVE',
        'observedAt': now.isoformat(),
        'validUntil': future.isoformat(),
        'source': 'test'
    }).encode()
    with patch('agents.health.publisher.s3_private') as mock_priv, \
         patch('agents.health.publisher.s3_public') as mock_pub, \
         patch('agents.health.publisher.PRIVATE_BUCKET','priv'), \
         patch('agents.health.publisher.PUBLIC_BUCKET','pub'):
        mock_priv.list_objects_v2.return_value = mock_list
        mock_priv.get_object.return_value = {'Body': mock_get}
        res = lambda_handler({}, None)
        assert res['statusCode']==200
        body = json.loads(mock_pub.put_object.call_args[1]['Body'])
        assert body['overall']=='OK'
        assert datetime.fromisoformat(body['validUntil']) <= future

def test_expired_alive():
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=1)
    mock_list = {'Contents': [{'Key': 'components/api/c1.json'}]}
    mock_get = MagicMock()
    mock_get.read.return_value = json.dumps({
        'componentId': 'c1',
        'componentType': 'api',
        'status': 'ALIVE',
        'observedAt': past.isoformat(),
        'validUntil': past.isoformat(),
        'source': 'test'
    }).encode()
    with patch('agents.health.publisher.s3_private') as mock_priv, \
         patch('agents.health.publisher.s3_public') as mock_pub, \
         patch('agents.health.publisher.PRIVATE_BUCKET','priv'), \
         patch('agents.health.publisher.PUBLIC_BUCKET','pub'):
        mock_priv.list_objects_v2.return_value = mock_list
        mock_priv.get_object.return_value = {'Body': mock_get}
        res = lambda_handler({}, None)
        assert res['statusCode']==200
        body = json.loads(mock_pub.put_object.call_args[1]['Body'])
        assert body['overall']=='NOT_OK'

print('tests passed')
