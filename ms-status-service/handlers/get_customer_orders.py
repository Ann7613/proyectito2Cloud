import json
import os
import boto3
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal
from utils import response
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["ORDERS_TABLE"])

def lambda_handler(event, context):
    print(f"Request: {json.dumps(event)}")

    try:
        # -------- tenant obligatorio ----------
        tenant_id = (event.get("headers") or {}).get("x-tenant-id")
        if not tenant_id:
            return response(400, {"error": "x-tenant-id header es requerido"})

        customer_id = (event.get("pathParameters") or {}).get("customer_id")
        if not customer_id:
            return response(400, {"error": "customer_id is required"})
            

        # -------- Query por cliente usando CustomerIndex ----------
        resp = table.query(
            IndexName="CustomerIndex",
            KeyConditionExpression=Key("customer_id").eq(customer_id),
            FilterExpression=Attr("tenant_id").eq(tenant_id),
            ScanIndexForward=False  # más recientes primero
        )

        pedidos = resp.get("Items", [])

        pedidos_formateados = [
            {
                "order_id": p.get("order_id"),
                "tenant_id": p.get("tenant_id"),
                "status": p.get("status"),
                "items": clean_decimals(p.get("items", [])),
                "total": float(p.get("total", 0)),
                "created_at": p.get("created_at"),
                "updated_at": p.get("updated_at"),
                "progress": calcular_progreso(p.get("status", "PENDIENTE")),
                "status_label": obtener_label_estado(p.get("status"))
            }
            for p in pedidos
        ]

        return response(200, {
                "customer_id": customer_id,
                "tenant_id": tenant_id,
                "orders": pedidos_formateados,
                "total_orders": len(pedidos_formateados)
            })

    except Exception as e:
        print(f"Error: {str(e)}")
        return response(500, {"error": str(e)})
        


def calcular_progreso(status):
    # progreso alineado al flujo único
    estados = {
        "PENDIENTE": 10,
        "COCINANDO": 40,
        "EMPACANDO": 70,
        "EN_REPARTO": 90,
        "ENTREGADO": 100,
        "CANCELADO": 0
    }
    return estados.get(status, 0)


def obtener_label_estado(status):
    labels = {
        "PENDIENTE": "Pedido Recibido",
        "COCINANDO": "En Cocina",
        "EMPACANDO": "Empacando",
        "EN_REPARTO": "En Camino",
        "ENTREGADO": "Entregado",
        "CANCELADO": "Cancelado"
    }
    return labels.get(status, status)


def clean_decimals(obj):
    if isinstance(obj, list):
        return [clean_decimals(i) for i in obj]
    if isinstance(obj, dict):
        return {k: clean_decimals(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj
