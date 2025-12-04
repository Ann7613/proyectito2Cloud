import json
import os
import boto3

dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    tenant_id = event['requestContext']['authorizer']['claims'].get('custom:tenant_id')
    user_id = event['pathParameters'].get('user_id')
    if not user_id:
        return {'statusCode': 400, 'body': json.dumps({'message': 'user_id path param required'})}
    table_name = os.getenv('USERS_TABLE')
    table = dynamodb.Table(table_name)
    response = table.get_item(Key={'tenant_id': tenant_id, 'user_id': user_id})
    item = response.get('Item')
    if not item:
        return {'statusCode': 404, 'body': json.dumps({'message': 'User not found'})}
    return {'statusCode': 200, 'body': json.dumps(item)}
