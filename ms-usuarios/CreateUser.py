import json
import os
import boto3

dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    # Extract body
    body = json.loads(event.get('body', '{}'))
    tenant_id = event['requestContext']['authorizer']['claims'].get('custom:tenant_id')
    user_id = body.get('user_id')
    email = body.get('email')
    if not user_id or not email:
        return {'statusCode': 400, 'body': json.dumps({'message': 'user_id and email required'})}
    table_name = os.getenv('USERS_TABLE')
    table = dynamodb.Table(table_name)
    item = {'tenant_id': tenant_id, 'user_id': user_id, 'email': email}
    table.put_item(Item=item)
    return {'statusCode': 201, 'body': json.dumps(item)}
