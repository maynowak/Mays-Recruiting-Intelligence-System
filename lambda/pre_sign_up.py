import json

def handler(event, context):
    user_attrs = event.get('request', {}).get('userAttributes', {})
    email = user_attrs.get('email')

    if not email:
        raise Exception('email attribute is required for sign-up')
    
    if '@' not in email or '.' not in email.split('@')[-1]:
        raise Exception('invalid email address')
    
    event['response'] = {'autoConfirmUser': False, 'autoVerifyEmail': False}
    return event
