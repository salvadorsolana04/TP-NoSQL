# Contexto para Claude Code · TP Integrador NoSQL (MongoDB) · BDA · UCC

## Qué es este proyecto
TP integrador de **Base de Datos Aplicada** (UCC). El equipo son Justo Solana Allende, Salvador Solana Allende y Agustín Rodríguez Richard.
Se construye un **e-commerce** sobre **MongoDB**: catálogo de productos con atributos variables, clientes y pedidos que descuentan stock. Hay que entregar una API con capa de repositorios, consultas y agregaciones, índices con `explain`, un caso de consistencia con transacción, un notebook de análisis y Docker Compose.
**Hay una sola entrega final** (no hay entregas parciales, aunque la consigna original las mencione).

- Consigna: `docs/Consigna_Proyecto_NoSQL_MongoDB.pdf` (si no está, pedírsela a Salvador)
- **Diseño acordado: `docs/01_diseno_modelo_documental.md`**. Es la fuente de verdad del modelo. No cambiar colecciones ni campos sin avisar y actualizar ese documento.

## Modo de trabajo (IMPORTANTE)
Salvador quiere **aprender**, no que le resuelvan el TP. Cada integrante tiene que poder explicar en la defensa individual el modelo, una consulta, un índice y el repositorio.
- Antes de escribir cada parte, explicar brevemente **qué se va a hacer y por qué**, y hacer 1 o 2 preguntas guía. Para las consultas y los índices, dejar que él proponga primero.
- Si pide explícitamente "hacelo vos", hacerlo, pero **explicar las decisiones** y cerrar con: *"Si el profe te pregunta esto, ¿cómo lo explicarías?"*
- Comentar el código en español, con foco en el porqué y no en el qué.
- Cambios chicos y verificables, uno por vez. No generar todo el proyecto de una.

## Stack
- **MongoDB 7** en Docker, como **replica set de un nodo** (`--replSet rs0`), porque las transacciones lo requieren.
- **Python 3.12**, **FastAPI**, **PyMongo** (síncrono, más simple de explicar) y **Pydantic v2**.
- Análisis: **JupyterLab**, PyMongo, Pandas y Matplotlib.
- Docker Compose con servicios `mongo` (más un init del replica set) y `api`. **Dentro de los contenedores, la API se conecta a `mongo`, nunca a `localhost`.**
- Configuración por `.env`; se versiona solo `.env.example`, sin credenciales reales.

## Estructura propuesta
```
TP NoSQL/
├── CLAUDE.md
├── README.md                 # requisitos, levantar/bajar, cargar datos, correr pruebas
├── docker-compose.yml
├── .env.example
├── data/
│   ├── raw/                  # products.json, users.json, carts.json (DummyJSON, YA DESCARGADOS)
│   └── seed/                 # productos.json, clientes.json, pedidos.json (salida de transformar.py)
├── scripts/
│   ├── transformar.py        # raw → seed (random.seed(42), reproducible)
│   └── cargar.py             # reinicia la base y carga seed + índices; verifica conteos
├── mongo/
│   ├── consultas.js          # ≥10 consultas comentadas (objetivo, comando, resultado esperado)
│   ├── indices.js            # creación de índices
│   └── explain.md            # análisis de explain("executionStats")
├── api/
│   ├── main.py
│   ├── routers/              # HTTP: /productos (CRUD), /pedidos (crear/cancelar)
│   ├── services/             # lógica de negocio (pedido + transacción)
│   ├── repositories/         # ÚNICO lugar que toca MongoDB
│   ├── schemas/              # modelos Pydantic (validación)
│   └── db.py                 # cliente Mongo desde variables de entorno
├── tests/                    # pruebas de endpoints y del caso de consistencia
├── analysis/
│   └── analisis_ventas.ipynb # ≥3 indicadores, ≥2 gráficos, interpretación y conclusión
└── docs/
    ├── consigna.pdf
    ├── 01_diseno_modelo_documental.md
    └── informe_tecnico.md
```

## Estado actual (28/10/2026)
- [x] Dominio elegido: e-commerce
- [x] Datos crudos descargados en `data/raw/` (194 productos, 208 usuarios, 208 carritos, verificados: todos los ids de los carritos existen)
- [x] Diseño documental en borrador (`docs/01_diseno_modelo_documental.md`), a cerrar en grupo el viernes
- [x] `git init` y `.gitignore` (`.env`, `__pycache__`, `.ipynb_checkpoints`, volumen de datos)
- [x] Docker Compose: mongo como replica set + volumen persistente (desde la Mac: `directConnection=true`)
- [ ] `scripts/transformar.py` y `scripts/cargar.py`
- [ ] 10 consultas (5.3): 2 de comparación, 1 lógica, 1 sobre anidados, 1 sobre arreglos, 1 con proyección + sort + limit, 2 con aggregate, 1 de agrupamiento estadístico, 1 libre (por ejemplo, `$lookup` de ventas por categoría)
- [ ] Índices + explain (5.5)
- [ ] API CRUD de `/productos` con repositorios, validación y códigos HTTP (5.4)
- [ ] Caso de consistencia: crear y cancelar pedido con transacción, y prueba de que ante un error no queda nada a medias (5.6)
- [ ] Notebook de análisis (5.7)
- [ ] README e informe técnico (7)

## Reglas
- No versionar secretos ni `.env`.
- Todo tiene que poder reproducirse desde cero con: `docker compose up -d` → `python scripts/cargar.py` → pruebas.
- Los conteos y números que vayan al informe se verifican corriendo el script, no a ojo.
