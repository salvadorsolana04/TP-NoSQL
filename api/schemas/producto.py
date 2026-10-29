"""Esquemas de productos. Validan lo que entra por la API antes de que llegue a Mongo,
que por sí solo acepta cualquier documento."""
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.schemas.comun import Salida

# Restricciones reutilizadas en alta y modificación.
Sku = Annotated[str, Field(min_length=3, max_length=40, pattern=r"^[A-Z0-9-]+$",
                           description="Código de negocio, único. Ej.: SMA-APP-IPH-122")]
Titulo = Annotated[str, Field(min_length=1, max_length=200)]
Categoria = Annotated[str, Field(min_length=1, max_length=50, pattern=r"^[a-z0-9-]+$")]
Precio = Annotated[float, Field(gt=0)]
Descuento = Annotated[float, Field(ge=0, le=100)]
Stock = Annotated[int, Field(ge=0)]


class Dimensiones(BaseModel):
    ancho: float = Field(gt=0)
    alto: float = Field(gt=0)
    profundidad: float = Field(gt=0)


class ProductoCrear(BaseModel):
    # extra="forbid": un campo mal escrito ("precioo") da 422 en lugar de guardarse en silencio,
    # que es lo que haría Mongo al no tener esquema.
    model_config = ConfigDict(extra="forbid")

    sku: Sku
    titulo: Titulo
    descripcion: str | None = None
    categoria: Categoria
    marca: str | None = None
    precio: Precio
    descuento_pct: Descuento = 0
    stock: Stock
    etiquetas: list[str] = []
    dimensiones: Dimensiones | None = None
    peso: float | None = Field(default=None, ge=0)
    # Libre a propósito: cada categoría tiene atributos distintos (es la razón de usar
    # un modelo documental). Solo se exige que sea un objeto.
    atributos: dict[str, Any] | None = None
    garantia: str | None = None
    politica_devolucion: str | None = None
    envio: str | None = None
    cantidad_minima: int | None = Field(default=None, ge=1)
    imagenes: list[str] = []


# Campos que un producto siempre tiene que tener: en un PATCH no se pueden borrar con null.
OBLIGATORIOS = {"sku", "titulo", "categoria", "precio", "stock"}


class ProductoActualizar(BaseModel):
    """PATCH: solo se modifican los campos enviados. Enviar null en un campo opcional
    lo elimina del documento (por ejemplo, {"marca": null})."""

    model_config = ConfigDict(extra="forbid")

    sku: Sku | None = None
    titulo: Titulo | None = None
    descripcion: str | None = None
    categoria: Categoria | None = None
    marca: str | None = None
    precio: Precio | None = None
    descuento_pct: Descuento | None = None
    stock: Stock | None = None
    etiquetas: list[str] | None = None
    dimensiones: Dimensiones | None = None
    peso: float | None = Field(default=None, ge=0)
    atributos: dict[str, Any] | None = None
    garantia: str | None = None
    politica_devolucion: str | None = None
    envio: str | None = None
    cantidad_minima: int | None = Field(default=None, ge=1)
    imagenes: list[str] | None = None

    @model_validator(mode="after")
    def _validar(self) -> "ProductoActualizar":
        enviados = self.model_fields_set
        if not enviados:
            raise ValueError("no se envió ningún campo para actualizar")
        nulos = {c for c in enviados & OBLIGATORIOS if getattr(self, c) is None}
        if nulos:
            raise ValueError(f"estos campos son obligatorios y no pueden ser null: {sorted(nulos)}")
        return self


class ReviewCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: int = Field(ge=1, le=5)
    comentario: str = Field(min_length=1, max_length=1000)
    autor: str = Field(min_length=1, max_length=100)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Review(BaseModel):
    rating: int
    comentario: str
    fecha: datetime
    autor: str
    email: str


# Las salidas no repiten las restricciones de entrada: describen lo que hay en la base,
# y el seed puede tener valores que una alta nueva no aceptaría.
class ProductoResumen(Salida):
    """Lo que devuelve el listado: sin reviews ni descripción, para no mandar de más."""

    sku: str
    titulo: str
    categoria: str
    marca: str | None = None
    precio: float
    descuento_pct: float = 0
    stock: int
    rating_promedio: float | None = None


class ProductoSalida(ProductoResumen):
    descripcion: str | None = None
    etiquetas: list[str] = []
    dimensiones: dict[str, float] | None = None
    peso: float | None = None
    atributos: dict[str, Any] | None = None
    garantia: str | None = None
    politica_devolucion: str | None = None
    envio: str | None = None
    cantidad_minima: int | None = None
    reviews: list[Review] = []
    imagenes: list[str] = []
    creado_en: datetime | None = None
    actualizado_en: datetime | None = None
