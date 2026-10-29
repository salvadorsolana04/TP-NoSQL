# TP Integrador NoSQL · E-commerce sobre MongoDB

Base de Datos Aplicada · UCC · Justo Solana Allende, Salvador Solana Allende, Agustín Rodríguez Richard

Tienda online sobre **MongoDB 7**: catálogo de productos con atributos que cambian según la categoría, clientes y pedidos que descuentan stock dentro de una **transacción**. Incluye una API (FastAPI) con capa de repositorios, 10 consultas y agregaciones, índices analizados con `explain`, pruebas automáticas y un notebook de análisis de ventas, todo levantado con Docker Compose.

> ## 👉 Si recién llegás al repo (o le pasás un archivo a una IA), leé primero [`AGENTS.md`](AGENTS.md)
>
> Tiene el contexto completo: qué es cada carpeta, qué está hecho, por qué se tomó cada decisión, las reglas del proyecto y cómo verificar que todo funciona.
> **Si usás Codex, Cursor, Copilot u otro asistente**, pedile que lea `AGENTS.md` antes de tocar nada (Codex lo lee solo). Claude Code lee `CLAUDE.md`, que apunta al mismo contexto.
> Al pasarle un archivo suelto a una IA, pasale también `AGENTS.md`: sin él no sabe, por ejemplo, que el borrado de productos es lógico, que desde tu máquina hace falta `directConnection=true` o que los datos se generan con semilla fija.

## Qué hay en el repo

| Entregable (consigna) | Dónde está |
|---|---|
| 5.1 Diseño del modelo documental | [`docs/01_diseno_modelo_documental.md`](docs/01_diseno_modelo_documental.md) |
| 5.2 Scripts de transformación y carga | [`scripts/transformar.py`](scripts/transformar.py), [`scripts/cargar.py`](scripts/cargar.py), datos en `data/` |
| 5.3 Consultas (10) y su salida | [`mongo/consultas.js`](mongo/consultas.js), [`mongo/consultas_salida.txt`](mongo/consultas_salida.txt) |
| 5.4 API con repositorios | [`api/`](api/) (Swagger en `/docs`) |
| 5.5 Índices y explain | [`mongo/indices.js`](mongo/indices.js), [`mongo/explain.js`](mongo/explain.js), [`mongo/explain.md`](mongo/explain.md) |
| 5.6 Consistencia con transacción | [`api/services/pedidos.py`](api/services/pedidos.py), pruebas en [`tests/test_pedidos.py`](tests/test_pedidos.py) |
| 5.7 Análisis de datos | [`analysis/analisis_ventas.ipynb`](analysis/analisis_ventas.ipynb) |
| 5.8 Docker Compose | [`docker-compose.yml`](docker-compose.yml), [`.env.example`](.env.example) |
| 7 Informe técnico | [`docs/informe_tecnico.md`](docs/informe_tecnico.md) |

## Requisitos

- Docker con Docker Compose v2
- Python 3.12 o superior (para los scripts, las pruebas y el notebook)

## Puesta en marcha (después de clonar o de cada `git pull`)

1. Crear el archivo de configuración local a partir del ejemplo. **Sin este paso, Compose y los scripts no encuentran las variables.** El `.env` no se versiona; cada integrante tiene el suyo. Si `.env.example` cambió desde la última vez, revisá si hay variables nuevas.

   ```bash
   cp .env.example .env
   ```

2. Levantar MongoDB y la API. `--wait` espera a que el replica set esté iniciado, Mongo sea PRIMARY y la API responda. `--build` reconstruye la imagen de la API si cambió el código.

   ```bash
   docker compose up -d --wait --build
   ```

3. Crear un entorno virtual e instalar las dependencias (incluye pruebas y notebook):

   ```bash
   python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt
   ```

4. Cargar los datos. Borra la base `ecommerce`, carga `data/seed/`, verifica conteos (208 clientes, 194 productos, 208 pedidos) y referencias, inicializa el contador de pedidos y crea los índices. Se puede repetir cuando quieras volver al estado inicial.

   ```bash
   python scripts/cargar.py
   ```

5. Correr las pruebas (24). Usan una base aparte (`ecommerce_test`), así que no tocan los datos de la demo.

   ```bash
   pytest -v
   ```

## Usar la API

- Swagger (para probar los endpoints desde el navegador): <http://localhost:8000/docs>
- Si el puerto 8000 está ocupado en tu máquina, cambiá `API_PORT` en tu `.env` y volvé a correr `docker compose up -d --wait`.

| Método | Endpoint | Qué hace |
|---|---|---|
| POST | `/productos` | Crea un producto (201; 409 si el sku existe; 422 si los datos son inválidos) |
| GET | `/productos` | Lista con filtros: `categoria`, `marca`, `precio_min`, `precio_max`, `con_stock`, `orden`, `limite`, `desde` |
| GET | `/productos/{id}` | Obtiene un producto (404 si no existe; 422 si el id está mal formado) |
| PATCH | `/productos/{id}` | Modifica los campos enviados; un campo opcional en `null` se elimina |
| DELETE | `/productos/{id}` | Baja **lógica** (204) |
| POST | `/productos/{id}/reviews` | Agrega una reseña y recalcula el rating en una operación atómica |
| POST | `/pedidos` | Registra un pedido y descuenta el stock en una **transacción** (409 si falta stock: no se descuenta nada) |
| POST | `/pedidos/{id}/cancelar` | Cancela y devuelve el stock en una **transacción** (409 si ya se envió) |
| GET | `/pedidos?cliente_id=...` | Pedidos de un cliente, del más reciente al más viejo |
| GET | `/pedidos/{id}` | Obtiene un pedido |
| GET | `/salud` | Verifica que la API llega a Mongo |

Ejemplo de pedido (los ids salen de `GET /productos` y de la colección `clientes`):

```json
{
  "cliente_id": "a31c06bd463e3923bc1aadbd",
  "metodo_pago": "mercado_pago",
  "items": [{ "producto_id": "54f7cb6e1b0219423882bf84", "cantidad": 2 }]
}
```

## Consultas, índices y explain

Los scripts de `mongo/` están montados en el contenedor de Mongo en `/scripts`:

```bash
docker compose exec mongo mongosh ecommerce --quiet --file /scripts/consultas.js
```

```bash
docker compose exec mongo mongosh ecommerce --quiet --file /scripts/explain.js
```

Los resultados esperados están comentados en `consultas.js` (y la salida completa, en `consultas_salida.txt`). El análisis de los índices está en `explain.md`. Ambos suponen la base recién cargada: si creaste pedidos desde la API, corré `python scripts/cargar.py` antes.

## Notebook de análisis

```bash
jupyter lab analysis/analisis_ventas.ipynb
```

Ya está ejecutado y tiene las salidas guardadas, así que se puede leer en GitHub sin correrlo. Para volver a ejecutarlo, cargá antes la base (paso 4).

## Bajar el entorno

```bash
docker compose down
```

Los datos quedan en el volumen `mongo-data`. Para empezar de cero (borra la base):

```bash
docker compose down -v
```

## Conectarse a MongoDB

| Desde | URI |
|---|---|
| Tu máquina (scripts, notebook, pruebas, Compass) | `mongodb://localhost:27017/?directConnection=true` |
| Otro contenedor de Compose (la API) | `mongodb://mongo:27017/?replicaSet=rs0` |

Desde tu máquina hace falta `directConnection=true`: el replica set anuncia su único miembro como `mongo:27017`, un nombre que solo existe dentro de la red de Docker. Sin ese parámetro el driver intenta conectarse a `mongo` y falla.

Mongo corre sin usuario ni contraseña y solo escucha en `127.0.0.1`, así que no hay credenciales que compartir.

## Datos

- `data/raw/` tiene los JSON originales de [DummyJSON](https://dummyjson.com). `users.json` incluye campos como `password`, `ssn` o `bank`: son **datos ficticios** del dataset, no secretos reales, y se descartan al transformar los datos.
- `data/seed/` tiene los documentos finales, generados con `python scripts/transformar.py`. Es reproducible (semilla fija): siempre da los mismos archivos. Ya están versionados, así que para cargar la base no hace falta volver a generarlos.
