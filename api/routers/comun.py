"""Utilidades compartidas por los routers."""
from bson import ObjectId
from fastapi import HTTPException, status


def a_object_id(valor: str, nombre: str = "id") -> ObjectId:
    # Un id mal formado es un error del cliente (422), distinto de un id bien formado que
    # no existe (404). Sin este chequeo, ObjectId("abc") lanzaría una excepción → 500.
    if not ObjectId.is_valid(valor):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"{nombre} inválido: tiene que tener 24 caracteres hexadecimales")
    return ObjectId(valor)
