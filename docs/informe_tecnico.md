# Informe técnico · E-commerce sobre MongoDB

Base de Datos Aplicada · UCC · Trabajo Práctico Integrador
Grupo: Justo Solana Allende, Salvador Solana Allende, Agustín Rodríguez Richard

Todos los números de este informe salen de correr los scripts sobre la base recién cargada (`python scripts/cargar.py`). Los datos son reproducibles: se generan con semilla fija.

---

## 1. Problema

Una tienda online necesita:

- administrar un **catálogo heterogéneo** (celulares, ropa, almacén, muebles, vehículos…), donde cada categoría tiene atributos propios;
- registrar **pedidos** que descuenten stock sin dejar datos inconsistentes;
- **analizar las ventas** para tomar decisiones comerciales.

**Por qué una base documental.** Los productos no comparten un esquema fijo: un smartphone tiene RAM y almacenamiento, una remera tiene talles y material, un producto de almacén tiene vencimiento. En un modelo relacional esto obliga a usar muchas columnas casi siempre vacías o una tabla clave-valor (EAV) que complica cada consulta. En MongoDB cada producto guarda solo los atributos que tiene, en un subdocumento `atributos`, y se consultan igual que cualquier otro campo (`"atributos.ram_gb": {$gte: 8}`). Además, un pedido se lee y se escribe siempre junto con sus ítems, y eso encaja con un documento que los contiene.

**Actores:** administrador de catálogo (CRUD de productos), cliente (compra y deja reseñas) y área comercial (reportes).

## 2. Requerimientos funcionales

| Id | Requerimiento | Dónde se resuelve |
|---|---|---|
| RF1 | CRUD de productos | `POST/GET/PATCH/DELETE /productos` |
| RF2 | Listar productos con filtros (categoría, precio, marca, con stock) | `GET /productos`, índice `categoria_precio` |
| RF3 | Registrar un pedido descontando stock | `POST /pedidos` (transacción) |
| RF4 | Cancelar un pedido devolviendo stock | `POST /pedidos/{id}/cancelar` (transacción) |
| RF5 | Pedidos de un cliente por fecha | `GET /pedidos?cliente_id=`, índice `cliente_fecha` |
| RF6 | Agregar una reseña y recalcular el rating | `POST /productos/{id}/reviews` (operación atómica) |
| RF7 | Reportes de ventas | Consultas 7 a 10, notebook de análisis |

## 3. Modelo documental

El detalle completo (documentos de ejemplo, campos obligatorios y opcionales, atributos por categoría) está en [`01_diseno_modelo_documental.md`](01_diseno_modelo_documental.md). Resumen:

| Colección | Documentos | Contenido |
|---|---:|---|
| `productos` (entidad principal) | 194 | Datos del producto, `atributos` variables por categoría, `reviews` embebidas, `dimensiones` anidadas |
| `clientes` | 208 | Datos personales mínimos y `direccion` embebida |
| `pedidos` | 208 | `items` embebidos, copia de datos del cliente y la dirección, `historial_estados`, `totales` |
| `contadores` | 1 | Último número de pedido (técnica, no es del dominio) |

Los datos salen de DummyJSON (`data/raw/`) y se transforman con `scripts/transformar.py`, que descarta los campos sensibles ficticios del dataset (password, ssn, bank…), genera los atributos por categoría y arma los pedidos a partir de los carritos con fechas, estados y recompra simulados. Hay casos límite reales: 92 productos sin marca (campo ausente, no `null`), 74 sin `atributos`, 4 con stock 0 y 57 clientes sin pedidos.

### Embeber o referenciar

| Relación | Decisión | Por qué |
|---|---|---|
| Producto → reviews | Embebido | Se leen siempre con el producto y son pocas. Si pudieran ser miles, se pasarían a una colección aparte (límite de 16 MB por documento). |
| Cliente → dirección | Embebido | No tiene identidad propia. |
| Pedido → ítems | Embebido | Un pedido sin ítems no existe; se crean juntos y no cambian. |
| Ítem → producto | Referencia (`producto_id`) + copia de sku, título y precio | El precio queda **congelado a la fecha de compra**. La referencia sirve para devolver stock y cruzar con el catálogo. |
| Pedido → cliente | Referencia (`cliente_id`) + copia de nombre, email y dirección | El cliente es compartido por muchos pedidos. La dirección se copia porque el envío va a la vigente al comprar. |
| Producto → categoría | String | La categoría no tiene datos propios. |

### Decisiones tomadas al implementar

- **Baja lógica de productos** (`activo: false`). Los pedidos referencian productos para devolver stock y el análisis los cruza para obtener la categoría; un borrado físico dejaría esas ventas sin categoría. Costo: las consultas de la API filtran `activo: {$ne: false}` y un sku dado de baja no se reutiliza.
- **Validación en la API con Pydantic**, sin `$jsonSchema` en Mongo. Se rechazan tipos y rangos inválidos, campos obligatorios faltantes y campos desconocidos (`extra="forbid"`: un `"precioo"` mal escrito da 422 en lugar de guardarse en silencio).
- **`cantidad_minima` es informativa**: validarla haría inválidos casi todos los pedidos históricos.

## 4. Consultas

[`mongo/consultas.js`](../mongo/consultas.js) tiene 10 consultas, cada una con objetivo, comando y resultado esperado. La salida de la ejecución está en [`mongo/consultas_salida.txt`](../mongo/consultas_salida.txt).

| # | Tipo pedido por la consigna | Pregunta del dominio | Resultado |
|---|---|---|---|
| 1 | Comparación (`$gt`, `$lt`) | ¿Qué productos están por agotarse? | 21 productos |
| 2 | Comparación (`$in`, `$lte`) | ¿Qué tecnología hay por menos de $500? | 15 productos |
| 3 | Lógica (`$and` + `$or`) | ¿Qué productos con stock tienen gran descuento o gran valoración? | 64 productos |
| 4 | Anidados (`atributos.ram_gb`) | ¿Qué equipos tienen ≥ 8 GB de RAM y ≥ 256 GB? | 8 productos |
| 5 | Arreglos (`$elemMatch`) | ¿Qué productos tienen reseñas negativas? | 101 productos |
| 6 | Proyección + sort + limit | ¿Cuáles son los 5 pedidos más grandes? | El mayor: $155.507 |
| 7 | Aggregate | ¿Cuánto se factura por mes? | 12 meses |
| 8 | Aggregate (`$unwind`) | ¿Cuáles son los productos más vendidos? | Top 5 con 25-29 unidades |
| 9 | Agrupamiento estadístico | ¿Cómo se distribuyen los precios por categoría? | Promedio, mín., máx. y desvío de 24 categorías |
| 10 | Libre (`$lookup` + `$setWindowFields`) | ¿Qué categorías generan la facturación? | `vehicle`: 52,6 % |

## 5. Índices

Definidos en [`mongo/indices.js`](../mongo/indices.js) y creados por `cargar.py`. El análisis completo, con la salida de `explain("executionStats")`, está en [`mongo/explain.md`](../mongo/explain.md).

| Índice | Para qué | Con índice (claves/docs) | Sin índice (docs) |
|---|---|---|---|
| `productos {sku: 1}` único | Integridad: rechaza duplicados (E11000 → 409) | — | — |
| `productos {categoria: 1, precio: 1}` | RF2 | 13 / 13 | 194 + orden en memoria |
| `clientes {email: 1}` único | Integridad y búsqueda | — | — |
| `pedidos {cliente_id: 1, fecha: -1}` | RF5 | 5 / 5 | 208 + orden en memoria |
| `pedidos {estado: 1, fecha: 1}` | Reportes por estado | 18 / 18 | 208 + orden en memoria |

Conclusiones del análisis:

- **Regla ESR.** El mismo índice con los campos al revés (`{precio, categoria}`) lee 23 claves en lugar de 13, porque recorre los precios de todas las categorías.
- **Selectividad.** `estado_fecha` sobre "entregado" (88 % de los pedidos) lee 159 de 208 documentos: casi no ahorra trabajo. Un índice sirve más cuanto más chico es el resultado comparado con la colección.
- **Costo.** Los índices ocupan entre el 17 % y el 41 % de lo que ocupan los datos (inflado por el tamaño mínimo de bloque con tan pocos documentos), y cada inserción de pedido actualiza 3 índices. `stock` no se indexó: se modifica en cada compra y ninguna consulta frecuente filtra por él.

## 6. Consistencia y transacciones

**Operación:** registrar un pedido = verificar y descontar el stock de **N productos** + insertar **1 pedido** + incrementar el **contador** de números.

**Qué pasa si falla a mitad de camino:** si se descuenta el stock de dos productos y la inserción del pedido falla, queda stock "perdido" sin pedido que lo explique. Si se inserta el pedido y falla un descuento, se vende algo que no hay.

**Solución implementada** ([`api/services/pedidos.py`](../api/services/pedidos.py)):

1. **Operación atómica por producto.** `find_one_and_update({_id, stock: {$gte: cantidad}}, {$inc: {stock: -cantidad}})`: la verificación y el descuento son una sola operación sobre el documento, así que dos compras simultáneas no pueden dejar el stock negativo.
2. **Transacción multidocumento para el pedido completo.** Todo corre dentro de `session.with_transaction(...)`. Si un ítem no tiene stock, el producto no existe o falla cualquier paso, se lanza una excepción, la transacción se aborta y Mongo descarta todos los cambios. `with_transaction` además reintenta ante errores transitorios, como el conflicto de dos pedidos que incrementan el contador a la vez.
3. **Cancelación con el mismo mecanismo**: cambiar el estado y devolver el stock de cada ítem van en una transacción. El cambio de estado lleva la condición `estado ∈ {pendiente, pagado}` en el filtro, así dos cancelaciones simultáneas no devuelven el stock dos veces.
4. **Requisito de entorno:** Mongo corre como **replica set de un nodo** (`--replSet rs0`), porque las transacciones necesitan el oplog del replica set.

Para contrastar, la reseña (RF6) **no** usa transacción: agregar la reseña y recalcular el promedio afecta a un solo documento y se resuelve con un update con pipeline, que es atómico.

**Prueba del comportamiento ante errores** ([`tests/test_pedidos.py`](../tests/test_pedidos.py)):

| Prueba | Qué verifica |
|---|---|
| `test_sin_stock_en_un_item_no_se_descuenta_ninguno` | El primer ítem se descuenta y el segundo no tiene stock → 409, el stock del primero vuelve a su valor, no se crea el pedido y el contador no avanza |
| `test_producto_inexistente_no_deja_nada_a_medias` | Lo mismo con un producto que no existe → 404 |
| `test_falla_inesperada_despues_de_descontar_stock` | Se simula una caída al insertar el pedido, con el stock ya descontado → no queda rastro |
| `test_cancelar_devuelve_stock` | Cancelar devuelve el stock; cancelar dos veces da 409 y no lo devuelve de nuevo |
| `test_compras_simultaneas_de_la_ultima_unidad` | 5 compras en paralelo de la última unidad → exactamente 1 se concreta (extensión: prueba de concurrencia) |

**Evidencia de que la transacción es necesaria.** Se corrieron las pruebas reemplazando la transacción por la ejecución directa de las operaciones: fallan exactamente las 3 primeras de la tabla (queda stock descontado sin pedido). La de concurrencia sigue pasando, porque la sobreventa ya la evita la operación atómica del punto 1. Cada mecanismo resuelve un problema distinto: **la operación atómica evita vender de más; la transacción evita quedar a medias.**

## 7. API

FastAPI + PyMongo + Pydantic v2, con responsabilidades separadas en capas:

```
routers/       HTTP: parámetros, códigos de estado (no conocen Mongo)
services/      reglas de negocio y transacciones (no conocen HTTP)
repositories/  ÚNICO lugar que arma consultas a MongoDB
schemas/       validación de entrada y forma de las respuestas
db.py          conexión desde variables de entorno y helper de transacción
```

- **Códigos HTTP:** 201 al crear (con `Location`), 204 al borrar, 404 si no existe, 409 por sku duplicado, falta de stock o estado inválido, 422 por datos o ids mal formados, 503 si Mongo no responde. Los errores de negocio se traducen a HTTP en un solo lugar (`main.py`).
- **Demostración:** Swagger en `/docs`.
- **Pruebas:** 24 pruebas con pytest (`tests/`), sobre una base aparte (`ecommerce_test`) cargada con el mismo seed y los mismos índices.
- En Docker, la API se conecta a `mongodb://mongo:27017/?replicaSet=rs0` (nombre del servicio, nunca `localhost`).

## 8. Análisis de datos

[`analysis/analisis_ventas.ipynb`](../analysis/analisis_ventas.ipynb) se conecta a Mongo, resuelve los cruces con agregaciones (`$lookup`) y analiza con Pandas. Indicadores principales:

| Indicador | Valor |
|---|---|
| Facturación del año (sin cancelados) | $3.052.020 en 185 pedidos |
| Ticket promedio / mediano | $16.497 / $1.626 |
| Facturación del 10 % de pedidos más grandes | 59,2 % del total |
| Participación de vehículos, relojes y motos | más del 90 % |
| Tasa de cancelación | 11,1 % (19,2 % con Mercado Pago) |
| Recompra | 29,8 % de los clientes que compraron; 57 clientes nunca compraron |
| Productos con demanda y < 2 meses de stock | 9 (4 ya en 0) |

Gráficos: facturación mensual, distribución del total por pedido (escala logarítmica) y facturación por categoría.

**Conclusión.** La facturación depende de pocas ventas de alto valor (vehículos, motos, relojes), lo que la vuelve volátil mes a mes y hace que el ticket promedio no represente al cliente típico. Se recomienda: seguir las ventas de alto valor por separado y usar la mediana como ticket de referencia; reponer ya los 9 productos con cobertura menor a dos meses, empezando por los 4 sin stock; investigar las cancelaciones con Mercado Pago, y activar a los clientes que nunca compraron.

## 9. Reproducibilidad

```bash
cp .env.example .env
docker compose up -d --wait --build
pip install -r requirements-dev.txt
python scripts/cargar.py
pytest
```

- `docker compose up` levanta Mongo, inicia el replica set (servicio `mongo-init`, idempotente) y la API. Los datos persisten en el volumen `mongo-data`.
- `cargar.py` reinicia la base y verifica conteos y referencias (Mongo no valida claves foráneas, así que se chequean en el script).
- Sin secretos: Mongo no tiene usuario y solo escucha en `127.0.0.1`; se versiona `.env.example`, no `.env`.

## 10. Limitaciones y posibles mejoras

- Los pedidos se simulan a partir de los carritos de DummyJSON: los números del análisis son reproducibles, pero no describen una tienda real.
- No hay autenticación ni CRUD de clientes (fuera del alcance de la consigna).
- El contador de pedidos es un único documento que modifican todas las transacciones de alta: con mucho tráfico sería un punto de contención.
- Extensiones posibles: índice de texto para buscar productos por palabra, validación `$jsonSchema` en Mongo y transiciones de estado del pedido (pagado, enviado, entregado) desde la API.
