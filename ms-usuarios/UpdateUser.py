import json
import os
import boto3

dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    tenant_id = event['requestContext']['authorizer']['claims'].get('custom:tenant_id')
    user_id = event['pathParameters'].get('user_id')
    if not user_id:
        return {'statusCode': 400, 'body': json.dumps({'message': 'user_id path param required'})}
    body = json.loads(event.get('body', '{}'))
    # Allow updating email only for simplicity
    email = body.get('email')
    if not email:
        return {'statusCode': 400, 'body': json.dumps({'message': 'email required'})}
    table_name = os.getenv('USERS_TABLE')
    table = dynamodb.Table(table_name)
    response = table.update_item(
        Key={'tenant_id': tenant_id, 'user_id': user_id},
        UpdateExpression='SET email = :e',
        ExpressionAttributeValues={':e': email},
        ReturnValues='ALL_NEW'
    )
    return {'statusCode': 200, 'body': json.dumps(response.get('Attributes'))}
