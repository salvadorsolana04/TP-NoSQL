"""Caso de consistencia (5.6): crear y cancelar pedidos con una transacción multidocumento.

Crear un pedido toca N productos (descontar stock) y 1 pedido (insertarlo). Si se hiciera
en operaciones sueltas y algo fallara a mitad de camino, quedaría stock descontado sin
pedido, o un pedido de algo que no había. Dentro de la transacción, o se aplica todo o
no se aplica nada.
"""
from datetime import datetime, timezone

from bson import ObjectId
from pymongo.client_session import ClientSession
from pymongo.database import Database

from api.db import ejecutar_en_transaccion
from api.repositories.clientes import ClientesRepositorio
from api.repositories.pedidos import CANCELABLES, PedidosRepositorio
from api.repositories.productos import ProductosRepositorio
from api.schemas.pedido import PedidoCrear
from api.services.errores import EstadoInvalido, NoEncontrado, StockInsuficiente


class PedidosServicio:
    def __init__(self, db: Database):
        self.pedidos = PedidosRepositorio(db)
        self.productos = ProductosRepositorio(db)
        self.clientes = ClientesRepositorio(db)

    def crear(self, datos: PedidoCrear) -> dict:
        # La función interna es lo que corre dentro de la transacción. Si lanza una
        # excepción (stock insuficiente, producto inexistente o cualquier error), la
        # transacción se aborta y Mongo descarta TODOS los descuentos de stock ya hechos.
        def operacion(session: ClientSession) -> dict:
            cliente = self.clientes.obtener(ObjectId(datos.cliente_id), session)
            if cliente is None:
                raise NoEncontrado(f"no existe el cliente {datos.cliente_id}")

            items = []
            for item in datos.items:
                producto_id = ObjectId(item.producto_id)
                producto = self.productos.descontar_stock(producto_id, item.cantidad, session)
                if producto is None:
                    # El descuento no aplicó: hay que distinguir si el producto no existe
                    # o si existe pero no alcanza el stock, para devolver un mensaje útil.
                    existente = self.productos.obtener(producto_id, session)
                    if existente is None:
                        raise NoEncontrado(f"no existe el producto {item.producto_id}")
                    raise StockInsuficiente(
                        f"stock insuficiente para {existente['sku']}: "
                        f"hay {existente['stock']} y se pidieron {item.cantidad}")
                items.append(self._armar_item(producto, item.cantidad))

            ahora = datetime.now(timezone.utc)
            bruto = round(sum(i["precio_unitario"] * i["cantidad"] for i in items), 2)
            total = round(sum(i["subtotal"] for i in items), 2)
            pedido = {
                "numero": self.pedidos.siguiente_numero(session),
                "cliente_id": cliente["_id"],
                "cliente": {"nombre": f"{cliente['nombre']} {cliente['apellido']}",
                            "email": cliente["email"]},
                "fecha": ahora,
                "estado": "pendiente",
                "historial_estados": [{"estado": "pendiente", "fecha": ahora}],
                "metodo_pago": datos.metodo_pago,
                # Copia: el pedido se envía a la dirección vigente al momento de comprar.
                "direccion_envio": dict(cliente["direccion"]),
                "items": items,
                "totales": {"bruto": bruto, "descuento": round(bruto - total, 2), "total": total},
                "cantidad_unidades": sum(i["cantidad"] for i in items),
            }
            pedido["_id"] = self.pedidos.insertar(pedido, session)
            return pedido

        return ejecutar_en_transaccion(operacion)

    @staticmethod
    def _armar_item(producto: dict, cantidad: int) -> dict:
        # Mismo cálculo que scripts/transformar.py, para que los pedidos nuevos y los
        # históricos sean comparables en el análisis.
        descuento = producto.get("descuento_pct", 0)
        return {
            "producto_id": producto["_id"],
            # Copia de sku, título y precio: quedan congelados a la fecha de la compra.
            "sku": producto["sku"],
            "titulo": producto["titulo"],
            "precio_unitario": producto["precio"],
            "descuento_pct": descuento,
            "cantidad": cantidad,
            "subtotal": round(producto["precio"] * cantidad * (1 - descuento / 100), 2),
        }

    def cancelar(self, id: ObjectId) -> dict:
        # Cambiar el estado y devolver el stock de cada ítem también son varios documentos:
        # si se cancelara el pedido y fallara la devolución, el stock quedaría perdido.
        def operacion(session: ClientSession) -> dict:
            pedido = self.pedidos.obtener(id, session)
            if pedido is None:
                raise NoEncontrado(f"no existe el pedido {id}")
            if pedido["estado"] not in CANCELABLES:
                raise EstadoInvalido(
                    f"el pedido está {pedido['estado']}; solo se cancela si está {' o '.join(CANCELABLES)}")
            if not self.pedidos.marcar_cancelado(id, datetime.now(timezone.utc), session):
                raise EstadoInvalido("el pedido cambió de estado mientras se cancelaba")
            for item in pedido["items"]:
                self.productos.devolver_stock(item["producto_id"], item["cantidad"], session)
            return self.pedidos.obtener(id, session)

        return ejecutar_en_transaccion(operacion)

    def obtener(self, id: ObjectId) -> dict:
        pedido = self.pedidos.obtener(id)
        if pedido is None:
            raise NoEncontrado(f"no existe el pedido {id}")
        return pedido

    def listar_por_cliente(self, cliente_id: ObjectId, limite: int) -> list[dict]:
        return self.pedidos.listar_por_cliente(cliente_id, limite)
