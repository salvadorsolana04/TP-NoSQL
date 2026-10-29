"""Lógica de productos. Es poca (el CRUD es casi directo), pero acá se decide qué es un
error de negocio, así los routers solo hablan HTTP y los repositorios solo hablan Mongo."""
from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from api.repositories.productos import ProductosRepositorio
from api.schemas.producto import ProductoActualizar, ProductoCrear, ReviewCrear
from api.services.errores import NoEncontrado, SkuDuplicado


class ProductosServicio:
    def __init__(self, db: Database):
        self.repo = ProductosRepositorio(db)

    def crear(self, datos: ProductoCrear) -> dict:
        # exclude_none: un campo opcional que no vino queda AUSENTE en el documento, igual
        # que en el seed (por ejemplo, la marca), en vez de guardarse como null.
        try:
            return self.repo.crear(datos.model_dump(exclude_none=True))
        except DuplicateKeyError:
            raise SkuDuplicado(f"ya existe un producto con sku {datos.sku}")

    def obtener(self, id: ObjectId) -> dict:
        producto = self.repo.obtener(id)
        if producto is None:
            raise NoEncontrado(f"no existe el producto {id}")
        return producto

    def listar(self, **filtros) -> list[dict]:
        return self.repo.listar(**filtros)

    def actualizar(self, id: ObjectId, datos: ProductoActualizar) -> dict:
        # exclude_unset: solo los campos que vinieron en el JSON. Entre ellos, los que vinieron
        # en null se eliminan del documento; el resto se modifica.
        enviados = datos.model_dump(exclude_unset=True)
        borrar = {campo for campo, valor in enviados.items() if valor is None}
        cambios = {campo: valor for campo, valor in enviados.items() if valor is not None}
        try:
            producto = self.repo.actualizar(id, cambios, borrar)
        except DuplicateKeyError:
            raise SkuDuplicado(f"ya existe un producto con sku {datos.sku}")
        if producto is None:
            raise NoEncontrado(f"no existe el producto {id}")
        return producto

    def eliminar(self, id: ObjectId) -> None:
        if not self.repo.eliminar(id):
            raise NoEncontrado(f"no existe el producto {id}")

    def agregar_review(self, id: ObjectId, datos: ReviewCrear) -> dict:
        producto = self.repo.agregar_review(id, datos.model_dump())
        if producto is None:
            raise NoEncontrado(f"no existe el producto {id}")
        return producto
