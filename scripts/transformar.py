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


# ---------------------------------------------------------------- productos

def parsear_fecha(iso: str) -> datetime:
    # DummyJSON usa "2025-04-30T09:41:02.053Z"; desde Python 3.11 fromisoformat acepta la Z.
    return datetime.fromisoformat(iso)


def atributos_electronica(categoria: str, marca: str | None) -> dict:
    # Valores tomados de listas realistas por tipo de equipo, para que una consulta
    # como {"atributos.ram_gb": {"$gte": 8}} devuelva un subconjunto con sentido.
    ram, almacenamiento, pantalla = {
        "smartphones": ([2, 3, 4, 6, 8, 12], [32, 64, 128, 256, 512], (4.7, 6.9)),
        "tablets": ([3, 4, 6, 8], [64, 128, 256], (8.0, 12.9)),
        "laptops": ([8, 16, 32], [256, 512, 1024], (13.0, 16.0)),
    }[categoria]
    if marca == "Apple":
        so = {"smartphones": "iOS", "tablets": "iPadOS", "laptops": "macOS"}[categoria]
    else:
        so = "Windows" if categoria == "laptops" else "Android"
    return {
        "ram_gb": rng.choice(ram),
        "almacenamiento_gb": rng.choice(almacenamiento),
        "pantalla_pulgadas": round(rng.uniform(*pantalla), 1),
        "sistema_operativo": so,
    }


def atributos_vehiculo(categoria: str) -> dict:
    if categoria == "motorcycle":
        return {"cilindrada_cc": rng.choice([125, 250, 300, 650, 1000]),
                "combustible": "nafta", "anio": rng.randint(2018, 2026)}
    combustible = rng.choice(["nafta", "diesel", "electrico"])
    atributos = {"combustible": combustible, "anio": rng.randint(2018, 2026)}
    # Un eléctrico no tiene cilindrada: el campo se omite en lugar de poner 0 o null.
    # Así el esquema varía incluso dentro de la misma categoría.
    if combustible != "electrico":
        atributos["cilindrada_cc"] = rng.choice([1000, 1400, 1600, 2000, 3000])
    return atributos


# Vencimientos alrededor de "hoy" (oct-2026): algunos productos ya vencieron,
# lo que permite una consulta de comparación con fechas.
VENC_DESDE = datetime(2026, 9, 1, tzinfo=timezone.utc)
VENC_HASTA = datetime(2027, 12, 31, tzinfo=timezone.utc)


def generar_atributos(categoria: str, marca: str | None) -> dict | None:
    """Atributos variables por categoría (tabla de la sección 5.1 del diseño).
    Devuelve None para las categorías sin atributos: el campo no se escribe."""
    if categoria in ("smartphones", "tablets", "laptops"):
        return atributos_electronica(categoria, marca)
    if categoria in ("mens-shirts", "tops", "womens-dresses"):
        return {
            # sorted() para que el arreglo quede en orden de talle y no al azar
            "talles": sorted(rng.sample(["XS", "S", "M", "L", "XL"], rng.randint(2, 5)),
                             key=["XS", "S", "M", "L", "XL"].index),
            "material": rng.choice(["algodon", "poliester", "lino", "seda"]),
            "color": rng.choice(["negro", "blanco", "azul", "rojo", "verde", "gris"]),
        }
    if categoria in ("mens-shoes", "womens-shoes"):
        inicio = rng.randint(35, 40)
        return {"talles": list(range(inicio, inicio + rng.randint(3, 6))),
                "material": rng.choice(["cuero", "sintetico", "tela"])}
    if categoria == "groceries":
        return {"vencimiento": fecha_al_azar(VENC_DESDE, VENC_HASTA),
                "peso_neto_g": rng.choice([250, 500, 1000, 2000]),
                "apto_celiacos": rng.random() < 0.4}
    if categoria in ("fragrances", "beauty", "skin-care"):
        return {"volumen_ml": rng.choice([30, 50, 100, 150, 200])}
    if categoria in ("furniture", "home-decoration"):
        return {"material": rng.choice(["madera", "metal", "vidrio", "tela"]),
                "requiere_armado": rng.random() < 0.5}
    if categoria in ("motorcycle", "vehicle"):
        return atributos_vehiculo(categoria)
    if categoria in ("mens-watches", "womens-watches"):
        return {"resistencia_agua_m": rng.choice([30, 50, 100, 200]),
                "tipo_movimiento": rng.choice(["cuarzo", "automatico", "digital"])}
    return None


def transformar_productos(products: list[dict]) -> tuple[list[dict], dict[int, dict]]:
    """Devuelve los productos y un mapa id de DummyJSON -> documento, para armar los pedidos
    (el pedido copia sku, título y precio del producto)."""
    productos = []
    por_id = {}
    for p in products:
        reviews = [{
            "rating": r["rating"],
            "comentario": r["comment"],
            "fecha": parsear_fecha(r["date"]),
            "autor": r["reviewerName"],
            "email": r["reviewerEmail"],
        } for r in p["reviews"]]
        doc = {
            "_id": nuevo_object_id(),
            # El sku del dataset ya es único (194/194), así que se conserva.
            "sku": p["sku"],
            "titulo": p["title"],
            "descripcion": p["description"],
            "categoria": p["category"],
        }
        # Campo ausente y no null: en 92 productos la marca no existe, y así se consulta
        # con {"marca": {"$exists": false}}.
        if p.get("brand"):
            doc["marca"] = p["brand"]
        doc |= {
            "precio": p["price"],
            "descuento_pct": p["discountPercentage"],
            "stock": p["stock"],
            "etiquetas": p["tags"],
            "dimensiones": {"ancho": p["dimensions"]["width"],
                            "alto": p["dimensions"]["height"],
                            "profundidad": p["dimensions"]["depth"]},
            "peso": p["weight"],
        }
        atributos = generar_atributos(p["category"], p.get("brand"))
        if atributos is not None:
            doc["atributos"] = atributos
        doc |= {
            "garantia": p["warrantyInformation"],
            "politica_devolucion": p["returnPolicy"],
            "envio": p["shippingInformation"],
            "cantidad_minima": p["minimumOrderQuantity"],
            # Se recalcula: el "rating" del dataset no coincide con sus propias reviews.
            "rating_promedio": round(sum(r["rating"] for r in reviews) / len(reviews), 2) if reviews else None,
            "reviews": reviews,
            "imagenes": p["images"],
            "creado_en": parsear_fecha(p["meta"]["createdAt"]),
            "actualizado_en": parsear_fecha(p["meta"]["updatedAt"]),
        }
        productos.append(doc)
        por_id[p["id"]] = doc
    return productos, por_id


# ---------------------------------------------------------------- pedidos

PEDIDOS_DESDE = datetime(2025, 11, 1, tzinfo=timezone.utc)
# "Hoy" es fijo y no datetime.now(): si no, el estado de los pedidos cambiaría
# según el día en que se corra el script y se perdería la reproducibilidad.
HOY = datetime(2026, 10, 28, 23, 59, tzinfo=timezone.utc)

METODOS_PAGO = ["tarjeta_credito", "tarjeta_debito", "mercado_pago", "transferencia"]
PROB_CANCELADO = 0.12


def generar_historial(fecha: datetime) -> list[dict]:
    """Arma la secuencia pendiente -> pagado -> enviado -> entregado con demoras realistas
    y la corta en HOY. Así el estado final sale solo: un pedido de hace meses queda
    entregado y uno de ayer puede seguir pendiente, sin elegir el estado por separado."""
    pasos = [
        ("pendiente", fecha),
        ("pagado", fecha + timedelta(minutes=rng.randint(2, 120))),
    ]
    pasos.append(("enviado", pasos[-1][1] + timedelta(hours=rng.randint(12, 72))))
    pasos.append(("entregado", pasos[-1][1] + timedelta(hours=rng.randint(24, 144))))
    historial = [{"estado": e, "fecha": f} for e, f in pasos if f <= HOY]

    # Según el diseño solo se cancela desde pendiente o pagado. Se cancela
    # desde el último de esos dos estados que haya llegado a ocurrir.
    if rng.random() < PROB_CANCELADO:
        historial = historial[:2]
        cancelacion = historial[-1]["fecha"] + timedelta(hours=rng.randint(1, 48))
        if cancelacion <= HOY:
            historial.append({"estado": "cancelado", "fecha": cancelacion})
    return historial


def asignar_clientes(clientes: list[dict], cantidad: int) -> list[dict]:
    """Reasigna los carritos a clientes con pesos desiguales: en DummyJSON hay un carrito
    por usuario, y así no se podría medir recompra ni encontrar clientes sin pedidos."""
    # Un 25% de los clientes no compra nunca (peso 0). El resto tiene peso 1, 2 o 4,
    # así aparecen unos pocos clientes frecuentes, como en una tienda real.
    pesos = [0 if rng.random() < 0.25 else rng.choice([1, 1, 1, 2, 4]) for _ in clientes]
    compradores = [c for c, p in zip(clientes, pesos) if p > 0]
    # Primero un pedido para cada comprador; si se sortearan todos por peso, con solo
    # 208 pedidos la mitad de los clientes quedaba sin comprar por puro azar.
    extra = rng.choices(clientes, weights=pesos, k=cantidad - len(compradores))
    asignados = compradores + extra
    rng.shuffle(asignados)  # para que los primeros carritos no vayan siempre a compradores únicos
    return asignados


def armar_items(productos_carrito: list[dict], productos_por_id: dict[int, dict]) -> list[dict]:
    # 12 carritos repiten un producto en dos líneas: se fusionan en un solo ítem
    # para que la transacción descuente el stock una vez por producto.
    cantidades: dict[int, int] = {}
    for linea in productos_carrito:
        cantidades[linea["id"]] = cantidades.get(linea["id"], 0) + linea["quantity"]

    items = []
    for id_raw, cantidad in cantidades.items():
        prod = productos_por_id[id_raw]
        # Se copian sku, título y precio para congelarlos a la fecha de compra
        # (sección 6 del diseño); producto_id queda para devolver stock y cruzar.
        items.append({
            "producto_id": prod["_id"],
            "sku": prod["sku"],
            "titulo": prod["titulo"],
            "precio_unitario": prod["precio"],
            "descuento_pct": prod["descuento_pct"],
            "cantidad": cantidad,
            "subtotal": round(prod["precio"] * cantidad * (1 - prod["descuento_pct"] / 100), 2),
        })
    return items


def transformar_pedidos(carts: list[dict], clientes: list[dict],
                        productos_por_id: dict[int, dict]) -> list[dict]:
    pedidos = []
    for cart, cliente in zip(carts, asignar_clientes(clientes, len(carts))):
        items = armar_items(cart["products"], productos_por_id)
        bruto = round(sum(i["precio_unitario"] * i["cantidad"] for i in items), 2)
        total = round(sum(i["subtotal"] for i in items), 2)
        historial = generar_historial(fecha_al_azar(PEDIDOS_DESDE, HOY))
        pedidos.append({
            "_id": nuevo_object_id(),
            "cliente_id": cliente["_id"],
            # Copia de nombre y email para mostrar el pedido sin hacer un $lookup a clientes
            "cliente": {"nombre": f'{cliente["nombre"]} {cliente["apellido"]}',
                        "email": cliente["email"]},
            "fecha": historial[0]["fecha"],
            "estado": historial[-1]["estado"],
            "historial_estados": historial,
            "metodo_pago": rng.choices(METODOS_PAGO, weights=[45, 20, 25, 10])[0],
            # Copia (no referencia): el envío va a la dirección vigente al comprar
            "direccion_envio": dict(cliente["direccion"]),
            "items": items,
            # descuento por diferencia para que siempre se cumpla bruto - descuento == total
            "totales": {"bruto": bruto, "descuento": round(bruto - total, 2), "total": total},
            "cantidad_unidades": sum(i["cantidad"] for i in items),
        })

    # El número de pedido es correlativo en orden cronológico, como en un sistema real
    # donde se asigna al crearse. Se ordena recién al final para no alterar el rng.
    # Se arma un dict nuevo para que "numero" quede segundo, como en el diseño.
    pedidos.sort(key=lambda p: p["fecha"])
    return [{"_id": p.pop("_id"), "numero": n, **p} for n, p in enumerate(pedidos, start=1001)]


def main() -> None:
    # El orden importa: todos usan el mismo rng, así que clientes va primero
    # para que agregar productos no cambie los clientes ya generados.
    clientes, _ids_clientes = transformar_clientes(leer_raw("users"))
    escribir_seed("clientes", clientes)
    print(f"clientes: {len(clientes)}")

    productos, productos_por_id = transformar_productos(leer_raw("products"))
    escribir_seed("productos", productos)
    print(f"productos: {len(productos)}")

    pedidos = transformar_pedidos(leer_raw("carts"), clientes, productos_por_id)
    escribir_seed("pedidos", pedidos)
    print(f"pedidos: {len(pedidos)}")


if __name__ == "__main__":
    main()
