# Notas de trabajo del equipo

Contexto interno para quien modifique el proyecto: estado, decisiones tomadas y cómo verificar que todo funciona. La puesta en marcha está en el [README](README.md); el modelo, en [`docs/01_diseno_modelo_documental.md`](docs/01_diseno_modelo_documental.md), que es la referencia: si se cambia una colección o un campo, se actualiza ese documento y se avisa al grupo.

## Estado

Todo lo obligatorio de la consigna está hecho (ver la tabla del README). Extensiones opcionales no hechas: índice de texto y `$jsonSchema`.

## Convenciones

- Comentarios en español, explicando el porqué y no el qué.
- Cambios chicos y verificables; después de cada cambio, correr las pruebas.
- Los números del informe se obtienen corriendo los scripts, no a mano.
- No versionar `.env` (solo `.env.example`).

## Decisiones y detalles a tener en cuenta

- **Replica set de un nodo** (`--replSet rs0`), porque las transacciones lo requieren. `mongo-init` hace `rs.initiate()` una sola vez.
- **Conexión:** desde la máquina, `mongodb://localhost:27017/?directConnection=true` (el miembro se anuncia como `mongo:27017`, que solo existe dentro de Docker). Desde la API en Docker, `mongodb://mongo:27017/?replicaSet=rs0`.
- **Baja lógica de productos** (`activo: false`). Los productos del seed no tienen el campo, por eso los filtros usan `{"activo": {"$ne": False}}`.
- **Opcionales ausentes, no `null`** (por ejemplo, `marca`). En un PATCH, enviar `null` elimina el campo.
- **Pedidos:** los ítems copian sku, título y precio y referencian `producto_id`. `subtotal = precio * cantidad * (1 - descuento_pct/100)`, igual en `transformar.py` y en la API.
- **Numeración de pedidos:** colección `contadores` con `$inc` dentro de la transacción; `cargar.py` la inicializa en 1208.
- **Consistencia:** `stock >= cantidad` + `$inc` en una sola operación evita la sobreventa; la transacción evita que el pedido quede a medias.
- **Reseñas:** update con pipeline sobre un documento (atómico, sin transacción).
- **Fecha "hoy" fija** en los datos (28/10/2026); los estados de los pedidos dependen de ella.
- Si el puerto 8000 está ocupado, cambiar `API_PORT` en el `.env`.

## Verificar

```bash
docker compose up -d --wait --build
python scripts/cargar.py      # tiene que terminar con "verificación OK"
pytest                        # 24 pruebas
```

Las consultas, el explain y el notebook suponen la base recién cargada.
