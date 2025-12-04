import os, json, uuid
import boto3
from datetime import datetime, timezone
from decimal import Decimal
from utils import response, publish_order_event

ddb = boto3.resource('dynamodb')
orders_table = ddb.Table(os.environ.get("ORDERS_TABLE", "Orders"))


def lambda_handler(event, context):
    # -------- 1) tenant_id obligatorio (multi-tenant) ----------
    tenant_id = (event.get("headers") or {}).get("x-tenant-id")
    if not tenant_id:
        return response(400, {"message": "x-tenant-id header es requerido"})

    # Parsear body con Decimal para los floats
    try:
        body = json.loads(event.get("body", "{}"), parse_float=Decimal)
    except json.JSONDecodeError:
        return response(400, {"message": "Invalid JSON body"})

    # Validaciones
    required_fields = ["customer_id", "items"]
    for field in required_fields:
        if field not in body:
            return response(400, {"message": f"{field} is required"})

    if not isinstance(body["items"], list) or len(body["items"]) == 0:
        return response(400, {"message": "items must be a non-empty list"})

    for item in body["items"]:
        if "product_id" not in item or "quantity" not in item:
            return response(400, {"message": "Each item must contain product_id and quantity"})

    # Calcular total usando Decimal
    total = Decimal("0")
    for item in body["items"]:
        unit_price = item.get("price", Decimal("0"))
        if not isinstance(unit_price, Decimal):
            unit_price = Decimal(str(unit_price))

        quantity = item.get("quantity", 0)
        if not isinstance(quantity, Decimal):
            quantity = Decimal(str(quantity))

        item["price"] = unit_price
        item["quantity"] = quantity

        total += unit_price * quantity

    # -------- 2) Armar pedido alineado al flujo único ----------
    order_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()

    order = {
        "tenant_id": tenant_id,                 # <- CLAVE multi-tenant
        "order_id": order_id,
        "customer_id": body["customer_id"],
        "status": "PENDIENTE",                  # <- MISMO estado inicial que Fulfillment
        "total": total,
        "items": body["items"],
        "created_at": now,
        "updated_at": now,
        "history": [
            {
                "action": "INIT",
                "status": "PENDIENTE",
                "timestamp": now,
                "by": body.get("customer_id", "unknown")
            }
        ]
    }

    # -------- 3) Guardar en DynamoDB (PK compuesta) ----------
    try:
        orders_table.put_item(Item=order)
    except Exception as e:
        print(f"Error saving order: {str(e)}")
        return response(500, {"message": "Error creating order"})

    # -------- 4) Publicar evento que Fulfillment escucha ----------
    try:
        publish_order_event(
            detail_type="PedidoRecibido",     # <- EXACTO al patrón del Fulfillment
            detail={
                "order_id": order_id,
                "tenant_id": tenant_id,
                "customer_id": body["customer_id"],
                "total": total,
                "items": body["items"],
                "created_at": now
            }
        )
    except Exception as e:
        print(f"Error publishing PedidoRecibido event: {str(e)}")

    return response(201, {
        "success": True,
        "message": "Pedido creado correctamente",
        "data": order
    })
