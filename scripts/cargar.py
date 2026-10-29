"""Reinicia la base, carga los documentos de data/seed, verifica conteos y referencias y crea los índices.

Uso: python scripts/cargar.py   (con Mongo levantado: docker compose up -d --wait)

Se puede correr todas las veces que haga falta: siempre deja la base en el mismo estado,
porque borra todo antes de cargar y el seed tiene los _id fijos.
"""
import os
import subprocess
import sys
from pathlib import Path

from bson import json_util
from dotenv import load_dotenv
from pymongo import MongoClient

RAIZ = Path(__file__).resolve().parent.parent
SEED = RAIZ / "data" / "seed"

# Clientes y productos antes que pedidos: Mongo no exige el orden (no hay claves foráneas),
# pero así la base nunca tiene pedidos que apunten a algo que todavía no existe.
COLECCIONES = ["clientes", "productos", "pedidos"]


def leer_seed(nombre: str) -> list[dict]:
    # json_util.loads, no json.load: convierte {"$oid": ...} y {"$date": ...} en
    # ObjectId y datetime. Si no, se guardarían como subdocumentos y las referencias
    # y los filtros por fecha dejarían de funcionar.
    with open(SEED / f"{nombre}.json", encoding="utf-8") as f:
        return json_util.loads(f.read())


def verificar_referencias(db) -> list[str]:
    """Mongo no valida referencias entre colecciones, así que lo chequeamos nosotros."""
    errores = []

    ids_clientes = set(db.clientes.distinct("_id"))
    clientes_faltantes = set(db.pedidos.distinct("cliente_id")) - ids_clientes
    if clientes_faltantes:
        errores.append(f"{len(clientes_faltantes)} cliente_id de pedidos no existen en clientes")

    # distinct sobre "items.producto_id" recorre el arreglo de ítems de cada pedido.
    ids_productos = set(db.productos.distinct("_id"))
    productos_faltantes = set(db.pedidos.distinct("items.producto_id")) - ids_productos
    if productos_faltantes:
        errores.append(f"{len(productos_faltantes)} producto_id de ítems no existen en productos")

    return errores


def crear_indices(nombre_db: str) -> list[str]:
    """Corre mongo/indices.js con el mongosh del contenedor.

    El .js es la única definición de los índices (es el entregable de 5.5); ejecutarlo
    desde acá evita tener una copia en Python que se desincronice. Requiere el compose
    levantado, que monta mongo/ en /scripts.
    """
    resultado = subprocess.run(
        ["docker", "compose", "exec", "-T", "mongo",
         "mongosh", nombre_db, "--quiet", "--file", "/scripts/indices.js"],
        cwd=RAIZ, capture_output=True, text=True,
    )
    print(resultado.stdout.rstrip())
    if resultado.returncode != 0:
        return [f"no se pudieron crear los índices: {resultado.stderr.strip()}"]
    return []


def inicializar_contador(db) -> None:
    """La API numera los pedidos nuevos con un contador atómico (ver
    api/repositories/pedidos.py). Arranca en el último número del seed para seguir la
    secuencia sin repetir."""
    ultimo = db.pedidos.find_one(sort=[("numero", -1)], projection={"numero": 1})
    db.contadores.insert_one({"_id": "pedidos", "ultimo": ultimo["numero"] if ultimo else 1000})


def cargar(cliente: MongoClient, nombre_db: str) -> list[str]:
    """Reinicia la base nombre_db y la deja lista. Devuelve la lista de errores (vacía si
    todo salió bien). Las pruebas la usan para armar su propia base."""
    db = cliente[nombre_db]

    # Borrar la base entera (y no solo vaciar colecciones) también elimina índices y
    # colecciones viejas: la carga parte siempre del mismo estado.
    cliente.drop_database(nombre_db)
    print(f"base '{nombre_db}' reiniciada")

    errores = []
    for nombre in COLECCIONES:
        documentos = leer_seed(nombre)
        db[nombre].insert_many(documentos)
        en_base = db[nombre].count_documents({})
        print(f"{nombre}: {en_base} documentos (seed: {len(documentos)})")
        if en_base != len(documentos):
            errores.append(f"{nombre}: se esperaban {len(documentos)} y hay {en_base}")

    errores += verificar_referencias(db)
    inicializar_contador(db)

    # Los índices se crean después de cargar: construirlos una vez sobre los datos es más
    # barato que actualizarlos documento por documento durante el insert_many.
    errores += crear_indices(nombre_db)
    return errores


def main() -> None:
    load_dotenv(RAIZ / ".env")
    # Los valores por defecto son los de .env.example, para que funcione aunque falte el .env.
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
    nombre_db = os.getenv("MONGO_DB", "ecommerce")

    errores = cargar(MongoClient(uri, serverSelectionTimeoutMS=5000), nombre_db)

    if errores:
        print("\nERRORES:")
        for error in errores:
            print(f"  - {error}")
        # Código de salida distinto de 0 para que una prueba o un script lo detecte.
        sys.exit(1)
    print("\nverificación OK: conteos y referencias correctos")


if __name__ == "__main__":
    main()
