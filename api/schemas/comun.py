"""Tipos compartidos por los esquemas: conversión entre ObjectId y string."""
from typing import Annotated, Any

from bson import ObjectId
from pydantic import AfterValidator, BaseModel, BeforeValidator, model_validator


def _a_str(valor: Any) -> Any:
    return str(valor) if isinstance(valor, ObjectId) else valor


def _validar_object_id(valor: str) -> str:
    if not ObjectId.is_valid(valor):
        raise ValueError("no es un id válido (24 caracteres hexadecimales)")
    return valor


# Salida: Mongo devuelve ObjectId, que JSON no sabe representar; se muestra como string.
IdSalida = Annotated[str, BeforeValidator(_a_str)]

# Entrada: un string que tiene que poder convertirse en ObjectId. Si no, 422 con el motivo.
IdEntrada = Annotated[str, AfterValidator(_validar_object_id)]


class Salida(BaseModel):
    """Base de las respuestas: expone el _id de Mongo como "id"."""

    id: IdSalida

    @model_validator(mode="before")
    @classmethod
    def _renombrar_id(cls, datos: Any) -> Any:
        if isinstance(datos, dict) and "_id" in datos:
            datos = {**datos, "id": datos["_id"]}
        return datos
