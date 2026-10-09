import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from agents.health.writer import lambda_handler


def test_writer_ok_alarm():
    event = {
        'detail': {
            'alarmName': 'test-alarm',
            'state': {'value': 'OK'}
        }
    }
    with patch('agents.health.writer.s3') as mock_s3, \
         patch('agents.health.writer.bucket', 'test-bucket'):
        result = lambda_handler(event, None)
        assert result['statusCode'] == 200
        mock_s3.put_object.assert_called_once()


def test_writer_missing_fields():
    event = {'detail': {}}
    with patch('agents.health.writer.s3'):
        result = lambda_handler(event, None)
        assert result['statusCode'] == 400


def test_writer_invalid_state():
    event = {
        'detail': {
            'alarmName': 'test-alarm',
            'state': {'value': 'UNKNOWN_STATE'}
        }
    }
    with patch('agents.health.writer.s3') as mock_s3, \
         patch('agents.health.writer.bucket', 'test-bucket'):
        result = lambda_handler(event, None)
        assert result['statusCode'] == 200
        # Should still write with UNKNOWN status
        mock_s3.put_object.assert_called_once()
