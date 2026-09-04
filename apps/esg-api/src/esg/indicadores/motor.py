"""Motor de indicadores: de lecturas sueltas a lo que enseña el dashboard.

Todo lo de aquí son **funciones puras sobre datos ya leídos**. No abre
conexiones ni sabe de FastAPI: se le dan lecturas, activos y ocupación, y
devuelve el panel. Así el cálculo —que es la parte que hay que defender delante
de un cliente— se prueba entero sin base de datos, y la parte que necesita base
de datos es solo el `SELECT` que trae las filas.

`[LIM]` El reparto a meses se hace en Python, no en SQL. Con el volumen de este
dominio —un edificio tiene entre 4 y 40 suministros, y cada uno doce facturas
al año— son miles de filas por consulta y sobra. Con cientos de miles de
lecturas habría que bajarlo a una vista con `generate_series`; el reparto está
aislado en `reparto.py` justo para que ese cambio sea de un fichero.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from esg.indicadores.reparto import dias_cubiertos, repartir
from esg.indicadores.unidades import UNIDAD_NORMAL, VECTORES

CERO = Decimal("0.0000")


@dataclass(frozen=True, slots=True)
class LecturaAgregable:
    """Una lectura tal y como la necesita el cálculo."""

    punto_id: uuid.UUID
    activo_id: uuid.UUID
    cartera_id: uuid.UUID
    vector: str
    inicio: date
    fin: date
    cantidad_normalizada: Decimal | None
    calidad: str = "MEDIDO"


@dataclass(frozen=True, slots=True)
class ActivoParaCalculo:
    id: uuid.UUID
    cartera_id: uuid.UUID
    codigo: str
    nombre: str
    #: La superficie **ya resuelta** según el criterio del activo o de su
    #: cartera. Resolverla es de `estructura`, no de aquí: este módulo no debe
    #: tener que saber qué es una cartera.
    superficie_m2: Decimal | None
    superficie_de_referencia: str


@dataclass(frozen=True, slots=True)
class PuntoEsperado:
    """Un suministro que **debería** tener dato en la ventana consultada.

    Sin esta lista no hay cobertura posible: los meses sin ninguna lectura no
    dejan ni rastro en la tabla de lecturas, y un activo del que no ha llegado
    nada saldría con cobertura perfecta de cero datos.
    """

    id: uuid.UUID
    activo_id: uuid.UUID
    vector: str
    alta_en: date | None = None
    baja_en: date | None = None


@dataclass(frozen=True, slots=True)
class Cobertura:
    dias_esperados: int
    dias_con_dato: int
    lecturas_sin_normalizar: int = 0

    @property
    def porcentaje(self) -> Decimal | None:
        if self.dias_esperados == 0:
            return None
        return (Decimal(self.dias_con_dato) * 100 / Decimal(self.dias_esperados)).quantize(
            Decimal("0.1")
        )


@dataclass(frozen=True, slots=True)
class TotalVector:
    vector: str
    unidad: str
    medido: Decimal
    estimado: Decimal
    cobertura: Cobertura

    @property
    def total(self) -> Decimal:
        """`[REQ]` Medido y estimado **no se mezclan aquí**.

        Quien quiera sumarlos lo hace a la vista, sabiendo lo que suma. El
        total del panel es lo medido: es lo que se puede defender.
        """
        return self.medido


@dataclass
class FilaDeActivo:
    activo_id: uuid.UUID
    codigo: str
    nombre: str
    cartera_id: uuid.UUID
    superficie_m2: Decimal | None
    superficie_de_referencia: str
    ocupantes_medios: Decimal | None
    por_vector: dict[str, TotalVector] = field(default_factory=dict)

    def intensidad_por_m2(self, vector: str) -> Decimal | None:
        """Consumo por metro cuadrado. `None` sin superficie, **nunca 0**.

        Un cero aquí se leería como «este edificio no consume» y saldría el
        primero en el ranking de eficiencia. Sin superficie no hay intensidad.
        """
        total = self.por_vector.get(vector)
        if total is None or self.superficie_m2 in (None, 0):
            return None
        assert self.superficie_m2 is not None
        return (total.medido / self.superficie_m2).quantize(Decimal("0.0001"))

    def intensidad_por_ocupante(self, vector: str) -> Decimal | None:
        total = self.por_vector.get(vector)
        if total is None or self.ocupantes_medios in (None, 0):
            return None
        assert self.ocupantes_medios is not None
        return (total.medido / self.ocupantes_medios).quantize(Decimal("0.0001"))


@dataclass
class Panel:
    desde: date
    hasta: date
    totales: dict[str, TotalVector]
    #: (vector, mes) → cantidad. Solo lo medido: una serie que mezcla medido y
    #: estimado tiene escalones que parecen consumo y son criterio de carga.
    serie: dict[tuple[str, date], Decimal]
    activos: list[FilaDeActivo]
    #: Totales del periodo anterior de la misma longitud, para la variación.
    comparativa: dict[str, Decimal] = field(default_factory=dict)

    def variacion(self, vector: str) -> Decimal | None:
        """Variación porcentual contra el periodo anterior.

        `None` —y no 0— cuando el periodo anterior no tiene dato o es cero: sin
        base con la que comparar, «0 %» sería una afirmación falsa sobre una
        mejora que nadie ha medido.
        """
        anterior = self.comparativa.get(vector)
        actual = self.totales.get(vector)
        if anterior is None or anterior == 0 or actual is None:
            return None
        return ((actual.medido - anterior) * 100 / anterior).quantize(Decimal("0.1"))


def _dias_esperados(punto: PuntoEsperado, desde: date, hasta: date) -> int:
    """Días de la ventana en los que ese suministro estaba de alta.

    Un contador dado de alta en septiembre no tiene un agujero de ocho meses:
    no existía. Contarlo como hueco hunde la cobertura de una cartera entera
    cada vez que se incorpora un activo, y entonces nadie mira la cobertura.
    """
    inicio = max(desde, punto.alta_en) if punto.alta_en else desde
    fin = min(hasta, punto.baja_en) if punto.baja_en else hasta
    return max((fin - inicio).days, 0)


def calcular_panel(
    *,
    desde: date,
    hasta: date,
    lecturas: list[LecturaAgregable],
    activos: list[ActivoParaCalculo],
    puntos: list[PuntoEsperado],
    ocupacion: dict[uuid.UUID, Decimal] | None = None,
    lecturas_anteriores: list[LecturaAgregable] | None = None,
) -> Panel:
    """Calcula el panel de una ventana `[desde, hasta)`.

    Las lecturas pueden empezar antes o acabar después de la ventana: se
    reparten a meses y **solo cuenta la parte que cae dentro**. Es la única
    forma de que el total de enero no dependa de qué día facturó cada
    comercializadora.
    """
    ocupacion = ocupacion or {}
    por_activo = {a.id: a for a in activos}

    aportes: dict[tuple[uuid.UUID, str, str], Decimal] = defaultdict(lambda: CERO)
    serie: dict[tuple[str, date], Decimal] = defaultdict(lambda: CERO)
    periodos: dict[tuple[uuid.UUID, str], list[tuple[date, date]]] = defaultdict(list)
    sin_normalizar: dict[tuple[uuid.UUID, str], int] = defaultdict(int)

    for lec in lecturas:
        recorte = (max(lec.inicio, desde), min(lec.fin, hasta))
        if recorte[0] >= recorte[1]:
            continue
        # La cobertura se mide con el periodo declarado, esté normalizado o no:
        # el dato llegó, aunque todavía no se pueda sumar.
        periodos[(lec.punto_id, lec.vector)].append(recorte)
        if lec.cantidad_normalizada is None:
            sin_normalizar[(lec.activo_id, lec.vector)] += 1
            continue
        for mes, parte in repartir(lec.inicio, lec.fin, lec.cantidad_normalizada).items():
            if mes < desde.replace(day=1) or mes >= hasta:
                continue
            # El mes puede asomar por los bordes de la ventana: se recorta con
            # la proporción de días que caen dentro.
            parte_dentro = _recortar_mes(lec, mes, parte, desde, hasta)
            if parte_dentro == 0:
                continue
            clave = (lec.activo_id, lec.vector, lec.calidad)
            aportes[clave] += parte_dentro
            if lec.calidad == "MEDIDO":
                serie[(lec.vector, mes)] += parte_dentro

    filas: list[FilaDeActivo] = []
    for activo in activos:
        fila = FilaDeActivo(
            activo_id=activo.id,
            codigo=activo.codigo,
            nombre=activo.nombre,
            cartera_id=activo.cartera_id,
            superficie_m2=activo.superficie_m2,
            superficie_de_referencia=activo.superficie_de_referencia,
            ocupantes_medios=ocupacion.get(activo.id),
        )
        for vector in VECTORES:
            puntos_del_vector = [
                p for p in puntos if p.activo_id == activo.id and p.vector == vector
            ]
            if not puntos_del_vector and not any(
                aportes.get((activo.id, vector, c), CERO) for c in ("MEDIDO", "ESTIMADO")
            ):
                continue
            esperados = sum(_dias_esperados(p, desde, hasta) for p in puntos_del_vector)
            con_dato = sum(
                dias_cubiertos(periodos.get((p.id, vector), []), desde, hasta)
                for p in puntos_del_vector
            )
            fila.por_vector[vector] = TotalVector(
                vector=vector,
                unidad=UNIDAD_NORMAL[vector],
                medido=aportes.get((activo.id, vector, "MEDIDO"), CERO),
                estimado=aportes.get((activo.id, vector, "ESTIMADO"), CERO),
                cobertura=Cobertura(
                    dias_esperados=esperados,
                    dias_con_dato=min(con_dato, esperados) if esperados else con_dato,
                    lecturas_sin_normalizar=sin_normalizar.get((activo.id, vector), 0),
                ),
            )
        filas.append(fila)

    totales: dict[str, TotalVector] = {}
    for vector in VECTORES:
        presentes = [f.por_vector[vector] for f in filas if vector in f.por_vector]
        if not presentes:
            continue
        totales[vector] = TotalVector(
            vector=vector,
            unidad=UNIDAD_NORMAL[vector],
            medido=sum((t.medido for t in presentes), CERO),
            estimado=sum((t.estimado for t in presentes), CERO),
            cobertura=Cobertura(
                dias_esperados=sum(t.cobertura.dias_esperados for t in presentes),
                dias_con_dato=sum(t.cobertura.dias_con_dato for t in presentes),
                lecturas_sin_normalizar=sum(
                    t.cobertura.lecturas_sin_normalizar for t in presentes
                ),
            ),
        )

    comparativa: dict[str, Decimal] = {}
    if lecturas_anteriores is not None:
        dias = (hasta - desde).days
        anterior_desde = date.fromordinal(desde.toordinal() - dias)
        panel_anterior = calcular_panel(
            desde=anterior_desde,
            hasta=desde,
            lecturas=lecturas_anteriores,
            activos=activos,
            puntos=puntos,
        )
        comparativa = {v: t.medido for v, t in panel_anterior.totales.items()}

    filas.sort(key=lambda f: f.codigo)
    return Panel(
        desde=desde,
        hasta=hasta,
        totales=totales,
        serie=dict(sorted(serie.items(), key=lambda kv: (kv[0][1], kv[0][0]))),
        activos=filas,
        comparativa=comparativa,
    )


def _recortar_mes(
    lec: LecturaAgregable, mes: date, parte: Decimal, desde: date, hasta: date
) -> Decimal:
    """La parte del mes que cae dentro de la ventana consultada."""
    from esg.indicadores.reparto import dias_en_mes, mes_siguiente

    dias_del_mes = dias_en_mes(lec.inicio, lec.fin, mes)
    if dias_del_mes == 0:
        return CERO
    dentro_inicio = max(lec.inicio, mes, desde)
    dentro_fin = min(lec.fin, mes_siguiente(mes), hasta)
    dias_dentro = max((dentro_fin - dentro_inicio).days, 0)
    if dias_dentro == dias_del_mes:
        return parte
    return (parte * dias_dentro / dias_del_mes).quantize(Decimal("0.0001"))
