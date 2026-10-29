"""Conexión a MongoDB. La configuración sale de variables de entorno:

- En la Mac se leen del .env (MONGO_URI con directConnection=true).
- En Docker las define el compose (MONGO_URI=mongodb://mongo:27017/?replicaSet=rs0).
"""
import os
from functools import lru_cache
from typing import Callable, TypeVar

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.client_session import ClientSession
from pymongo.database import Database

# No pisa variables que ya existan: en Docker y en las pruebas manda el entorno, no el .env.
load_dotenv()

T = TypeVar("T")


@lru_cache
def get_cliente() -> MongoClient:
    # Un solo MongoClient para toda la app: maneja su propio pool de conexiones y crear
    # uno por request sería lento. tz_aware=True devuelve las fechas con zona horaria (UTC).
    return MongoClient(
        os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true"),
        serverSelectionTimeoutMS=5000,
        tz_aware=True,
    )


def get_db() -> Database:
    # Se lee en cada llamada (no se cachea) para que las pruebas puedan usar otra base.
    return get_cliente()[os.getenv("MONGO_DB", "ecommerce")]


def ejecutar_en_transaccion(operacion: Callable[[ClientSession], T]) -> T:
    """Ejecuta operacion(session) dentro de una transacción multidocumento.

    with_transaction hace commit si la función termina bien y abort si lanza una excepción,
    que después se propaga. Además reintenta sola ante errores transitorios (por ejemplo,
    un conflicto de escritura con otra transacción que tocó el mismo documento).
    Requiere replica set: con un Mongo standalone, start_transaction falla.
    """
    with get_cliente().start_session() as session:
        return session.with_transaction(operacion)
