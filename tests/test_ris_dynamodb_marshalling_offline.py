"""Offline regression: resource client double-marshals TransactWriteItems.

No AWS calls: botocore's endpoint transport is replaced before invoking it.
Run: python -m unittest -v test_ris_dynamodb_marshalling_offline.py
"""
import json
import unittest
from unittest.mock import patch
import boto3

TABLE = 'ris-dev2-dev-work-items'
FENCE = 'erasure-fence#' + 'a' * 64


class InterceptedTransport(Exception):
    pass


def inspect_wire_request(client):
    captured = {}
    def capture(operation, request):
        captured['body'] = json.loads(request['body'])
        raise InterceptedTransport
    with patch.object(client._endpoint, 'make_request', side_effect=capture):
        with unittest.TestCase().assertRaises(InterceptedTransport):
            client.transact_write_items(TransactItems=[
                {'ConditionCheck': {
                    'TableName': TABLE,
                    'Key': {'workId': {'S': FENCE}},
                    'ConditionExpression': 'attribute_not_exists(workId)',
                }},
                {'Put': {
                    'TableName': TABLE,
                    'Item': {'workId': {'S': 'work-synthetic'},
                             'payload': {'M': {'job': {'S': 'synthetic'}}}},
                    'ConditionExpression': 'attribute_not_exists(workId)',
                }},
            ])
    return captured['body']


class DynamoDBMarshallingRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session = boto3.session.Session(
            aws_access_key_id='OFFLINE_ONLY',
            aws_secret_access_key='OFFLINE_ONLY',
            region_name='eu-central-1',
        )

    def test_resource_client_double_marshals_explicit_dynamodb_json(self):
        client = self.session.resource('dynamodb').Table(TABLE).meta.client
        wire = inspect_wire_request(client)
        key = wire['TransactItems'][0]['ConditionCheck']['Key']['workId']
        self.assertEqual({'M': {'S': {'S': FENCE}}}, key)

    def test_low_level_client_preserves_explicit_dynamodb_json(self):
        client = self.session.client('dynamodb')
        wire = inspect_wire_request(client)
        self.assertEqual({'S': FENCE},
            wire['TransactItems'][0]['ConditionCheck']['Key']['workId'])
        self.assertEqual({'S': 'work-synthetic'},
            wire['TransactItems'][1]['Put']['Item']['workId'])
        self.assertEqual({'M': {'job': {'S': 'synthetic'}}},
            wire['TransactItems'][1]['Put']['Item']['payload'])


if __name__ == '__main__':
    unittest.main()
