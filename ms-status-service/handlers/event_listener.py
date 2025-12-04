import json
import os
from datetime import datetime, timezone
import boto3
from utils import response
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["ORDERS_TABLE"])

# Mapeo opcional de tipo de evento -> etiqueta corta (solo para orden/timeline)
EVENT_LABELS = {
    "PedidoRecibido": "pedido_recibido",
    "PedidoInicializado": "pedido_inicializado",
    "CocinaIniciada": "cocina_iniciada",
    "EmpaqueIniciado": "empaque_iniciado",
    "RepartoIniciado": "reparto_iniciado",
    "PedidoEntregado": "pedido_entregado",
    "PedidoCancelado": "pedido_cancelado",
}

def handle_order_event(event, context):
    print(f"Evento recibido: {json.dumps(event)}")

    try:
        detail = event.get("detail", {})
        event_type = event.get("detail-type")
        order_id = detail.get("order_id")
        tenant_id = detail.get("tenant_id")

        if not event_type or not order_id or not tenant_id:
            return response(400, {"error": "Missing required fields in event",
                    "required": ["detail-type", "detail.order_id", "detail.tenant_id"]})

        now = datetime.now(timezone.utc).isoformat()

        # Base común de historial de eventos
        history_entry = {
            "event_type": event_type,
            "event_label": EVENT_LABELS.get(event_type, event_type),
            "timestamp": now,
            "event_time": detail.get("event_time", now),
            "order_id": order_id,
            "tenant_id": tenant_id,
            "status": detail.get("status"),          # casi todos los eventos ya lo envían
            "customer_id": detail.get("customer_id"),
            "staff_id": detail.get("staff_id"),
            "staff_name": detail.get("staff_name"),
            "reason": detail.get("reason"),
            "total": detail.get("total"),
        }

        # Limpieza de None para no ensuciar el event_history
        history_entry = {k: v for k, v in history_entry.items() if v is not None}

        table.update_item(
            Key={"tenant_id": tenant_id, "order_id": order_id},
            UpdateExpression=(
                "SET event_history = list_append(if_not_exists(event_history, :empty_list), :history_entry), "
                "last_event_update = :timestamp"
            ),
            ExpressionAttributeValues={
                ":history_entry": [history_entry],
                ":empty_list": [],
                ":timestamp": now
            },
            ReturnValues="UPDATED_NEW"
        )

        print(f"Pedido {tenant_id}/{order_id} actualizado con evento {event_type}")

        return response(200, {"message": "Event processed successfully",
                "order_id": order_id,
                "tenant_id": tenant_id,
                "event_type": event_type})

    except Exception as e:
        print(f"Error procesando evento: {str(e)}")
        
        return response(500, {"error": str(e)})
        
