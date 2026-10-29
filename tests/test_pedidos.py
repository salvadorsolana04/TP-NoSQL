"""Pruebas del caso de consistencia (5.6): crear y cancelar pedidos con transacción.

La idea central es que, pase lo que pase en el medio, el stock y los pedidos quedan
coherentes: o se aplicó toda la operación o no se aplicó nada.
"""
from concurrent.futures import ThreadPoolExecutor

import pytest
from bson import ObjectId

from api.repositories.pedidos import PedidosRepositorio
from api.schemas.pedido import PedidoCrear
from api.services.errores import StockInsuficiente
from api.services.pedidos import PedidosServicio


def stock(db, producto: dict) -> int:
    return db.productos.find_one({"_id": ObjectId(producto["id"])})["stock"]


def pedido(cliente: dict, *items: tuple[dict, int]) -> dict:
    return {"cliente_id": str(cliente["_id"]), "metodo_pago": "mercado_pago",
            "items": [{"producto_id": p["id"], "cantidad": c} for p, c in items]}


def test_crear_pedido_descuenta_stock_y_calcula_totales(api, db, nuevo_producto, un_cliente):
    a = nuevo_producto(stock=10, precio=100, descuento_pct=10)
    b = nuevo_producto(stock=5, precio=50)
    ultimo_numero = db.contadores.find_one({"_id": "pedidos"})["ultimo"]

    respuesta = api.post("/pedidos", json=pedido(un_cliente, (a, 3), (b, 2)))

    assert respuesta.status_code == 201, respuesta.text
    creado = respuesta.json()
    assert stock(db, a) == 7 and stock(db, b) == 3
    assert creado["numero"] == ultimo_numero + 1
    assert creado["estado"] == "pendiente"
    assert [h["estado"] for h in creado["historial_estados"]] == ["pendiente"]
    assert creado["totales"] == {"bruto": 400.0, "descuento": 30.0, "total": 370.0}
    assert creado["cantidad_unidades"] == 5
    # Se copian los datos del cliente y del producto al momento de la compra
    assert creado["cliente"]["email"] == un_cliente["email"]
    assert creado["direccion_envio"] == un_cliente["direccion"]
    assert creado["items"][0]["precio_unitario"] == 100


def test_sin_stock_en_un_item_no_se_descuenta_ninguno(api, db, nuevo_producto, un_cliente):
    """El primer ítem se descuenta bien y el segundo falla: la transacción tiene que
    deshacer también el primero."""
    con_stock = nuevo_producto(stock=10)
    sin_stock = nuevo_producto(stock=1)
    pedidos_antes = db.pedidos.count_documents({})
    contador_antes = db.contadores.find_one({"_id": "pedidos"})["ultimo"]

    respuesta = api.post("/pedidos", json=pedido(un_cliente, (con_stock, 4), (sin_stock, 2)))

    assert respuesta.status_code == 409
    assert "stock insuficiente" in respuesta.json()["detail"]
    assert stock(db, con_stock) == 10  # el descuento del primer ítem se deshizo
    assert stock(db, sin_stock) == 1
    assert db.pedidos.count_documents({}) == pedidos_antes
    assert db.contadores.find_one({"_id": "pedidos"})["ultimo"] == contador_antes


def test_producto_inexistente_no_deja_nada_a_medias(api, db, nuevo_producto, un_cliente):
    existente = nuevo_producto(stock=10)
    inexistente = {"id": "0" * 24}
    respuesta = api.post("/pedidos", json=pedido(un_cliente, (existente, 1), (inexistente, 1)))
    assert respuesta.status_code == 404
    assert stock(db, existente) == 10


def test_falla_inesperada_despues_de_descontar_stock(db, nuevo_producto, un_cliente, monkeypatch):
    """Simula que se cae la inserción del pedido cuando el stock ya se descontó (el peor
    momento). Sin transacción quedaría stock perdido; con transacción no queda rastro."""
    a, b = nuevo_producto(stock=10), nuevo_producto(stock=10)
    pedidos_antes = db.pedidos.count_documents({})

    def insertar_que_falla(self, pedido, session):
        raise RuntimeError("falla simulada al insertar el pedido")

    monkeypatch.setattr(PedidosRepositorio, "insertar", insertar_que_falla)
    with pytest.raises(RuntimeError, match="falla simulada"):
        PedidosServicio(db).crear(PedidoCrear(**pedido(un_cliente, (a, 3), (b, 5))))

    assert stock(db, a) == 10 and stock(db, b) == 10
    assert db.pedidos.count_documents({}) == pedidos_antes


def test_cliente_inexistente_da_404(api, nuevo_producto):
    producto = nuevo_producto()
    respuesta = api.post("/pedidos", json=pedido({"_id": "0" * 24}, (producto, 1)))
    assert respuesta.status_code == 404


def test_validaciones_del_pedido_dan_422(api, nuevo_producto, un_cliente):
    p = nuevo_producto()
    base = pedido(un_cliente, (p, 1))
    invalidos = [
        {**base, "items": []},                                     # sin ítems
        {**base, "metodo_pago": "efectivo"},                       # método no admitido
        {**base, "items": [{"producto_id": p["id"], "cantidad": 0}]},
        {**base, "items": [{"producto_id": "abc", "cantidad": 1}]},
        pedido(un_cliente, (p, 1), (p, 2)),                        # producto repetido
    ]
    for datos in invalidos:
        assert api.post("/pedidos", json=datos).status_code == 422, datos


def test_cancelar_devuelve_stock(api, db, nuevo_producto, un_cliente):
    a, b = nuevo_producto(stock=10), nuevo_producto(stock=10)
    creado = api.post("/pedidos", json=pedido(un_cliente, (a, 3), (b, 4))).json()
    assert stock(db, a) == 7 and stock(db, b) == 6

    respuesta = api.post(f"/pedidos/{creado['id']}/cancelar")

    assert respuesta.status_code == 200
    cancelado = respuesta.json()
    assert cancelado["estado"] == "cancelado"
    assert [h["estado"] for h in cancelado["historial_estados"]] == ["pendiente", "cancelado"]
    assert stock(db, a) == 10 and stock(db, b) == 10

    # Cancelar dos veces no devuelve el stock dos veces
    assert api.post(f"/pedidos/{creado['id']}/cancelar").status_code == 409
    assert stock(db, a) == 10


def test_no_se_cancela_un_pedido_entregado(api, db):
    entregado = db.pedidos.find_one({"estado": "entregado"})
    respuesta = api.post(f"/pedidos/{entregado['_id']}/cancelar")
    assert respuesta.status_code == 409
    assert db.pedidos.find_one({"_id": entregado["_id"]})["estado"] == "entregado"


def test_pedidos_de_un_cliente_ordenados_por_fecha(api, db):
    # El cliente con más pedidos del seed
    top = next(db.pedidos.aggregate([{"$group": {"_id": "$cliente_id", "n": {"$sum": 1}}},
                                     {"$sort": {"n": -1, "_id": 1}}, {"$limit": 1}]))
    respuesta = api.get("/pedidos", params={"cliente_id": str(top["_id"])})
    assert respuesta.status_code == 200
    pedidos = respuesta.json()
    assert len(pedidos) == top["n"]
    fechas = [p["fecha"] for p in pedidos]
    assert fechas == sorted(fechas, reverse=True)


def test_compras_simultaneas_de_la_ultima_unidad(db, nuevo_producto, un_cliente):
    """Extensión opcional (pruebas de concurrencia): 5 clientes compran al mismo tiempo la
    única unidad que queda. Tiene que venderse exactamente una vez."""
    ultima = nuevo_producto(stock=1)
    datos = PedidoCrear(**pedido(un_cliente, (ultima, 1)))

    def comprar(_):
        try:
            PedidosServicio(db).crear(datos)
            return "vendido"
        except StockInsuficiente:
            return "sin stock"

    with ThreadPoolExecutor(max_workers=5) as pool:
        resultados = list(pool.map(comprar, range(5)))

    assert resultados.count("vendido") == 1
    assert resultados.count("sin stock") == 4
    assert stock(db, ultima) == 0
    assert db.pedidos.count_documents({"items.producto_id": ObjectId(ultima["id"])}) == 1
