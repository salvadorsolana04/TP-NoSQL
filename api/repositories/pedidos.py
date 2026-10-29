"""Acceso a la colección pedidos (y al contador de números de pedido)."""
from datetime import datetime

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.client_session import ClientSession
from pymongo.database import Database

# Solo se cancela desde estos estados (sección 5.3 del diseño): un pedido enviado ya salió.
CANCELABLES = ["pendiente", "pagado"]


class PedidosRepositorio:
    def __init__(self, db: Database):
        self.col = db.pedidos
        self.contadores = db.contadores

    def siguiente_numero(self, session: ClientSession) -> int:
        """Número correlativo de pedido.

        Buscar el máximo y sumarle 1 fallaría con dos pedidos simultáneos (los dos leerían
        el mismo máximo). El $inc sobre un único documento contador es atómico, y dentro de
        la transacción, si otra la modifica a la vez, Mongo detecta el conflicto y
        with_transaction reintenta. cargar.py lo inicializa con el último número del seed.
        """
        contador = self.contadores.find_one_and_update(
            {"_id": "pedidos"}, {"$inc": {"ultimo": 1}},
            upsert=True, return_document=ReturnDocument.AFTER, session=session,
        )
        return contador["ultimo"]

    def insertar(self, pedido: dict, session: ClientSession) -> ObjectId:
        return self.col.insert_one(pedido, session=session).inserted_id

    def obtener(self, id: ObjectId, session: ClientSession | None = None) -> dict | None:
        return self.col.find_one({"_id": id}, session=session)

    def listar_por_cliente(self, cliente_id: ObjectId, limite: int = 20) -> list[dict]:
        # RF5. Usa el índice cliente_fecha: filtra por cliente y ya devuelve ordenado.
        return list(self.col.find({"cliente_id": cliente_id}).sort("fecha", -1).limit(limite))

    def marcar_cancelado(self, id: ObjectId, fecha: datetime, session: ClientSession) -> bool:
        """Cambia el estado a cancelado solo si sigue en un estado cancelable. La condición
        va en el filtro (no alcanza con haberla chequeado antes): si dos cancelaciones
        llegan juntas, solo una modifica el documento y el stock se devuelve una vez."""
        resultado = self.col.update_one(
            {"_id": id, "estado": {"$in": CANCELABLES}},
            {"$set": {"estado": "cancelado"},
             "$push": {"historial_estados": {"estado": "cancelado", "fecha": fecha}}},
            session=session,
        )
        return resultado.modified_count == 1
