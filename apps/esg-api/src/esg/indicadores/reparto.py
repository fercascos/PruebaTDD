"""Reparto de una lectura a meses naturales.

Una factura va del 14 de marzo al 16 de abril. El dashboard habla de meses. En
algún punto hay que repartir, y la decisión de este proyecto es hacerlo **al
consultar** y no al guardar (decisión 1 del diseño): así el dato guardado sigue
siendo el que decía la factura y el criterio de reparto se puede cambiar.

El criterio es proporcional a los días. Es el único defendible sin datos
horarios: cualquier otro —cargar el consumo al mes de la fecha de factura, o
partir por mitades— desplaza consumo entre meses y estropea justo la
comparación interanual que se quiere leer.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal


def primer_dia(d: date) -> date:
    return d.replace(day=1)


def mes_siguiente(d: date) -> date:
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


def meses_entre(inicio: date, fin: date) -> list[date]:
    """Meses (día 1) que toca el intervalo `[inicio, fin)`."""
    if fin <= inicio:
        return []
    meses: list[date] = []
    mes = primer_dia(inicio)
    while mes < fin:
        meses.append(mes)
        mes = mes_siguiente(mes)
    return meses


def dias_en_mes(inicio: date, fin: date, mes: date) -> int:
    """Días del intervalo `[inicio, fin)` que caen dentro de `mes`."""
    desde = max(inicio, mes)
    hasta = min(fin, mes_siguiente(mes))
    return max((hasta - desde).days, 0)


def repartir(inicio: date, fin: date, cantidad: Decimal) -> dict[date, Decimal]:
    """Reparte `cantidad` entre los meses que toca `[inicio, fin)`.

    `[REQ]` La suma de lo repartido es **exactamente** la cantidad original. El
    último mes se lleva el resto del redondeo en vez de repartir el error: con
    doce facturas al año y cuatro decimales, redondear cada trozo por separado
    hacía que el total anual del dashboard no cuadrara con la suma de las
    facturas, y esa diferencia de céntimos es la que hace que nadie se fíe del
    resto de la pantalla.
    """
    total_dias = (fin - inicio).days
    if total_dias <= 0:
        return {}
    meses = meses_entre(inicio, fin)
    reparto: dict[date, Decimal] = {}
    acumulado = Decimal(0)
    for mes in meses[:-1]:
        parte = (cantidad * dias_en_mes(inicio, fin, mes) / total_dias).quantize(Decimal("0.0001"))
        reparto[mes] = parte
        acumulado += parte
    reparto[meses[-1]] = cantidad - acumulado
    return reparto


def dias_cubiertos(periodos: list[tuple[date, date]], desde: date, hasta: date) -> int:
    """Días del intervalo `[desde, hasta)` cubiertos por algún periodo.

    Los periodos que llegan aquí **no se solapan** —lo impide la restricción
    `sin_solape_por_suministro` del esquema—, pero esta función no lo da por
    hecho: cuenta días distintos. Que una barrera exista no es motivo para
    escribir código que se rompe cuando falle.
    """
    dias: set[date] = set()
    for inicio, fin in periodos:
        d = max(inicio, desde)
        tope = min(fin, hasta)
        while d < tope:
            dias.add(d)
            d += timedelta(days=1)
    return len(dias)
