import os
import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal
from utils import response

ddb = boto3.resource("dynamodb")
orders_table = ddb.Table(os.environ.get("ORDERS_TABLE", "Orders"))

# Estados del FLUJO ÚNICO (Fulfillment)
VALID_STATUSES = [
    "PENDIENTE",
    "COCINANDO",
    "EMPACANDO",
    "EN_REPARTO",
    "ENTREGADO",
    "CANCELADO"
]

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

        query_params = event.get("queryStringParameters") or {}
        status = query_params.get("status") if query_params else None

        if not status:
            return response(400, {"message": "status query parameter is required"})

        if status not in VALID_STATUSES:
            return response(400, {
                "message": f"Invalid status. Valid statuses: {', '.join(VALID_STATUSES)}"
            })

        # Query por tenant + status usando StatusIndex
        resp = orders_table.query(
            IndexName="StatusIndex",
            KeyConditionExpression=
                Key("tenant_id").eq(tenant_id) & Key("status").eq(status)
        )

        items = resp.get("Items", [])
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        items = clean_decimals(items)

        return response(200, {"success": True, "data": items})

    except Exception as e:
        print(f"Error listing orders by status: {str(e)}")
        return response(500, {
            "message": "Error listing orders by status",
            "error": str(e)
        })
