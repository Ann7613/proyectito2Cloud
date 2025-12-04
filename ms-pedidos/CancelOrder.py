import os, json
import boto3
from datetime import datetime, timezone
from utils import response, publish_order_event

ddb = boto3.resource('dynamodb')
orders_table = ddb.Table(os.environ.get("ORDERS_TABLE", "Orders"))

# Estados finales del flujo ÚNICO (alineado a Fulfillment)
FINAL_STATUSES = ["ENTREGADO", "CANCELADO"]


def lambda_handler(event, context):
    # -------- 1) tenant_id obligatorio ----------
    tenant_id = (event.get("headers") or {}).get("x-tenant-id")
    if not tenant_id:
        return response(400, {"message": "x-tenant-id header es requerido"})

    path_params = event.get("pathParameters") or {}
    order_id = path_params.get("order_id")

    if not order_id:
        return response(400, {"message": "order_id is required in path"})

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return response(400, {"message": "Invalid JSON body"})

    cancelled_by = body.get("cancelled_by", "system")
    reason = body.get("reason", "")

    try:
        # -------- 2) Obtener pedido con PK compuesta ----------
        result = orders_table.get_item(
            Key={"tenant_id": tenant_id, "order_id": order_id}
        )
        item = result.get("Item")
        if not item:
            return response(404, {"message": "Order not found"})

        current_status = item.get("status", "PENDIENTE")

        if current_status in FINAL_STATUSES:
            return response(400, {
                "message": f"Cannot cancel an order with status {current_status}"
            })

        now = datetime.now(timezone.utc).isoformat()
        history_entry = {
            "action": "CANCELLED",
            "status": "CANCELADO",
            "timestamp": now,
            "by": cancelled_by,
            "reason": reason
        }

        # -------- 3) Update consistente ----------
        update_result = orders_table.update_item(
            Key={"tenant_id": tenant_id, "order_id": order_id},
            UpdateExpression=(
                "SET #status = :cancelled, "
                "updated_at = :updated_at, "
                "history = list_append(if_not_exists(history, :empty_list), :history_entry)"
            ),
            ExpressionAttributeNames={
                "#status": "status"
            },
            ExpressionAttributeValues={
                ":cancelled": "CANCELADO",
                ":updated_at": now,
                ":history_entry": [history_entry],
                ":empty_list": []
            },
            ReturnValues="ALL_NEW"
        )

        updated_order = update_result.get("Attributes", {})

        # -------- 4) Publicar evento alineado a arquitectura ----------
        try:
            publish_order_event(
                detail_type="PedidoCancelado",
                detail={
                    "order_id": order_id,
                    "tenant_id": tenant_id,
                    "customer_id": updated_order.get("customer_id"),
                    "status": updated_order.get("status"),
                    "reason": reason,
                    "cancelled_by": cancelled_by,
                    "timestamp": now
                }
            )
        except Exception as e:
            print(f"Error publishing PedidoCancelado event: {str(e)}")

        return response(200, {
            "success": True,
            "message": "Order cancelled successfully",
            "data": updated_order
        })

    except Exception as e:
        print(f"Error cancelling order: {str(e)}")
        return response(500, {"message": "Error cancelling order"})
