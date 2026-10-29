# Contexto del proyecto (para personas y asistentes de IA)

> Este archivo es el contexto completo del repo. Lo leen automáticamente Codex y otros agentes (`AGENTS.md`); Claude Code lo importa desde `CLAUDE.md`. **Si sos una IA y te pasaron un archivo suelto de este repo, leé esto antes de proponer cambios.** Si sos integrante del grupo, también te sirve como resumen para la defensa.

## Qué es

TP integrador de **Base de Datos Aplicada** (UCC). Grupo: Justo Solana Allende, Salvador Solana Allende y Agustín Rodríguez Richard. **Hay una sola entrega final** (la consigna menciona entregas parciales, pero no aplican).

Un **e-commerce sobre MongoDB 7**: catálogo de productos con atributos variables por categoría, clientes y pedidos que descuentan stock con una transacción. Se entrega API con repositorios, consultas y agregaciones, índices con `explain`, un caso de consistencia, un notebook de análisis y Docker Compose.

- Consigna: [`docs/Consigna_Proyecto_NoSQL_MongoDB.pdf`](docs/Consigna_Proyecto_NoSQL_MongoDB.pdf)
- **Fuente de verdad del modelo:** [`docs/01_diseno_modelo_documental.md`](docs/01_diseno_modelo_documental.md). No cambiar colecciones ni campos sin avisar al grupo y actualizar ese documento.
- Resumen de todo lo hecho y sus resultados: [`docs/informe_tecnico.md`](docs/informe_tecnico.md)

## Cómo trabajar (importante para las IA)

Cada integrante tiene que poder explicar en la **defensa individual** el modelo, una consulta, un índice y el repositorio. Por eso:

- El objetivo es **aprender**, no que la IA resuelva el TP. Antes de escribir algo, explicá brevemente **qué** vas a hacer y **por qué**, y hacé 1 o 2 preguntas guía. Para consultas e índices, dejá que la persona proponga primero.
- Si te piden "hacelo vos", hacelo, pero explicá las decisiones y cerrá con: *"Si el profe te pregunta esto, ¿cómo lo explicarías?"*.
- Comentarios del código **en español**, sobre el **porqué** y no el qué. Mantené el estilo y la densidad de comentarios del código que ya existe.
- Cambios chicos y verificables, de a uno. Después de cambiar algo, corré las pruebas (ver "Verificar").
- Los números que van al informe se verifican **corriendo los scripts**, nunca a ojo.

## Estado (29/10/2026): todo lo obligatorio está hecho

| Parte de la consigna | Estado | Archivos |
|---|---|---|
| 5.1 Diseño | Hecho; las decisiones abiertas se tomaron (sección 9 del diseño), falta confirmarlas en grupo | `docs/01_diseno_modelo_documental.md` |
| 5.2 Carga | Hecho | `scripts/transformar.py`, `scripts/cargar.py`, `data/` |
| 5.3 Consultas | Hecho (10) | `mongo/consultas.js`, `mongo/consultas_salida.txt` |
| 5.4 API CRUD | Hecho | `api/` |
| 5.5 Índices + explain | Hecho | `mongo/indices.js`, `mongo/explain.js`, `mongo/explain.md` |
| 5.6 Consistencia | Hecho, con pruebas | `api/services/pedidos.py`, `tests/test_pedidos.py` |
| 5.7 Análisis | Hecho (ejecutado, con salidas) | `analysis/analisis_ventas.ipynb` |
| 5.8 Docker | Hecho | `docker-compose.yml`, `api/Dockerfile`, `.env.example` |
| 7 README + informe | Hecho | `README.md`, `docs/informe_tecnico.md` |

**Pendiente:** confirmar en grupo las decisiones de la sección 9 del diseño, repartir quién defiende qué y preparar la presentación. Extensiones opcionales no hechas: índice de texto, `$jsonSchema`.

## Mapa del repo

```
api/                       API FastAPI (entidad principal: productos)
  main.py                  app, routers y traducción de errores de negocio a HTTP (404/409/503)
  db.py                    MongoClient desde variables de entorno + ejecutar_en_transaccion()
  schemas/                 Pydantic: validación de entrada (extra="forbid") y forma de las salidas
  repositories/            ÚNICO lugar que arma consultas a Mongo (productos, clientes, pedidos)
  services/                reglas de negocio; pedidos.py tiene las transacciones (crear/cancelar)
  routers/                 solo HTTP: parámetros, códigos de estado
  Dockerfile               imagen python:3.12-slim; se construye desde la raíz
scripts/
  transformar.py           data/raw → data/seed (random.Random(42): reproducible). No hace falta correrlo: el seed está versionado
  cargar.py                borra la base, carga el seed, verifica conteos y referencias, inicia el contador y crea índices
mongo/                     montado en el contenedor como /scripts (solo lectura)
  indices.js               definición única de los índices (cargar.py la ejecuta)
  consultas.js             10 consultas con objetivo, comando y resultado esperado
  explain.js / explain.md  medición con explain("executionStats") y su interpretación
tests/                     pytest contra la base ecommerce_test (se crea y se borra sola)
analysis/                  notebook de ventas (indicadores, 3 gráficos, conclusiones)
data/raw/                  JSON originales de DummyJSON (users.json trae passwords FICTICIOS, se descartan)
data/seed/                 documentos finales en Extended JSON ($oid, $date)
docs/                      consigna, diseño, informe técnico
```

## Decisiones y trampas que hay que conocer

- **Replica set de un nodo** (`--replSet rs0`): las transacciones lo requieren. El servicio `mongo-init` del compose hace `rs.initiate()` una vez (es idempotente).
- **Conexión desde la máquina:** `mongodb://localhost:27017/?directConnection=true`. Sin `directConnection` falla, porque el replica set anuncia el miembro como `mongo:27017`, que solo existe dentro de Docker. **Dentro de Docker**, la API usa `mongodb://mongo:27017/?replicaSet=rs0`, nunca `localhost`.
- **Sin usuario ni contraseña** en Mongo: solo escucha en `127.0.0.1`. No versionar `.env` (solo `.env.example`).
- **Baja lógica de productos:** `DELETE` pone `activo: false`. Los productos del seed no tienen el campo (ausente = activo), por eso los filtros usan `{"activo": {"$ne": False}}`. Un sku dado de baja no se puede reutilizar.
- **Campos opcionales ausentes, no `null`:** por ejemplo, `marca` falta en 92 productos. Al crear se usa `model_dump(exclude_none=True)`. En un PATCH, enviar `null` elimina el campo (`$unset`).
- **Pedidos:** los ítems copian sku, título y precio (quedan congelados a la fecha de compra) y referencian `producto_id`. `subtotal = precio * cantidad * (1 - descuento_pct/100)`, igual en `transformar.py` y en la API.
- **Numeración de pedidos:** colección técnica `contadores` (`{_id: "pedidos", ultimo: N}`), con `$inc` dentro de la transacción. `cargar.py` la inicializa con 1208.
- **Consistencia:** la condición `stock >= cantidad` y el `$inc` van en una sola operación atómica (evita la sobreventa); la transacción evita que quede algo a medias. Con la transacción desactivada fallan 3 pruebas de `test_pedidos.py`: así se comprobó que hacen falta las dos cosas.
- **Reseñas:** update con pipeline (atómico en un documento, sin transacción). El review va dentro de `$literal` para que un comentario que empiece con `$` no se interprete como campo.
- **Fecha "hoy" fija** en los datos: 28/10/2026 (`transformar.py`). Los estados de los pedidos dependen de ella.
- **`cantidad_minima`** es informativa: la API no la valida.
- Si en tu máquina el puerto 8000 está ocupado, cambiá `API_PORT` en tu `.env`.

## Verificar que todo funciona

```bash
cp .env.example .env                       # si no existe
docker compose up -d --wait --build        # mongo + replica set + api
pip install -r requirements-dev.txt        # en un venv
python scripts/cargar.py                   # debe terminar con "verificación OK"
pytest                                     # 24 pruebas
docker compose exec mongo mongosh ecommerce --quiet --file /scripts/consultas.js
```

Las consultas, el explain y el notebook suponen la base **recién cargada**: si se crearon pedidos desde la API, corré `cargar.py` antes de comparar resultados.

## Stack

MongoDB 7 · Python 3.12 · FastAPI · PyMongo (síncrono) · Pydantic v2 · pytest · JupyterLab, Pandas y Matplotlib · Docker Compose. Dependencias: `requirements.txt` (API y scripts, lo que va en la imagen) y `requirements-dev.txt` (más pruebas y notebook).
