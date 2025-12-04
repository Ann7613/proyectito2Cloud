import json
import os
import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime, timezone
from decimal import Decimal
from collections import Counter
from utils import response
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["ORDERS_TABLE"])

# Estados del flujo único
VALID_STATUSES = [
    "PENDIENTE",
    "COCINANDO",
    "EMPACANDO",
    "EN_REPARTO",
    "ENTREGADO",
    "CANCELADO"
]

def lambda_handler(event, context):
    print(f"Request: {json.dumps(event)}")

    try:
        # -------- tenant obligatorio ----------
        tenant_id = (event.get("headers") or {}).get("x-tenant-id")
        if not tenant_id:
            return response(400, {"error": "x-tenant-id header es requerido"})
            

        params = event.get("queryStringParameters", {}) or {}
        status_filter = params.get("status")

        pedidos = []

        # -------- cuando viene status, query directa ----------
        if status_filter:
            if status_filter not in VALID_STATUSES:
                return response(400, {"error": f"status inválido. Válidos: {', '.join(VALID_STATUSES)}"})

            resp = table.query(
                IndexName="StatusIndex",
                KeyConditionExpression=
                    Key("tenant_id").eq(tenant_id) & Key("status").eq(status_filter),
                ScanIndexForward=True
            )
            pedidos = resp.get("Items", [])

        # -------- sin status: queries por estado ----------
        else:
            for st in VALID_STATUSES:
                resp = table.query(
                    IndexName="StatusIndex",
                    KeyConditionExpression=
                        Key("tenant_id").eq(tenant_id) & Key("status").eq(st),
                    ScanIndexForward=True
                )
                pedidos.extend(resp.get("Items", []))

        pedidos_formateados = [
            {
                "order_id": p.get("order_id"),
                "tenant_id": p.get("tenant_id"),
                "customer_id": p.get("customer_id"),
                "status": p.get("status"),
                "items": clean_decimals(p.get("items", [])),
                "total": float(p.get("total", 0)),
                "created_at": p.get("created_at"),
                "updated_at": p.get("updated_at"),
                "tiempo_espera_minutos": calcular_tiempo_espera(p.get("created_at")),
                "pasos_completados": contar_pasos(p.get("history", []))
            }
            for p in pedidos
        ]

        pedidos_formateados.sort(key=lambda x: x["created_at"] or "")

        estadisticas = generar_estadisticas_dashboard(pedidos_formateados)
        return response(200, {"tenant_id": tenant_id,
                "orders": pedidos_formateados,
                "statistics": estadisticas,
                "total": len(pedidos_formateados),
                "filter_applied": status_filter})
        

    except Exception as e:
        print(f"Error: {str(e)}")
        return response(500, {"error": str(e)})
        


def calcular_tiempo_espera(created_at):
    if not created_at:
        return 0

    try:
        fecha_pedido = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        ahora = datetime.now(fecha_pedido.tzinfo)
        diferencia = (ahora - fecha_pedido).total_seconds() / 60
        return round(diferencia, 1)
    except:
        return 0


def contar_pasos(history):
    """
    En tu flujo nuevo, cada UpdateOrderStatusStep agrega entradas
    con action = INIT/COOKING/PACKING/ON_DELIVERY/DELIVERED
    Así contamos pasos reales (excepto INIT si no quieres contarlo).
    """
    acciones_flujo = {"INIT", "COOKING", "PACKING", "ON_DELIVERY", "DELIVERED"}
    return len([h for h in history if h.get("action") in acciones_flujo])


def generar_estadisticas_dashboard(pedidos):
    if not pedidos:
        return {
            "total_pedidos": 0,
            "por_estado": {},
            "tiempo_espera_promedio": 0,
            "pedido_mas_antiguo_minutos": 0,
            "total_ventas": 0,
            "estados_disponibles": VALID_STATUSES
        }

    estados = Counter(p["status"] for p in pedidos)

    tiempos_espera = [p["tiempo_espera_minutos"] for p in pedidos]
    tiempo_promedio = sum(tiempos_espera) / len(tiempos_espera) if tiempos_espera else 0
    pedido_mas_antiguo = max(tiempos_espera) if tiempos_espera else 0

    total_ventas = sum(p["total"] for p in pedidos)

    return {
        "total_pedidos": len(pedidos),
        "por_estado": dict(estados),
        "tiempo_espera_promedio": round(tiempo_promedio, 1),
        "pedido_mas_antiguo_minutos": round(pedido_mas_antiguo, 1),
        "total_ventas": round(total_ventas, 2),
        "estados_disponibles": VALID_STATUSES
    }


def clean_decimals(obj):
    if isinstance(obj, list):
        return [clean_decimals(i) for i in obj]
    if isinstance(obj, dict):
        return {k: clean_decimals(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj
