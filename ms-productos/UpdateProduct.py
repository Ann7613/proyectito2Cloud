import json
import os
import boto3

dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    tenant_id = event['requestContext']['authorizer']['claims'].get('custom:tenant_id')
    product_id = event['pathParameters'].get('product_id')
    if not product_id:
        return {'statusCode': 400, 'body': json.dumps({'message': 'product_id path param required'})}
    body = json.loads(event.get('body', '{}'))
    # Allow updating name, price, category
    update_expr = []
    expr_vals = {}
    if 'name' in body:
        update_expr.append('name = :n')
        expr_vals[':n'] = body['name']
    if 'price' in body:
        update_expr.append('price = :p')
        expr_vals[':p'] = body['price']
    if 'category' in body:
        update_expr.append('category = :c')
        expr_vals[':c'] = body['category']
    if not update_expr:
        return {'statusCode': 400, 'body': json.dumps({'message': 'No updatable fields provided'})}
    update_expression = 'SET ' + ', '.join(update_expr)
    table_name = os.getenv('PRODUCTS_TABLE')
    table = dynamodb.Table(table_name)
    response = table.update_item(
        Key={'tenant_id': tenant_id, 'product_id': product_id},
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expr_vals,
        ReturnValues='ALL_NEW'
    )
    return {'statusCode': 200, 'body': json.dumps(response.get('Attributes'))}
