# UpdateOrderStatusStep.py (corregido multi-tenant + history list_append)
import os
import json
import boto3
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb")
eventbridge = boto3.client("events")

table = dynamodb.Table(os.environ["ORDERS_TABLE"])
EVENT_BUS_NAME = os.environ["EVENT_BUS_NAME"]

ACTION_CONFIG = {
    "INIT": {"status": "PENDIENTE", "event_type": "PedidoInicializado"},
    "COOKING": {"status": "COCINANDO", "event_type": "CocinaIniciada"},
    "PACKING": {"status": "EMPACANDO", "event_type": "EmpaqueIniciado"},
    "ON_DELIVERY": {"status": "EN_REPARTO", "event_type": "RepartoIniciado"},
    "DELIVERED": {"status": "ENTREGADO", "event_type": "PedidoEntregado"},
}

def lambda_handler(event, context):
    """
    Invocada por Step Functions.

    event:
    {
      "action": "COOKING" | "PACKING" | "ON_DELIVERY" | "DELIVERED" | "INIT",
      "payload": {
        "order_id": "...",
        "tenant_id": "...",
        "customer_id": "...",   # opcional
        "staff_id": "...",      # opcional (si lo pasas desde endpoints)
        "staff_name": "..."     # opcional
      }
    }
    """
    action = event["action"]
    payload = event["payload"]

    order_id = payload["order_id"]
    tenant_id = payload.get("tenant_id")
    customer_id = payload.get("customer_id")

    if not tenant_id:
        raise ValueError("tenant_id es requerido para UpdateOrderStatusStep")

    if action not in ACTION_CONFIG:
        raise ValueError(f"Acción inválida: {action}")

    cfg = ACTION_CONFIG[action]
    new_status = cfg["status"]
    event_type = cfg["event_type"]

    now = datetime.now(timezone.utc).isoformat()

    history_entry = {
        "action": action,
        "status": new_status,
        "timestamp": now,
    }

    # Si viene staff desde endpoint, lo agregamos al historial
    if payload.get("staff_id"):
        history_entry["staff_id"] = payload["staff_id"]
    if payload.get("staff_name"):
        history_entry["staff_name"] = payload["staff_name"]

    # Actualiza status + timestamps + añade entrada al historial (LISTA)
    table.update_item(
        Key={
            "tenant_id": tenant_id,
            "order_id": order_id
        },
        UpdateExpression=(
            "SET #st = :st, "
            "updated_at = :ts, "
            "history = list_append(if_not_exists(history, :empty), :new)"
        ),
        ExpressionAttributeNames={
            "#st": "status",
        },
        ExpressionAttributeValues={
            ":st": new_status,
            ":ts": now,
            ":new": [history_entry],
            ":empty": [],
        },
    )

    # Publica evento a EventBridge para Status/Dashboard
    event_detail = {
        "order_id": order_id,
        "tenant_id": tenant_id,
        "status": new_status,
        "timestamp": now,
    }
    if customer_id:
        event_detail["customer_id"] = customer_id

    eventbridge.put_events(
        Entries=[
            {
                "Source": "fulfillment.service",
                "DetailType": event_type,
                "Detail": json.dumps(event_detail),
                "EventBusName": EVENT_BUS_NAME,
            }
        ]
    )

    return {
        "order_id": order_id,
        "tenant_id": tenant_id,
        "status": new_status,
        "ts": now,
    }
