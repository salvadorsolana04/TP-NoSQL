"""Endpoints HTTP de productos (entidad principal, CRUD de la sección 5.4).

Los routers solo traducen HTTP: leen parámetros, llaman al servicio y eligen el código de
respuesta. Los errores de negocio los convierte main.py."""
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status

from api.db import get_db
from api.routers.comun import a_object_id
from api.schemas.producto import (ProductoActualizar, ProductoCrear, ProductoResumen,
                                  ProductoSalida, ReviewCrear)
from api.services.productos import ProductosServicio

router = APIRouter(prefix="/productos", tags=["productos"])


def servicio() -> ProductosServicio:
    return ProductosServicio(get_db())


@router.post("", response_model=ProductoSalida, status_code=status.HTTP_201_CREATED,
             summary="Crear un producto",
             responses={409: {"description": "Ya existe un producto con ese sku"}})
def crear(datos: ProductoCrear, response: Response, svc: ProductosServicio = Depends(servicio)):
    producto = svc.crear(datos)
    response.headers["Location"] = f"/productos/{producto['_id']}"
    return producto


@router.get("", response_model=list[ProductoResumen], summary="Listar productos con filtros")
def listar(
    categoria: str | None = None,
    marca: str | None = None,
    precio_min: float | None = Query(None, ge=0),
    precio_max: float | None = Query(None, ge=0),
    con_stock: bool = Query(False, description="Solo productos con stock > 0"),
    orden: Literal["precio", "-precio", "titulo", "-rating"] = "precio",
    limite: int = Query(20, ge=1, le=100),
    desde: int = Query(0, ge=0, description="Cuántos resultados saltear (paginación)"),
    svc: ProductosServicio = Depends(servicio),
):
    return svc.listar(categoria=categoria, marca=marca, precio_min=precio_min,
                      precio_max=precio_max, con_stock=con_stock, orden=orden,
                      limite=limite, desde=desde)


@router.get("/{id}", response_model=ProductoSalida, summary="Obtener un producto por id",
            responses={404: {"description": "No existe"}})
def obtener(id: str, svc: ProductosServicio = Depends(servicio)):
    return svc.obtener(a_object_id(id))


@router.patch("/{id}", response_model=ProductoSalida, summary="Modificar campos de un producto",
              responses={404: {"description": "No existe"}, 409: {"description": "sku duplicado"}})
def actualizar(id: str, datos: ProductoActualizar, svc: ProductosServicio = Depends(servicio)):
    return svc.actualizar(a_object_id(id), datos)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Dar de baja un producto (borrado lógico)",
               responses={404: {"description": "No existe o ya fue dado de baja"}})
def eliminar(id: str, svc: ProductosServicio = Depends(servicio)):
    svc.eliminar(a_object_id(id))


@router.post("/{id}/reviews", response_model=ProductoSalida, status_code=status.HTTP_201_CREATED,
             summary="Agregar una reseña y recalcular el rating (RF6)",
             responses={404: {"description": "No existe"}})
def agregar_review(id: str, datos: ReviewCrear, svc: ProductosServicio = Depends(servicio)):
    return svc.agregar_review(a_object_id(id), datos)
