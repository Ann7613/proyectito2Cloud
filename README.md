# China Wok – Arquitectura Serverless (Pedidos, Cumplimiento y Status)

Proyecto de ejemplo para demostrar una **arquitectura serverless multi-tenant y basada en eventos** para un restaurante tipo China Wok.

Incluye 3 microservicios en AWS:

1. **ms-pedidos**  
   Crea y lista pedidos de clientes, expone APIs públicas para la app del cliente.

2. **ms-cumplimiento**  
   Orquesta el **flujo de trabajo del restaurante** (cocinero → empaque → delivery) usando **AWS Step Functions**.

3. **ms-status**  
   Expone APIs de **consulta de estado, historial y dashboard** para el restaurante y el cliente.

Tecnologías principales:

- AWS Lambda
- API Gateway
- DynamoDB
- EventBridge
- Step Functions
- S3
- Serverless Framework

---

## 1. Arquitectura general

### Flujo simplificado

1. El **cliente** crea un pedido desde la app → `ms-pedidos` (`POST /orders`).
2. `ms-pedidos` guarda el pedido en **DynamoDB** y publica un evento `PedidoRecibido` en **EventBridge**.
3. `ms-cumplimiento` escucha el evento y arranca una **State Machine** de Step Functions que:
   - Marca el pedido como `PENDIENTE`.
   - Espera a que el staff:
     - Asigne cocinero (`assign-cook`).
     - Marque empacado (`mark-packed`).
     - Asigne repartidor (`assign-delivery`).
     - Marque entregado (`mark-delivered`).
   - Actualiza el estado en la tabla de pedidos y emite eventos para el dashboard.
4. `ms-status` consulta la misma tabla para:
   - Saber estado actual de un pedido.
   - Ver historial (timeline).
   - Mostrar dashboard por estado.
   - Listar pedidos por cliente.

### Multi-tenancy

Se maneja multi-tenancy con:

- **Header HTTP:** `x-tenant-id`
- **DynamoDB PK:** `tenant_id`
- **SK:** `order_id`

Todos los endpoints que interactúan con pedidos deben recibir `x-tenant-id`.

---

## 2. Requisitos previos

- Node.js (>= 16)
- npm
- Serverless Framework instalado globalmente:

  ```bash
  npm install -g serverless
  ```
---

## 3. Estructura del repositorio

Ejemplo de estructura:

```bash
ChinaWok-Clone-Backend/
├─ ms-pedidos/          # Microservicio de pedidos (Order Service)
├─ ms-cumplimiento/     # Microservicio de cumplimiento (Fulfillment / Workflow)
└─ ms-status/           # Microservicio de status y dashboard
```

Cada microservicio tiene su propio `serverless.yml`, código de Lambdas y su `.env`.

---

## 4. Variables de entorno (.env)

### 4.1. ms-pedidos (`ms-pedidos/.env`)

```env
ORG_NAME=orgname
ORDERS_SERVICE_NAME=china-wok-orders-service

AWS_ACCOUNT_ID=123456789103
ROLE_NAME=LabRole
```

Este stack **crea**:

- Tabla DynamoDB de pedidos (multi-tenant).
- EventBridge Event Bus.
- S3 Bucket.
- Exporta estos recursos para que otros stacks los importen.

---

### 4.2. ms-cumplimiento (`ms-cumplimiento/.env`)

```env
ORG_NAME=orgname
FULFILLMENT_SERVICE_NAME=china-wok-fulfillment-service
ORDERS_SERVICE_NAME=china-wok-orders-service

AWS_ACCOUNT_ID=123456789103
ROLE_NAME=LabRole
```

Este servicio **importa** los recursos del stack `ms-pedidos` (tabla, event bus, bucket).

---

### 4.3. ms-status (`ms-status/.env`)

```env
ORG_NAME=orgname
SERVICE_NAME=china-wok-status-service
ORDERS_SERVICE_NAME=china-wok-orders-service

AWS_ACCOUNT_ID=123456789103
ROLE_NAME=LabRole
```

Este servicio también **importa** la tabla de pedidos del stack `ms-pedidos`.

---

## 5. Despliegue (Deploy)

> **Importante:** `ms-cumplimiento` y `ms-status` importan recursos de `ms-pedidos`.

### 5.1. Desplegar ms-pedidos

```bash
cd ms-pedidos
npm install
sls deploy
```

Esto creará:

- DynamoDB `OrdersTable` (multi-tenant).
- EventBridge Bus.
- S3 Bucket.
- Exports de CloudFormation:
  - `${ORDERS_SERVICE_NAME}-dev-OrdersTableName`
  - `${ORDERS_SERVICE_NAME}-dev-EventBusName`
  - `${ORDERS_SERVICE_NAME}-dev-DeliveryBucketName`

### 5.2. Desplegar ms-cumplimiento

```bash
cd ../ms-cumplimiento
npm install
sls deploy
```

Este servicio:

- **Importa** `ORDERS_TABLE`, `EVENT_BUS_NAME` y `DELIVERY_BUCKET` del stack de pedidos.
- Crea la State Machine `OrderFulfillmentStateMachine` que orquesta el workflow.
- Expone los endpoints internos para el staff (assign-cook, mark-packed, etc.).

### 5.3. Desplegar ms-status

```bash
cd ../ms-status
npm install
sls deploy
```

Este servicio:

- **Importa** la misma tabla de pedidos.
- Crea Lambdas para:
  - Estado actual del pedido.
  - Historial del pedido.
  - Dashboard.
  - Pedidos por cliente.

---

## 6. Endpoints por microservicio

> Los Invoke URL exactos se obtienen con `sls info` o en la consola de API Gateway.  
> Aquí se muestran los que se desplegaron en el entorno actual.

### 6.1. ms-pedidos (Order Service)

**Base URL:**

```text
https://1qvyjv74r3.execute-api.us-east-1.amazonaws.com/dev
```

Todos los endpoints aceptan el header:

```http
x-tenant-id: CHINAWOK_LIMA_CENTRO
```

#### 6.1.1. Crear pedido

- **Método:** `POST`
- **URL:** `/orders`

**Headers:**
```http
Content-Type: application/json
x-tenant-id: CHINAWOK_LIMA_CENTRO
```

**Body ejemplo:**

```json
{
  "customer_id": "cliente_001",
  "items": [
    {
      "product_id": "POLLO_ARROZ",
      "quantity": 2,
      "price": 15.5
    },
    {
      "product_id": "ROLLO_PRIMAVERA",
      "quantity": 3,
      "price": 4.0
    }
  ]
}
```

#### 6.1.2. Listar pedidos por cliente

- **Método:** `GET`
- **URL:** `/orders/customer/{customer_id}`

Ejemplo:

```http
GET /orders/customer/cliente_001
Host: 1qvyjv74r3.execute-api.us-east-1.amazonaws.com
x-tenant-id: CHINAWOK_LIMA_CENTRO
```

#### 6.1.3. Listar pedidos por estado

- **Método:** `GET`
- **URL:** `/orders?status={status}`

Ejemplo:

```http
GET /orders?status=PENDIENTE
Host: 1qvyjv74r3.execute-api.us-east-1.amazonaws.com
x-tenant-id: CHINAWOK_LIMA_CENTRO
```

#### 6.1.4. Cancelar pedido

- **Método:** `PATCH`
- **URL:** `/orders/{order_id}/cancel`

**Body ejemplo:**

```json
{
  "cancelled_by": "cliente_001",
  "reason": "Me confundí al pedir"
}
```

---

### 6.2. ms-cumplimiento (Fulfillment / Workflow)

**Base URL:**

```text
https://gc8sncxhie.execute-api.us-east-1.amazonaws.com/dev
```

Todos requieren:

```http
x-tenant-id: CHINAWOK_LIMA_CENTRO
Content-Type: application/json
```

#### 6.2.1. Asignar cocinero

- **Método:** `POST`
- **URL:** `/orders/{order_id}/assign-cook`

**Body:**

```json
{
  "staff_id": "COOK_01",
  "staff_name": "Juan Cocinero"
}
```

#### 6.2.2. Marcar empacado

- **Método:** `POST`
- **URL:** `/orders/{order_id}/mark-packed`

**Body:**

```json
{
  "staff_id": "PACKER_01",
  "staff_name": "Ana Empacadora"
}
```

#### 6.2.3. Asignar repartidor

- **Método:** `POST`
- **URL:** `/orders/{order_id}/assign-delivery`

**Body:**

```json
{
  "staff_id": "DELIVERY_01",
  "staff_name": "Luis Repartidor"
}
```

#### 6.2.4. Marcar entregado

- **Método:** `POST`
- **URL:** `/orders/{order_id}/mark-delivered`

**Body:**

```json
{
  "staff_id": "DELIVERY_01",
  "staff_name": "Luis Repartidor"
}
```

---

### 6.3. ms-status (Estado y Dashboard)

**Base URL:**

```text
https://93icxxrllb.execute-api.us-east-1.amazonaws.com/dev
```

#### 6.3.1. Obtener estado actual de un pedido

- **Método:** `GET`
- **URL:** `/status/order/{order_id}`

#### 6.3.2. Obtener historial (timeline) de un pedido

- **Método:** `GET`
- **URL:** `/status/order/{order_id}/history`

#### 6.3.3. Dashboard

- **Método:** `GET`
- **URL:** `/status/dashboard`

#### 6.3.4. Pedidos por cliente (vista cliente)

- **Método:** `GET`
- **URL:** `/status/customer/{customer_id}`

---

## 7. Prueba end-to-end (resumen)

1. **Crear pedido (cliente)**  
   `POST /orders` (ms-pedidos).

2. **Ver estado inicial**  
   `GET /status/order/{order_id}` (ms-status).

3. **Flujo staff (cumplimiento):**
   1. `POST /orders/{order_id}/assign-cook`
   2. `POST /orders/{order_id}/mark-packed`
   3. `POST /orders/{order_id}/assign-delivery`
   4. `POST /orders/{order_id}/mark-delivered`

4. **Ver estado final + historial + dashboard**  
   - `GET /status/order/{order_id}`  
   - `GET /status/order/{order_id}/history`  
   - `GET /status/dashboard`  
   - `GET /status/customer/{customer_id}`

---
