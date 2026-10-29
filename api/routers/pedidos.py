"""Endpoints HTTP de pedidos: crear y cancelar (con transacción) y consultar."""
from fastapi import APIRouter, Depends, Query, Response, status

from api.db import get_db
from api.routers.comun import a_object_id
from api.schemas.pedido import PedidoCrear, PedidoSalida
from api.services.pedidos import PedidosServicio

router = APIRouter(prefix="/pedidos", tags=["pedidos"])


def servicio() -> PedidosServicio:
    return PedidosServicio(get_db())


@router.post("", response_model=PedidoSalida, status_code=status.HTTP_201_CREATED,
             summary="Registrar un pedido y descontar el stock (transacción)",
             responses={404: {"description": "No existe el cliente o algún producto"},
                        409: {"description": "Stock insuficiente: no se descuenta nada"}})
def crear(datos: PedidoCrear, response: Response, svc: PedidosServicio = Depends(servicio)):
    pedido = svc.crear(datos)
    response.headers["Location"] = f"/pedidos/{pedido['_id']}"
    return pedido


@router.get("", response_model=list[PedidoSalida],
            summary="Pedidos de un cliente, del más reciente al más viejo (RF5)")
def listar(cliente_id: str, limite: int = Query(20, ge=1, le=100),
           svc: PedidosServicio = Depends(servicio)):
    return svc.listar_por_cliente(a_object_id(cliente_id, "cliente_id"), limite)


@router.get("/{id}", response_model=PedidoSalida, summary="Obtener un pedido por id",
            responses={404: {"description": "No existe"}})
def obtener(id: str, svc: PedidosServicio = Depends(servicio)):
    return svc.obtener(a_object_id(id))


@router.post("/{id}/cancelar", response_model=PedidoSalida,
             summary="Cancelar un pedido y devolver el stock (transacción)",
             responses={404: {"description": "No existe"},
                        409: {"description": "El pedido ya no se puede cancelar"}})
def cancelar(id: str, svc: PedidosServicio = Depends(servicio)):
    return svc.cancelar(a_object_id(id))
