# api/MarkPacked.py (corregido multi-tenant)
import os
import json
import boto3
from datetime import datetime, timezone
from utils import response
dynamodb = boto3.resource("dynamodb")
stepfunctions = boto3.client("stepfunctions")
table = dynamodb.Table(os.environ["ORDERS_TABLE"])


def lambda_handler(event, context):
    order_id = event["pathParameters"]["order_id"]
    body = json.loads(event.get("body") or "{}")

    tenant_id = (event.get("headers") or {}).get("x-tenant-id")
    if not tenant_id:
        return response(400, {"error": "x-tenant-id header requerido"})

    staff_id = body.get("staff_id")
    staff_name = body.get("staff_name")
    if not staff_id or not staff_name:
        return response(400, {"error": "staff_id y staff_name son requeridos"})

        

    res = table.get_item(Key={"tenant_id": tenant_id, "order_id": order_id})
    item = res.get("Item")
    if not item:
        return response(404, {"error": "Order not found"})

    if item.get("pending_step") != "PACK":
        return response(409, {"error": "Order not waiting for PACK"})

    task_token = item.get("pending_task_token")
    if not task_token:
        return response(409, {"error": "No pending task token"})

    now = datetime.now(timezone.utc).isoformat()

    output = {
        "order_id": order_id,
        "tenant_id": tenant_id,
        "customer_id": item.get("customer_id"),
        "total": item.get("total"),
        "staff_id": staff_id,
        "staff_name": staff_name,
        "step": "PACK",
        "timestamp": now,
    }

    stepfunctions.send_task_success(
        taskToken=task_token,
        output=json.dumps(output, default=str)
    )

    table.update_item(
        Key={"tenant_id": tenant_id, "order_id": order_id},
        UpdateExpression="REMOVE pending_task_token, pending_step, pending_updated_at",
    )

    return response(200, {"message": "Order marked as packed, workflow resumed", "order_id": order_id})
