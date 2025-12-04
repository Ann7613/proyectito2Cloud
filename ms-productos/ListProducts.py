import json
import os
import boto3

dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    tenant_id = event['requestContext']['authorizer']['claims'].get('custom:tenant_id')
    table_name = os.getenv('PRODUCTS_TABLE')
    table = dynamodb.Table(table_name)
    # Scan for all products of the tenant
    response = table.scan(FilterExpression=boto3.dynamodb.conditions.Attr('tenant_id').eq(tenant_id))
    items = response.get('Items', [])
    return {'statusCode': 200, 'body': json.dumps(items)}
