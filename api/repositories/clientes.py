"""Acceso a la colección clientes. La API no tiene CRUD de clientes (la entidad principal
es producto); solo se leen para armar los pedidos."""
from bson import ObjectId
from pymongo.client_session import ClientSession
from pymongo.database import Database


class ClientesRepositorio:
    def __init__(self, db: Database):
        self.col = db.clientes

    def obtener(self, id: ObjectId, session: ClientSession | None = None) -> dict | None:
        return self.col.find_one({"_id": id}, session=session)
