# TP Integrador NoSQL · E-commerce sobre MongoDB

Base de Datos Aplicada · UCC · Justo Solana Allende, Salvador Solana Allende, Agustín Rodríguez Richard

Diseño del modelo: [`docs/01_diseno_modelo_documental.md`](docs/01_diseno_modelo_documental.md)

## Requisitos

- Docker con Docker Compose v2
- Python 3.12 (para los scripts, las pruebas y el notebook)

## Puesta en marcha (después de clonar o de cada `git pull` que cambie `.env.example`)

1. Crear el archivo de configuración local a partir del ejemplo. **Sin este paso, Compose y los scripts no encuentran las variables.** El `.env` no se versiona; cada integrante tiene el suyo.

   ```bash
   cp .env.example .env
   ```

2. Levantar MongoDB. `--wait` espera a que el replica set esté iniciado y el nodo sea PRIMARY.

   ```bash
   docker compose up -d --wait
   ```

3. Verificar que el replica set quedó bien (tiene que decir `PRIMARY`):

   ```bash
   docker compose exec mongo mongosh --quiet --eval "rs.status().members[0].stateStr"
   ```

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
| La Mac/PC (scripts, notebook, pruebas, Compass) | `mongodb://localhost:27017/?directConnection=true` |
| Otro contenedor de Compose (la API) | `mongodb://mongo:27017/?replicaSet=rs0` |

Desde la máquina hace falta `directConnection=true`: el replica set anuncia su único miembro como `mongo:27017`, un nombre que solo existe dentro de la red de Docker. Sin ese parámetro el driver intenta conectarse a `mongo` y falla.

Mongo corre sin usuario ni contraseña y solo escucha en `127.0.0.1`, así que no hay credenciales que compartir.

## Datos

`data/raw/` tiene los JSON originales de [DummyJSON](https://dummyjson.com). `users.json` incluye campos como `password`, `ssn` o `bank`: son **datos ficticios** del dataset, no secretos reales, y se descartan al transformar los datos.

<!-- Pendiente: cargar datos (scripts/cargar.py), correr la API y las pruebas. -->
