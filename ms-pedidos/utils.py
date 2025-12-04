import os
import json
import boto3
from datetime import datetime, timezone
from decimal import Decimal

# ---------------------------
# Utils: limpieza de Decimals
# ---------------------------
def clean_decimals(obj):
    if isinstance(obj, list):
        return [clean_decimals(i) for i in obj]
    if isinstance(obj, dict):
        return {k: clean_decimals(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        # si es número entero, devuelve int; si no, float
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


# ---------------------------
# Utils: respuestas API Gateway
# ---------------------------
def response(status, body):
    body = clean_decimals(body)
    return {
        "statusCode": status,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": (
                "Content-Type,X-Amz-Date,Authorization,X-Api-Key,"
                "X-Amz-Security-Token,x-tenant-id"
            ),
            "Access-Control-Allow-Methods": "OPTIONS,GET,POST,PUT,DELETE,PATCH"
        },
        "body": json.dumps(body, default=str)
    }


# ---------------------------
# Utils: publicar eventos EB
# ---------------------------
events_client = boto3.client("events")

def publish_order_event(detail_type: str, detail: dict, source: str = "orders.service"):
    """
    Envía un evento a EventBridge.
    Usa el bus definido en EVENT_BUS_NAME (si no existe, usa default).
    """
    detail = dict(detail)  # copia defensiva
    detail["event_time"] = datetime.now(timezone.utc).isoformat()

    # Limpia Decimals para que json.dumps no falle
    detail = clean_decimals(detail)

    bus_name = os.environ.get("EVENT_BUS_NAME", "default")

    try:
        resp = events_client.put_events(
            Entries=[
                {
                    "Source": source,
                    "DetailType": detail_type,
                    "Detail": json.dumps(detail, default=str),
                    "EventBusName": bus_name,
                }
            ]
        )
        return resp
    except Exception as e:
        print(f"Error putting event {detail_type} to bus {bus_name}: {str(e)}")
        raise
