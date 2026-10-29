"""Errores de negocio. Los servicios los lanzan sin saber de HTTP; main.py los traduce
al código de estado que corresponde."""


class ErrorDeNegocio(Exception):
    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


class NoEncontrado(ErrorDeNegocio):
    """404: el recurso no existe (o fue dado de baja)."""


class Conflicto(ErrorDeNegocio):
    """409: la operación choca con el estado actual de los datos."""


class SkuDuplicado(Conflicto):
    pass


class StockInsuficiente(Conflicto):
    pass


class EstadoInvalido(Conflicto):
    pass
