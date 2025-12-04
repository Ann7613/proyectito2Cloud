import json
import os
import boto3
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
            return response(400,{"error": "x-tenant-id header es requerido"})
            

        order_id = (event.get("pathParameters") or {}).get("order_id")
        if not order_id:
            return response(400, {"error": "order_id es requerido"})
            

        # -------- get pedido con PK compuesta ----------
        resp = table.get_item(Key={"tenant_id": tenant_id, "order_id": order_id})

        if "Item" not in resp:
            return response(404, {"error": "Pedido no encontrado"})
            

        pedido = resp["Item"]
        status = pedido.get("status", "PENDIENTE")

        resultado = {
            "order_id": order_id,
            "tenant_id": tenant_id,
            "status": status,
            "customer_id": pedido.get("customer_id"),
            "items": clean_decimals(pedido.get("items", [])),
            "total": float(pedido.get("total", 0)),
            "created_at": pedido.get("created_at"),
            "updated_at": pedido.get("updated_at"),
            "progress": calcular_progreso(status)
        }

        return response(200,{resultado})
        

    except Exception as e:
        print(f"Error: {str(e)}")
        return response(500, {"error": "Error interno del servidor",
                "details": str(e)})
        


def calcular_progreso(status):
    estados = {
        "PENDIENTE": 10,
        "COCINANDO": 40,
        "EMPACANDO": 70,
        "EN_REPARTO": 90,
        "ENTREGADO": 100,
        "CANCELADO": 0
    }
    return estados.get(status, 0)


def clean_decimals(obj):
    if isinstance(obj, list):
        return [clean_decimals(i) for i in obj]
    if isinstance(obj, dict):
        return {k: clean_decimals(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj
