"""Transforma los JSON crudos de DummyJSON (data/raw) en los documentos finales (data/seed).

Uso: python scripts/transformar.py

Es reproducible: todo lo que se genera al azar sale de un único random.Random(42),
así que dos corridas producen exactamente los mismos archivos.
"""
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bson import ObjectId, json_util

RAIZ = Path(__file__).resolve().parent.parent
RAW = RAIZ / "data" / "raw"
SEED = RAIZ / "data" / "seed"

# Un generador propio en vez de random.seed() global: si alguna librería usa random,
# no nos corre la secuencia y los datos siguen siendo los mismos.
rng = random.Random(42)


def nuevo_object_id() -> ObjectId:
    # ObjectId() usa la hora actual, entonces cambiaría en cada corrida.
    # Armarlo con 12 bytes del rng lo hace reproducible, y como los ids quedan fijos,
    # los pedidos pueden referenciar a clientes y productos desde el seed.
    return ObjectId(bytes(rng.getrandbits(8) for _ in range(12)))


def fecha_al_azar(desde: datetime, hasta: datetime) -> datetime:
    segundos = int((hasta - desde).total_seconds())
    return desde + timedelta(seconds=rng.randint(0, segundos))


def leer_raw(nombre: str) -> list[dict]:
    with open(RAW / f"{nombre}.json", encoding="utf-8") as f:
        return json.load(f)[nombre]


def escribir_seed(nombre: str, documentos: list[dict]) -> None:
    # Extended JSON ({"$oid": ...}, {"$date": ...}) para que al cargar se recuperen
    # ObjectId y fechas reales; con json.dump quedarían como strings.
    SEED.mkdir(parents=True, exist_ok=True)
    with open(SEED / f"{nombre}.json", "w", encoding="utf-8") as f:
        f.write(json_util.dumps(documentos, indent=2, ensure_ascii=False,
                                json_options=json_util.RELAXED_JSON_OPTIONS))


# ---------------------------------------------------------------- clientes

# Las altas son anteriores al primer pedido (nov-2025) para que ningún cliente
# compre antes de existir.
ALTA_DESDE = datetime(2024, 1, 1, tzinfo=timezone.utc)
ALTA_HASTA = datetime(2025, 10, 31, tzinfo=timezone.utc)


def transformar_clientes(users: list[dict]) -> tuple[list[dict], dict[int, ObjectId]]:
    """Devuelve los clientes y un mapa id de DummyJSON -> _id, para armar los pedidos."""
    clientes = []
    ids = {}
    for u in users:
        _id = nuevo_object_id()
        ids[u["id"]] = _id
        dir_ = u["address"]
        # Se copian solo los campos del diseño (minimización de datos): password, ssn,
        # bank, crypto, etc. no se leen nunca. Tampoco las coordenadas, que son aleatorias.
        clientes.append({
            "_id": _id,
            "nombre": u["firstName"],
            "apellido": u["lastName"],
            "email": u["email"],
            "telefono": u.get("phone"),
            # DummyJSON trae "1996-5-30" (sin ceros); strptime lo acepta igual.
            "fecha_nacimiento": datetime.strptime(u["birthDate"], "%Y-%m-%d").replace(tzinfo=timezone.utc),
            "genero": u["gender"],
            "direccion": {
                "calle": dir_["address"],
                "ciudad": dir_["city"],
                "estado": dir_["state"],
                "codigo_postal": dir_["postalCode"],
                "pais": dir_["country"],
            },
            "fecha_alta": fecha_al_azar(ALTA_DESDE, ALTA_HASTA),
        })
    return clientes, ids


def main() -> None:
    clientes, _ids_clientes = transformar_clientes(leer_raw("users"))
    escribir_seed("clientes", clientes)
    print(f"clientes: {len(clientes)}")


if __name__ == "__main__":
    main()
