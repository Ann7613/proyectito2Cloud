import os
import json
import boto3
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal
from utils import response

ddb = boto3.resource("dynamodb")
orders_table = ddb.Table(os.environ.get("ORDERS_TABLE", "Orders"))

def clean_decimals(obj):
    if isinstance(obj, list):
        return [clean_decimals(i) for i in obj]
    if isinstance(obj, dict):
        return {k: clean_decimals(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    return obj

def lambda_handler(event, context):
    try:
        # tenant obligatorio
        tenant_id = (event.get("headers") or {}).get("x-tenant-id")
        if not tenant_id:
            return response(400, {"message": "x-tenant-id header es requerido"})

        path_params = event.get("pathParameters") or {}
        query_params = event.get("queryStringParameters") or {}

        customer_id = (
            path_params.get("customer_id")
            or (query_params.get("customer_id") if query_params else None)
        )

        if not customer_id:
            return response(400, {"message": "customer_id is required"})

        # Query por cliente usando GSI CustomerIndex
        # + filtro tenant para no mezclar sedes
        resp = orders_table.query(
            IndexName="CustomerIndex",
            KeyConditionExpression=Key("customer_id").eq(customer_id),
            FilterExpression=Attr("tenant_id").eq(tenant_id)
        )

        items = resp.get("Items", [])
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        items = clean_decimals(items)

        return response(200, {"success": True, "data": items})

    except Exception as e:
        print(f"Error listing orders by user: {str(e)}")
        return response(500, {
            "message": "Error listing orders by user",
            "error": str(e)
        })
