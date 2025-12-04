import json
import os
import boto3

dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    tenant_id = event['requestContext']['authorizer']['claims'].get('custom:tenant_id')
    product_id = event['pathParameters'].get('product_id')
    if not product_id:
        return {'statusCode': 400, 'body': json.dumps({'message': 'product_id path param required'})}
    table_name = os.getenv('PRODUCTS_TABLE')
    table = dynamodb.Table(table_name)
    response = table.get_item(Key={'tenant_id': tenant_id, 'product_id': product_id})
    item = response.get('Item')
    if not item:
        return {'statusCode': 404, 'body': json.dumps({'message': 'Product not found'})}
    return {'statusCode': 200, 'body': json.dumps(item)}
