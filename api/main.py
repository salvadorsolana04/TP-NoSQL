"""Punto de entrada de la API.

Local:  uvicorn api.main:app --reload   (desde la raíz del proyecto)
Docker: servicio api del compose. Documentación interactiva (Swagger) en /docs.
"""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pymongo.errors import ConnectionFailure

from api.db import get_db
from api.routers import pedidos, productos
from api.services.errores import Conflicto, ErrorDeNegocio, NoEncontrado

app = FastAPI(
    title="E-commerce · TP NoSQL",
    description="Catálogo de productos (CRUD) y pedidos con descuento de stock transaccional, sobre MongoDB.",
    version="1.0.0",
)
app.include_router(productos.router)
app.include_router(pedidos.router)

# Cada error de negocio tiene su código HTTP. Se decide en un solo lugar, así los
# servicios no dependen de FastAPI y los routers no repiten try/except.
CODIGOS = {NoEncontrado: status.HTTP_404_NOT_FOUND, Conflicto: status.HTTP_409_CONFLICT}


@app.exception_handler(ErrorDeNegocio)
def error_de_negocio(_: Request, error: ErrorDeNegocio) -> JSONResponse:
    codigo = next((c for tipo, c in CODIGOS.items() if isinstance(error, tipo)),
                  status.HTTP_400_BAD_REQUEST)
    return JSONResponse(status_code=codigo, content={"detail": error.mensaje})


@app.exception_handler(ConnectionFailure)
def base_no_disponible(_: Request, __: ConnectionFailure) -> JSONResponse:
    # 503 y no 500: el problema no es del request sino de que Mongo no responde.
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        content={"detail": "la base de datos no está disponible"})


@app.get("/salud", tags=["salud"], summary="Verifica que la API llega a MongoDB")
def salud():
    get_db().command("ping")
    return {"estado": "ok"}
