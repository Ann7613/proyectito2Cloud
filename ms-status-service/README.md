# china-wok-status-service

Endpoints:
GET /status/order/{order_id}
GET /status/order/{order_id}/history
GET /status/dashboard
GET /status/customer/{customer_id}

Functions:
eventListener
getOrderStatus
getOrderHistory
getDashboardOrders
getCustomerOrders


## Endpoints Disponibles

| Método | Endpoint                                      | Descripción |
|--------|-----------------------------------------------|-------------|
| GET    | `/status/order/{order_id}`                    | Estado actual del pedido |
| GET    | `/status/order/{order_id}/history`            | Historial completo |
| GET    | `/status/dashboard`                           | Vista general del restaurante |
| GET    | `/status/customer/{customer_id}`              | Pedidos por cliente |

---

## Funciones Lambda

| Función             | Propósito |
|---------------------|-----------|
| `eventListener`     | Procesa eventos de EventBridge y actualiza DynamoDB |
| `getOrderStatus`    | Devuelve estado actual de un pedido |
| `getOrderHistory`   | Devuelve historial completo |
| `getDashboardOrders`| Devuelve pedidos activos del día |
| `getCustomerOrders` | Lista pedidos de un cliente |
