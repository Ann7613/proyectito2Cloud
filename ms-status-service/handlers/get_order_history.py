import json
import os
import boto3
from datetime import datetime
from decimal import Decimal
from utils import response
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["ORDERS_TABLE"])

# Acciones reales del flujo único
FLOW_ACTIONS = {"INIT", "COOKING", "PACKING", "ON_DELIVERY", "DELIVERED"}

def lambda_handler(event, context):
    print(f"Request: {json.dumps(event)}")

    try:
        # -------- tenant obligatorio ----------
        tenant_id = (event.get("headers") or {}).get("x-tenant-id")
        if not tenant_id:
            return response(400, {"error": "x-tenant-id header es requerido"})
            

        order_id = (event.get("pathParameters") or {}).get("order_id")
        if not order_id:
            return response(400,{"error": "order_id es requerido"})
            

        # -------- get pedido con PK compuesta ----------
        resp = table.get_item(Key={"tenant_id": tenant_id, "order_id": order_id})

        if "Item" not in resp:
            return response(404, {"error": "Pedido no encontrado"})
            

        pedido = resp["Item"]

        history_original = pedido.get("history", [])
        event_history = pedido.get("event_history", [])

        timeline = construir_timeline(history_original, event_history)
        estadisticas = calcular_estadisticas(timeline, pedido)

        resultado = {
            "order_id": order_id,
            "tenant_id": tenant_id,
            "customer_id": pedido.get("customer_id"),
            "status": pedido.get("status"),
            "items": clean_decimals(pedido.get("items", [])),
            "total": float(pedido.get("total", 0)),
            "created_at": pedido.get("created_at"),
            "updated_at": pedido.get("updated_at"),
            "timeline": timeline,
            "statistics": estadisticas
        }

        return response(200,{resultado})

    except Exception as e:
        print(f"Error: {str(e)}")
        return response(500,{"error": str(e)})
        


def construir_timeline(history_original, event_history):
    timeline = []

    # 1) Historial del flujo (lo escribe Orders + Fulfillment)
    for entry in history_original:
        timeline.append({
            "timestamp": entry.get("at") or entry.get("timestamp"),
            "action": entry.get("action"),
            "status": entry.get("status"),
            "by": entry.get("by") or entry.get("staff_id"),
            "staff_name": entry.get("staff_name"),
            "reason": entry.get("reason", ""),
            "source": "workflow"
        })

    # 2) Historial de eventos (lo escribe Status Listener)
    for entry in event_history:
        timeline.append({
            "timestamp": entry.get("timestamp"),
            "event_type": entry.get("event_type"),
            "event_label": entry.get("event_label"),
            "status": entry.get("status"),
            "details": {k: v for k, v in entry.items() if k not in ["timestamp", "event_type", "event_label"]},
            "source": "eventbridge"
        })

    timeline.sort(key=lambda x: x.get("timestamp", ""))
    return timeline


def calcular_estadisticas(timeline, pedido):
    if not timeline:
        return {}

    try:
        created_at = pedido.get("created_at")
        updated_at = pedido.get("updated_at")

        if created_at and updated_at:
            inicio = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            fin = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            tiempo_total = (fin - inicio).total_seconds() / 60
        else:
            tiempo_total = 0

        # pasos del flujo único
        pasos_completados = len([
            e for e in timeline
            if e.get("action") in FLOW_ACTIONS
        ])

        return {
            "tiempo_total_minutos": round(tiempo_total, 2),
            "eventos_totales": len(timeline),
            "pasos_completados": pasos_completados,
            "estado_actual": pedido.get("status")
        }

    except Exception as e:
        print(f"Error calculando estadísticas: {str(e)}")
        return response(500, {"error": "No se pudieron calcular estadísticas"})


def clean_decimals(obj):
    if isinstance(obj, list):
        return [clean_decimals(i) for i in obj]
    if isinstance(obj, dict):
        return {k: clean_decimals(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj
