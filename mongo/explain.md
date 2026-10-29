# Índices y análisis con `explain("executionStats")` (5.5)

Los índices se definen en [`indices.js`](indices.js) y los crea `scripts/cargar.py` después de cargar los datos. Los números de este documento salen de [`explain.js`](explain.js) y se pueden reproducir con:

```bash
python scripts/cargar.py
docker compose exec mongo mongosh ecommerce --quiet --file /scripts/explain.js
```

## Índices creados

| Colección | Índice | Tipo | Para qué |
|---|---|---|---|
| productos | `{sku: 1}` | único | Integridad: no puede haber dos productos con el mismo código |
| productos | `{categoria: 1, precio: 1}` | compuesto | RF2: listar por categoría con rango y orden de precio |
| clientes | `{email: 1}` | único | Integridad y búsqueda de un cliente por email |
| pedidos | `{cliente_id: 1, fecha: -1}` | compuesto | RF5: pedidos de un cliente, del más reciente al más viejo |
| pedidos | `{estado: 1, fecha: 1}` | compuesto | RF7: reportes por estado en un período |

Además está el índice `_id_`, que Mongo crea siempre.

## Cómo leer los resultados

Con 194 a 208 documentos por colección, los tiempos dan 0 o 1 ms en todos los casos y no sirven para comparar (la consigna lo aclara). Por eso se comparan las cantidades de trabajo que informa `executionStats`:

- **devueltos** (`nReturned`): documentos del resultado.
- **claves** (`totalKeysExamined`): entradas del índice que se leyeron.
- **docs** (`totalDocsExamined`): documentos que se leyeron de la colección.

En el caso ideal, claves = docs = devueltos: no se lee nada que después se descarte. Cada consulta se corrió con el índice y forzando `hint({$natural: 1})`, que obliga a un `COLLSCAN` (recorrer la colección entera).

## Resultados

### 1. Smartphones entre $200 y $1000, ordenados por precio

```js
db.productos.find({ categoria: "smartphones", precio: { $gte: 200, $lte: 1000 } }).sort({ precio: 1 })
```

| Plan | Devueltos | Claves | Docs |
|---|---:|---:|---:|
| `IXSCAN(categoria_precio)` → `FETCH` | 13 | 13 | 13 |
| `COLLSCAN` → `SORT` | 13 | 0 | 194 |
| `IXSCAN({precio: 1, categoria: 1})` → `FETCH` (orden inverso, temporal) | 13 | 23 | 13 |

- Con el índice se leen solo los 13 productos del resultado. Sin él se leen los 194 y además aparece una etapa `SORT`: el orden se hace en memoria.
- Con el índice no hay `SORT`, porque dentro de una categoría las claves ya están ordenadas por precio.
- **Por qué importa el orden de los campos (regla ESR: Equality, Sort, Range).** Con `{precio, categoria}` el índice recorre *todos* los productos entre $200 y $1000, de cualquier categoría (23 claves), y descarta los que no son smartphones. Con `{categoria, precio}` salta directo al tramo de smartphones y dentro de él lee solo el rango de precios. Con más productos, esa diferencia crece.

### 2. Pedidos de un cliente, del más reciente al más viejo

```js
db.pedidos.find({ cliente_id: <cliente con más pedidos> }).sort({ fecha: -1 })
```

| Plan | Devueltos | Claves | Docs |
|---|---:|---:|---:|
| `IXSCAN(cliente_fecha)` → `FETCH` | 5 | 5 | 5 |
| `COLLSCAN` → `SORT` | 5 | 0 | 208 |

Es la consulta más frecuente de un e-commerce ("mis pedidos"). Con el índice el costo depende de cuántos pedidos tiene el cliente, no de cuántos pedidos hay en total: sin índice, cada cliente que entra a ver sus pedidos obliga a leer la colección completa.

### 3. Pedidos por estado en un período

```js
db.pedidos.find({ estado: "cancelado", fecha: { $gte: ISODate("2026-01-01") } }).sort({ fecha: 1 })
```

| Consulta | Plan | Devueltos | Claves | Docs |
|---|---|---:|---:|---:|
| cancelados desde 2026 | `IXSCAN(estado_fecha)` → `FETCH` | 18 | 18 | 18 |
| cancelados desde 2026, sin índice | `COLLSCAN` → `SORT` | 18 | 0 | 208 |
| entregados desde 2026 | `IXSCAN(estado_fecha)` → `FETCH` | 159 | 159 | 159 |

El índice es eficiente en los dos casos (claves = devueltos), pero **la ganancia depende de la selectividad**. Para los cancelados evita leer 190 documentos. Para los entregados, que son la gran mayoría (183 de 208 pedidos), lee 159 en lugar de 208: casi no ahorra trabajo. Un índice sirve más cuanto más chico es el resultado comparado con la colección. Para reportes sobre todos los pedidos (por ejemplo, ventas por mes) conviene un `aggregate` que recorra la colección entera, y ahí este índice no aporta.

### 4. Índices únicos

```
E11000 duplicate key error collection: ecommerce.productos index: sku_unico dup key: { sku: "BEA-ESS-ESS-001" }
```

`sku_unico` y `email_unico` no están por rendimiento sino por **integridad**. Mongo no tiene claves primarias de negocio ni restricciones `UNIQUE` aparte de los índices, así que esta es la única forma de que la base rechace un duplicado, incluso si llegan dos altas del mismo producto al mismo tiempo. En la API, este error (código 11000) se va a traducir en un `409 Conflict`.

## Costo de los índices

### Almacenamiento

| Colección | Datos (bytes) | Índices (bytes) |
|---|---:|---:|
| productos | 263 140 | 45 056 |
| clientes | 69 590 | 28 672 |
| pedidos | 265 502 | 49 152 |

Los índices ocupan entre un 17 % y un 41 % de lo que ocupan los datos. Con tan pocos documentos, el tamaño de cada índice está dominado por el bloque mínimo que reserva el motor de almacenamiento (por eso varios miden exactamente 20 480 o 24 576 bytes): no hay que leerlo como una proporción que se mantenga al crecer. Un índice guarda solo los campos indexados y un puntero al documento, así que con muchos documentos ocupa bastante menos que la colección.

### Mantenimiento en las escrituras

Cada índice es una estructura más que hay que actualizar cuando cambia un campo indexado:

- **Insertar un pedido** actualiza 3 índices (`_id_`, `cliente_fecha`, `estado_fecha`). **Cambiar su estado** (por ejemplo, al cancelarlo) actualiza `estado_fecha`.
- **Descontar stock** (`$inc` sobre `stock`) no toca ningún índice, porque `stock` no está indexado. Esto es importante para el caso de consistencia: la operación que se repite en cada compra no paga costo de mantenimiento.
- **Cambiar el precio** de un producto actualiza `categoria_precio`. Es poco frecuente comparado con las lecturas del catálogo, así que el costo vale la pena.

Por eso no se indexa todo: no se indexó `stock`, `marca` ni `rating_promedio`, porque ninguna consulta frecuente los usa como filtro principal. Un índice que no se usa ocupa espacio y vuelve más lentas todas las escrituras.

## Pendiente (extensión opcional)

- Índice de texto sobre `titulo` y `descripcion` para buscar productos por palabra.
- Cuando estén las 10 consultas de `consultas.js`, revisar si alguna necesita otro índice.
