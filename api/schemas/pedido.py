"""Esquemas de pedidos."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.schemas.comun import IdEntrada, IdSalida, Salida

MetodoPago = Literal["tarjeta_credito", "tarjeta_debito", "mercado_pago", "transferencia"]
Estado = Literal["pendiente", "pagado", "enviado", "entregado", "cancelado"]


class ItemCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    producto_id: IdEntrada
    cantidad: int = Field(ge=1, le=100)


class PedidoCrear(BaseModel):
    """Lo que manda el cliente: quién compra, qué y cómo paga. Precios, totales, número
    y estado los calcula el servidor; si vinieran del cliente se podrían adulterar."""

    model_config = ConfigDict(extra="forbid")

    cliente_id: IdEntrada
    items: list[ItemCrear] = Field(min_length=1, max_length=50)
    metodo_pago: MetodoPago

    @field_validator("items")
    @classmethod
    def _sin_productos_repetidos(cls, items: list[ItemCrear]) -> list[ItemCrear]:
        # Igual que en la transformación: un producto, un ítem. Así el stock se descuenta
        # una sola vez por producto y el pedido no tiene dos líneas iguales.
        ids = [i.producto_id for i in items]
        if len(ids) != len(set(ids)):
            raise ValueError("hay productos repetidos: sumá las cantidades en un solo ítem")
        return items


class ItemSalida(BaseModel):
    producto_id: IdSalida
    sku: str
    titulo: str
    precio_unitario: float
    descuento_pct: float
    cantidad: int
    subtotal: float


class CambioEstado(BaseModel):
    estado: Estado
    fecha: datetime


class ClienteResumen(BaseModel):
    nombre: str
    email: str


class Totales(BaseModel):
    bruto: float
    descuento: float
    total: float


class PedidoSalida(Salida):
    numero: int
    cliente_id: IdSalida
    cliente: ClienteResumen
    fecha: datetime
    estado: Estado
    historial_estados: list[CambioEstado]
    metodo_pago: MetodoPago
    direccion_envio: dict[str, str]
    items: list[ItemSalida]
    totales: Totales
    cantidad_unidades: int
