"""Configuración de las pruebas.

Las pruebas usan una base aparte (ecommerce_test) para no tocar la que se usa en la demo.
Se carga una vez con el mismo seed y los mismos índices que la real, y se borra al final.
Requiere el compose levantado (docker compose up -d --wait).
"""
import os
import sys
import uuid
from pathlib import Path

# Antes de importar la API: api.db lee MONGO_DB en cada llamada y load_dotenv no pisa
# variables que ya existen, así que todo lo que corra en las pruebas apunta a esta base.
os.environ["MONGO_DB"] = "ecommerce_test"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.db import get_cliente, get_db  # noqa: E402
from api.main import app  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import cargar  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def base_de_prueba():
    errores = cargar.cargar(get_cliente(), "ecommerce_test")
    assert not errores, errores
    yield
    get_cliente().drop_database("ecommerce_test")


@pytest.fixture
def api() -> TestClient:
    return TestClient(app)


@pytest.fixture
def db():
    return get_db()


@pytest.fixture
def nuevo_producto(api):
    """Crea un producto propio de la prueba, con stock conocido. Cada prueba usa los suyos
    (sku al azar), así no dependen del orden en que corren ni de lo que hicieron las demás."""

    def crear(stock: int = 10, precio: float = 100.0, descuento_pct: float = 0, **extra) -> dict:
        datos = {"sku": f"TEST-{uuid.uuid4().hex[:10].upper()}", "titulo": "Producto de prueba",
                 "categoria": "test", "precio": precio, "descuento_pct": descuento_pct,
                 "stock": stock, **extra}
        respuesta = api.post("/productos", json=datos)
        assert respuesta.status_code == 201, respuesta.text
        return respuesta.json()

    return crear


@pytest.fixture
def un_cliente(db) -> dict:
    return db.clientes.find_one(sort=[("email", 1)])
