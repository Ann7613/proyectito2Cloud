import json
import os
import boto3

dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    body = json.loads(event.get('body', '{}'))
    tenant_id = event['requestContext']['authorizer']['claims'].get('custom:tenant_id')
    product_id = body.get('product_id')
    name = body.get('name')
    price = body.get('price')
    category = body.get('category')
    if not all([product_id, name, price]):
        return {'statusCode': 400, 'body': json.dumps({'message': 'product_id, name, price required'})}
    table_name = os.getenv('PRODUCTS_TABLE')
    table = dynamodb.Table(table_name)
    item = {'tenant_id': tenant_id, 'product_id': product_id, 'name': name, 'price': price, 'category': category}
    table.put_item(Item=item)
    return {'statusCode': 201, 'body': json.dumps(item)}
