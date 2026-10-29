# TP Integrador NoSQL · Diseño del modelo documental (entregable 5.1)

Base de Datos Aplicada · UCC · Grupo: Justo Solana Allende, Salvador Solana Allende, Agustín Rodríguez Richard
Estado: **implementado** (29/10/2026). Las decisiones que estaban abiertas se tomaron al implementar y están en la sección 9; quedan para confirmar en grupo.

---

## 1. Problema

Una tienda online necesita administrar un **catálogo de productos heterogéneo** (celulares, ropa, almacén, muebles, motos…) donde cada categoría tiene atributos propios, registrar **pedidos de clientes** que descuenten stock sin dejar datos inconsistentes y **analizar las ventas** (importe por período, pedidos por estado, ticket promedio, categorías más vendidas).

**Por qué una base documental:** los productos no comparten un esquema fijo. Un smartphone tiene RAM y almacenamiento, una remera tiene talles y material y un producto de almacén tiene vencimiento. En un modelo relacional esto se resuelve con muchas columnas casi siempre vacías o con una tabla de atributos clave-valor (EAV) que complica las consultas. Además, un pedido se lee y se escribe siempre junto con sus ítems, y eso encaja con un documento que los contiene.

## 2. Actores

| Actor | Qué hace |
|---|---|
| Administrador de catálogo | Alta, baja y modificación de productos, precios y stock |
| Cliente | Compra productos y deja reseñas |
| Área comercial / analista | Consulta reportes e indicadores de ventas |

## 3. Requerimientos funcionales

- **RF1** CRUD de productos (entidad principal).
- **RF2** Listar productos con filtros: categoría, rango de precio, marca, solo con stock.
- **RF3** Registrar un pedido y **descontar el stock** de cada producto (caso de consistencia).
- **RF4** Cancelar un pedido y **devolver el stock**.
- **RF5** Consultar los pedidos de un cliente, ordenados por fecha.
- **RF6** Agregar una reseña a un producto y recalcular su rating.
- **RF7** Reportes: ventas por período, por categoría, por estado y ticket promedio.

## 4. Fuente de datos

Se usa **DummyJSON** (https://dummyjson.com), descargado una sola vez y versionado en `data/raw/`:

| Archivo | Documentos | Observaciones |
|---|---|---|
| products.json | 194 | 24 categorías (3 a 30 productos c/u); `brand` ausente en 92; 4 con stock 0 y 25 con stock < 10; 3 reviews c/u |
| users.json | 208 | Trae campos sensibles falsos (password, ssn, bank, crypto…) que se descartan |
| carts.json | 208 | 800 ítems; todos los productos referenciados existen; sin fecha ni estado |

**Por qué se versiona el JSON y no se baja de la API en cada carga:** la carga tiene que funcionar desde un entorno limpio y dar siempre el mismo resultado. DummyJSON cambia fechas y contenido, y puede no estar disponible.

Un script de transformación (`scripts/transformar.py`) convierte los archivos crudos en los documentos finales. Usa **`random.seed(42)`** para los datos que genera (fechas, estados, atributos), así que cada corrida produce exactamente los mismos documentos.

## 5. Colecciones

Total: **610 documentos** (194 productos + 208 clientes + 208 pedidos), más 1 documento técnico en `contadores` (5.4).

### 5.1. `productos` (entidad principal)

```json
{
  "_id": ObjectId("..."),
  "sku": "SMA-APP-IPH-122",
  "titulo": "iPhone 6",
  "descripcion": "...",
  "categoria": "smartphones",
  "marca": "Apple",
  "precio": 299.99,
  "descuento_pct": 6.69,
  "stock": 25,
  "etiquetas": ["smartphones", "apple"],
  "dimensiones": { "ancho": 7.1, "alto": 13.8, "profundidad": 0.7 },
  "peso": 1,
  "atributos": { "ram_gb": 1, "almacenamiento_gb": 16, "pantalla_pulgadas": 4.7, "sistema_operativo": "iOS" },
  "garantia": "1 year warranty",
  "politica_devolucion": "30 days return policy",
  "envio": "Ships in 1 week",
  "cantidad_minima": 2,
  "rating_promedio": 4.33,
  "reviews": [
    { "rating": 5, "comentario": "Highly impressed!", "fecha": ISODate("2025-04-30T09:41:02Z"),
      "autor": "Lucas Gordon", "email": "lucas.gordon@x.dummyjson.com" }
  ],
  "imagenes": ["https://cdn.dummyjson.com/..."],
  "creado_en": ISODate("..."),
  "actualizado_en": ISODate("...")
}
```

| Campo | Obligatorio | Tipo / nota |
|---|---|---|
| sku, titulo, categoria, precio, stock | Sí | `sku` único; `precio` > 0; `stock` ≥ 0 |
| marca | **No** (falta en 92 productos) | Atributo opcional real del dataset |
| atributos | **No**: depende de la categoría | Objeto con campos variables (ver tabla) |
| reviews | Sí (puede ser `[]`) | Arreglo embebido |
| etiquetas, imagenes | Sí (pueden ser `[]`) | Arreglos de strings |
| dimensiones | No | Documento anidado |
| activo, eliminado_en | No | Solo existen en productos dados de baja (`activo: false`). Ausente = activo |

**Atributos variables por categoría** (generados en la transformación, con semilla fija):

| Categorías | `atributos` |
|---|---|
| smartphones, tablets, laptops | ram_gb, almacenamiento_gb, pantalla_pulgadas, sistema_operativo |
| mens-shirts, tops, womens-dresses | talles (arreglo), material, color |
| mens-shoes, womens-shoes | talles (arreglo numérico), material |
| groceries | vencimiento (fecha), peso_neto_g, apto_celiacos (bool) |
| fragrances, beauty, skin-care | volumen_ml |
| furniture, home-decoration | material, requiere_armado (bool) |
| motorcycle, vehicle | cilindrada_cc, combustible, anio |
| mens-watches, womens-watches | resistencia_agua_m, tipo_movimiento |
| resto (kitchen, sports, sunglasses, bags, jewellery, mobile-accessories) | **sin** `atributos` → caso de campo ausente |

**Campos que se descartan o recalculan:**
- `availabilityStatus` se descarta porque se deduce del `stock`. Guardarlo duplicado permitiría inconsistencias, como un producto "In Stock" con stock 0.
- `rating` se **recalcula** como `rating_promedio` a partir de las reviews y se actualiza al agregar una. Es el patrón *computed*: se paga en la escritura para que la lectura sea barata.
- `meta.barcode` y `meta.qrCode` se descartan porque no se usan. `meta.createdAt` y `meta.updatedAt` pasan a `creado_en` y `actualizado_en`.

### 5.2. `clientes`

```json
{
  "_id": ObjectId("..."),
  "nombre": "Emily",
  "apellido": "Johnson",
  "email": "emily.johnson@x.dummyjson.com",
  "telefono": "+81 965-431-3024",
  "fecha_nacimiento": ISODate("1996-05-30"),
  "genero": "female",
  "direccion": {
    "calle": "626 Main Street", "ciudad": "Phoenix", "estado": "Mississippi",
    "codigo_postal": "29112", "pais": "United States"
  },
  "fecha_alta": ISODate("...")
}
```

- `email` es obligatorio y único. Los demás campos son obligatorios salvo `telefono`.
- `fecha_alta` se genera entre ene-2024 y oct-2025, antes del primer pedido, para que ningún cliente compre antes de existir.
- **Se descartan** password, ssn, ein, bank, crypto, ip, macAddress, userAgent, bloodGroup, height, weight, eyeColor, hair, university, company, image y maidenName. El criterio es la **minimización de datos**: un e-commerce no necesita esos datos, y la consigna pide no versionar secretos.
- **Las coordenadas se descartan:** en DummyJSON son aleatorias (por ejemplo, latitud −77, en la Antártida) y no coinciden con la ciudad, así que no sirven para consultas geoespaciales.

### 5.3. `pedidos`

```json
{
  "_id": ObjectId("..."),
  "numero": 1001,
  "cliente_id": ObjectId("..."),
  "cliente": { "nombre": "Emily Johnson", "email": "emily.johnson@x.dummyjson.com" },
  "fecha": ISODate("2026-03-14T15:20:00Z"),
  "estado": "entregado",
  "historial_estados": [
    { "estado": "pendiente", "fecha": ISODate("2026-03-14T15:20:00Z") },
    { "estado": "pagado",    "fecha": ISODate("2026-03-14T15:25:00Z") },
    { "estado": "enviado",   "fecha": ISODate("2026-03-16T10:00:00Z") },
    { "estado": "entregado", "fecha": ISODate("2026-03-19T18:30:00Z") }
  ],
  "metodo_pago": "tarjeta_credito",
  "direccion_envio": { "calle": "626 Main Street", "ciudad": "Phoenix", "estado": "Mississippi",
                       "codigo_postal": "29112", "pais": "United States" },
  "items": [
    { "producto_id": ObjectId("..."), "sku": "SMA-APP-IPH-122", "titulo": "iPhone 6",
      "precio_unitario": 299.99, "descuento_pct": 6.69, "cantidad": 3, "subtotal": 839.76 }
  ],
  "totales": { "bruto": 899.97, "descuento": 60.21, "total": 839.76 },
  "cantidad_unidades": 3
}
```

- **Estados:** `pendiente → pagado → enviado → entregado`, o `cancelado` desde pendiente o pagado.
- **Datos generados a partir del carrito:** `fecha` repartida entre nov-2025 y oct-2026, `estado` con más peso en "entregado", `metodo_pago`, un `historial_estados` coherente con el estado final, y `direccion_envio` copiada del cliente.
- **Reasignación de clientes:** en DummyJSON hay un carrito por usuario, lo que no permite medir recompra. La transformación reasigna `cliente_id`, con la misma semilla, para que haya clientes con varios pedidos y clientes sin ninguno.
- El stock de los productos se carga **tal cual viene en el dataset**: los pedidos históricos no lo vuelven a descontar.
- **Estado según la fecha:** el historial se arma con demoras realistas (pago en minutos, envío en 0,5 a 3 días, entrega en 1 a 6 días) y se corta en una fecha "hoy" fija (28/10/2026). Así un pedido viejo queda entregado y solo los recientes quedan en camino. Un 12% se cancela desde pendiente o pagado.
- **Ítems repetidos:** 12 carritos repiten un producto en dos líneas. Se fusionan en un ítem sumando las cantidades.
- **`numero`** es correlativo en orden cronológico, desde 1001.
- **Resultado** (verificado con el script): 208 pedidos, 788 ítems, 2417 unidades; 151 clientes con al menos un pedido (45 con recompra) y 57 sin pedidos; 183 entregados, 23 cancelados, 1 enviado y 1 pagado.

### 5.4. `contadores` (técnica)

```json
{ "_id": "pedidos", "ultimo": 1208 }
```

Guarda el último `numero` de pedido usado. La API lo incrementa con `$inc` dentro de la transacción del pedido. Buscar el máximo y sumarle 1 fallaría con dos pedidos simultáneos, que leerían el mismo máximo: el `$inc` sobre un documento es atómico, y si dos transacciones lo modifican a la vez, Mongo detecta el conflicto y una se reintenta. `cargar.py` lo inicializa con el último número del seed. No es una entidad del dominio.

## 6. Relaciones y decisiones: embeber o referenciar

| Relación | Cardinalidad | Decisión | Por qué |
|---|---|---|---|
| Producto → reviews | 1 a pocos | **Embebido** | Se leen siempre con el producto y están acotadas. Si pudieran ser miles (riesgo del límite de 16 MB por documento y de documentos que crecen sin parar), se pasarían a una colección `reviews`, o se dejarían solo las últimas N embebidas (patrón *subset*). |
| Cliente → dirección | 1 a 1 | **Embebido** | Se lee siempre con el cliente y no tiene identidad propia. |
| Pedido → ítems | 1 a pocos | **Embebido** | Un pedido sin ítems no existe. Se crean juntos en una sola escritura y no cambian después de confirmados. |
| Ítem → producto | N a 1 | **Referencia (`producto_id`) + copia** de sku, título y precio | El precio y el título se **congelan al momento de la compra**: si el producto cambia de precio o se borra, el pedido no se altera. La referencia sirve para descontar o devolver stock y para cruzar con el catálogo. |
| Pedido → cliente | N a 1 | **Referencia (`cliente_id`) + copia** de nombre, email y dirección de envío | El cliente tiene vida propia y lo comparten muchos pedidos. La dirección se copia porque el envío se hace a la dirección vigente en la fecha de la compra. |
| Producto → categoría | N a 1 | **Campo string** (sin colección) | La categoría no tiene datos propios, es solo una etiqueta. Si tuviera descripción, responsable o jerarquía, se justificaría una colección. |

**Consecuencia para el CRUD:** como cada pedido guarda una copia de los datos del producto, borrar un producto no rompe la visualización de los pedidos históricos. Aun así el DELETE es **lógico** (`activo: false`): el análisis de ventas por categoría hace `$lookup` de los ítems a `productos`, y con un borrado físico esas ventas quedarían sin categoría (ver sección 9).

## 7. Caso de consistencia (adelanto de la sección 5.6)

**Operación:** registrar un pedido = (a) verificar que haya stock de cada ítem, (b) descontarlo en **N documentos de `productos`** y (c) insertar el documento en `pedidos`.

**Qué pasa si falla a mitad de camino:** si se descuenta el stock de dos productos y la inserción del pedido falla, queda stock "perdido" sin ningún pedido que lo explique. Si se inserta el pedido y falla un descuento, se vende algo que no hay.

**Solución:**
- Un `update_one({_id, stock: {$gte: cantidad}}, {$inc: {stock: -cantidad}})` es **atómico para un producto**: evita la sobreventa entre compras concurrentes. Pero **no cubre varios documentos a la vez**.
- Por eso el pedido completo se hace con una **transacción multidocumento**: si cualquier ítem no tiene stock, se aborta y no queda nada a medias.
- **Requisito de entorno:** MongoDB tiene que correr como **replica set**. En Docker Compose se levanta como replica set de un solo nodo (`--replSet rs0` más `rs.initiate()`).
- La cancelación de un pedido (devolver stock y cambiar el estado) usa el mismo mecanismo.

## 8. Índices (implementados en `mongo/indices.js`, analizados en `mongo/explain.md`)

| Colección | Índice | Consulta que apoya |
|---|---|---|
| productos | `{sku: 1}` único | Unicidad del código de negocio |
| productos | `{categoria: 1, precio: 1}` | RF2: filtrar por categoría y rango u orden de precio (regla ESR) |
| clientes | `{email: 1}` único | Unicidad y búsqueda por email |
| pedidos | `{cliente_id: 1, fecha: -1}` | RF5: pedidos de un cliente, del más reciente al más viejo |
| pedidos | `{estado: 1, fecha: 1}` | Reportes por estado y período |
| *(extensión, no implementada)* productos | texto sobre `titulo` y `descripcion` | Búsqueda de productos por palabra |

## 9. Decisiones tomadas al implementar (a confirmar en grupo)

- **DELETE de producto: lógico.** Marca `activo: false` y `eliminado_en`. La API trata al producto como inexistente (404 en GET, PATCH y DELETE; no aparece en el listado; no se puede comprar), pero el documento sigue en la base. Motivos: los pedidos lo referencian por `producto_id` para devolver stock al cancelar y el análisis lo cruza para obtener la categoría. Costo: todas las consultas de la API filtran `activo: {$ne: false}`, y el `sku` de un producto dado de baja no se puede reutilizar (sigue en el índice único).
- **Nombres de campos en español.** La transformación ya los genera así, y el dominio se explica en español en la defensa.
- **Sin `$jsonSchema`.** La validación se hace con Pydantic en la API (tipos, rangos, campos obligatorios y desconocidos). La validación en Mongo protegería también contra escrituras que no pasen por la API; queda como extensión opcional.
- **`cantidad_minima`: dato informativo.** Se conserva como viene del dataset, pero la API no la valida al crear un pedido. Validarla haría que casi todos los pedidos históricos fueran inválidos (los carritos tienen como máximo 5 unidades por ítem, y el mínimo llega a 50).
- **Reparto de tareas:** pendiente.
