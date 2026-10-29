"""Acceso a la colección productos. Es el único lugar de la API que arma consultas a Mongo
sobre productos: los routers y servicios llaman a estos métodos y no saben de filtros ni
operadores."""
from datetime import datetime, timezone

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.client_session import ClientSession
from pymongo.database import Database

# Borrado lógico: un producto eliminado queda con activo: false. Se usa $ne en vez de
# activo: true porque los productos del seed no tienen el campo (ausente = activo).
ACTIVO = {"activo": {"$ne": False}}

# Proyección del listado: coincide con ProductoResumen. Pedir solo estos campos evita
# traer reviews, descripción e imágenes de cada producto.
CAMPOS_RESUMEN = {"sku": 1, "titulo": 1, "categoria": 1, "marca": 1, "precio": 1,
                  "descuento_pct": 1, "stock": 1, "rating_promedio": 1}

ORDENES = {"precio": [("precio", 1)], "-precio": [("precio", -1)],
           "titulo": [("titulo", 1)], "-rating": [("rating_promedio", -1)]}


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


class ProductosRepositorio:
    def __init__(self, db: Database):
        self.col = db.productos

    def crear(self, datos: dict) -> dict:
        """Inserta un producto nuevo. Si el sku ya existe, el índice único sku_unico hace
        que Mongo lance DuplicateKeyError (la API lo traduce a 409)."""
        ahora = _ahora()
        doc = {**datos, "rating_promedio": None, "reviews": [],
               "creado_en": ahora, "actualizado_en": ahora}
        doc["_id"] = self.col.insert_one(doc).inserted_id
        return doc

    def obtener(self, id: ObjectId, session: ClientSession | None = None) -> dict | None:
        return self.col.find_one({"_id": id, **ACTIVO}, session=session)

    def listar(self, *, categoria: str | None = None, marca: str | None = None,
               precio_min: float | None = None, precio_max: float | None = None,
               con_stock: bool = False, orden: str = "precio",
               limite: int = 20, desde: int = 0) -> list[dict]:
        filtro: dict = dict(ACTIVO)
        if categoria:
            filtro["categoria"] = categoria
        if marca:
            filtro["marca"] = marca
        if precio_min is not None or precio_max is not None:
            filtro["precio"] = {}
            if precio_min is not None:
                filtro["precio"]["$gte"] = precio_min
            if precio_max is not None:
                filtro["precio"]["$lte"] = precio_max
        if con_stock:
            filtro["stock"] = {"$gt": 0}
        # Con categoría + rango/orden de precio, Mongo usa el índice categoria_precio.
        # _id como desempate: sin él, productos con el mismo precio podrían repetirse o
        # saltearse entre páginas.
        return list(self.col.find(filtro, CAMPOS_RESUMEN)
                    .sort(ORDENES[orden] + [("_id", 1)]).skip(desde).limit(limite))

    def actualizar(self, id: ObjectId, cambios: dict, borrar: set[str]) -> dict | None:
        """$set de los campos enviados y $unset de los que llegaron en null.
        Devuelve el documento ya modificado, o None si no existe."""
        operacion: dict = {"$set": {**cambios, "actualizado_en": _ahora()}}
        if borrar:
            operacion["$unset"] = {campo: "" for campo in borrar}
        return self.col.find_one_and_update({"_id": id, **ACTIVO}, operacion,
                                            return_document=ReturnDocument.AFTER)

    def eliminar(self, id: ObjectId) -> bool:
        """Borrado lógico. Se conserva el documento porque los pedidos históricos lo
        referencian: el análisis de ventas por categoría hace $lookup a productos, y si
        el producto desapareciera esas ventas quedarían sin categoría."""
        resultado = self.col.update_one({"_id": id, **ACTIVO},
                                        {"$set": {"activo": False, "eliminado_en": _ahora()}})
        return resultado.modified_count == 1

    def agregar_review(self, id: ObjectId, review: dict) -> dict | None:
        """Agrega la reseña y recalcula rating_promedio en UNA sola operación atómica.

        Es un update con pipeline: la segunda etapa ve el arreglo que dejó la primera, así
        que el promedio siempre incluye la reseña nueva. Hacerlo en dos operaciones (leer,
        calcular en Python, escribir) permitiría que dos reseñas simultáneas se pisen."""
        review = {**review, "fecha": _ahora()}
        return self.col.find_one_and_update(
            {"_id": id, **ACTIVO},
            [
                # $literal: dentro de un pipeline, un string que empieza con "$" se
                # interpretaría como nombre de campo. Así el comentario se guarda tal cual.
                {"$set": {"reviews": {"$concatArrays": [{"$ifNull": ["$reviews", []]},
                                                        [{"$literal": review}]]}}},
                {"$set": {"rating_promedio": {"$round": [{"$avg": "$reviews.rating"}, 2]},
                          "actualizado_en": "$$NOW"}},
            ],
            return_document=ReturnDocument.AFTER,
        )

    def descontar_stock(self, id: ObjectId, cantidad: int, session: ClientSession) -> dict | None:
        """Descuenta stock solo si alcanza. La condición stock >= cantidad y el $inc van en
        la misma operación, que es atómica sobre el documento: dos compras simultáneas no
        pueden dejar el stock negativo. Devuelve el producto como estaba ANTES (para copiar
        su precio al pedido) o None si no existe o no hay stock suficiente."""
        return self.col.find_one_and_update(
            {"_id": id, **ACTIVO, "stock": {"$gte": cantidad}},
            {"$inc": {"stock": -cantidad}, "$set": {"actualizado_en": _ahora()}},
            return_document=ReturnDocument.BEFORE,
            session=session,
        )

    def devolver_stock(self, id: ObjectId, cantidad: int, session: ClientSession) -> None:
        # Sin filtro de ACTIVO: si el producto se dio de baja después de la compra, el stock
        # igual vuelve, para que los números cierren si se lo reactiva.
        self.col.update_one({"_id": id},
                            {"$inc": {"stock": cantidad}, "$set": {"actualizado_en": _ahora()}},
                            session=session)
