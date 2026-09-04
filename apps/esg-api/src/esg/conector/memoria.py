"""Doble en memoria del lector de facturas. Solo para pruebas y demostración."""

from __future__ import annotations

from datetime import date

from esg.conector.puerto import FacturaLeida, Lote


class LectorEnMemoria:
    def __init__(self, facturas: list[FacturaLeida] | None = None, *, pagina: int = 100):
        self.facturas_disponibles = facturas or []
        self._pagina = pagina
        #: Las llamadas recibidas, para que una prueba pueda comprobar que se
        #: pidió la ventana que se pidió.
        self.llamadas: list[tuple[date, date, str | None]] = []

    def facturas(self, *, desde: date, hasta: date, cursor: str | None = None) -> Lote:
        self.llamadas.append((desde, hasta, cursor))
        candidatas = [f for f in self.facturas_disponibles if f.inicio < hasta and f.fin > desde]
        arranque = int(cursor) if cursor else 0
        trozo = candidatas[arranque : arranque + self._pagina]
        siguiente = arranque + self._pagina
        return Lote(
            facturas=trozo,
            siguiente=str(siguiente) if siguiente < len(candidatas) else None,
        )
