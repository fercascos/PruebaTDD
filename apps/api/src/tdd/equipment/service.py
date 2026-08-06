"""Vida residual del equipo `[REQ]` §7 / P-15.

Lógica pura: ni base de datos ni HTTP. Se prueba sin levantar nada.

**P-15 · «La vida residual se calcula, no se teclea.»** Aquí está el cálculo, y
está aquí y no en un `SELECT` para que la API, el informe y cualquier consumidor
futuro devuelvan el mismo número.

Dos decisiones que conviene no perder de vista:

**El año de fin de vida se guarda; la vida residual, no.** Una columna generada
con la vida residual valdría el día que se escribe y mentiría a partir del 1 de
enero siguiente. Lo que no cambia es el año en que el equipo agota su vida útil;
lo que resta hasta ahí se calcula al leer.

**El plazo no se inventa.** Un equipo al que le quedan cuatro años no cae en un
«medio plazo» decidido en este módulo: cae en el horizonte `MEDIO` del catálogo
del sistema, que va de 3 a 5 años porque así lo fijó el cliente en §3.3.4.
Inventar unos umbrales propios habría producido dos verdades sobre el mismo
edificio: la del inventario y la del CAPEX.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Horizonte:
    """Un plazo del catálogo `time_horizon`, tal como está sembrado."""

    code: str
    name_es: str
    year_from: int | None
    year_to: int | None


def vida_residual(end_of_life_year: int | None, *, anio_actual: int) -> int | None:
    """Años que le quedan al equipo. `None` si no hay datos para calcularlo.

    **Puede ser negativa**, y es información, no un error: un equipo que agotó
    su vida útil hace seis años es exactamente lo que hay que ver en la lista.
    Recortarla a cero escondería la diferencia entre «vencido el año pasado» y
    «vencido hace una década», que es la que decide la urgencia.
    """
    if end_of_life_year is None:
        return None
    return end_of_life_year - anio_actual


def horizonte_de_reposicion(residual: int | None, horizontes: list[Horizonte]) -> Horizonte | None:
    """En qué plazo del catálogo cae la reposición del equipo.

    Devuelve `None` cuando no hay vida residual que situar. Un equipo **ya
    vencido** cae en el primer plazo —el más inmediato—: la reposición no está
    «en el pasado», está pendiente y es lo más urgente que hay.

    Solo se consideran los plazos con rango de años. `MEJORAS` y `OTRO` no lo
    tienen porque no son plazos temporales sino categorías de decisión del
    cliente (P-05), y meter ahí un equipo por descarte sería colocarlo en un
    cajón que significa otra cosa.
    """
    con_rango = sorted(
        (h for h in horizontes if h.year_from is not None),
        key=lambda h: h.year_from or 0,
    )
    if residual is None or not con_rango:
        return None
    if residual <= (con_rango[0].year_to or con_rango[0].year_from or 0):
        return con_rango[0]
    for h in con_rango:
        if h.year_to is None or residual <= h.year_to:
            return h
    # Más allá del último plazo: la reposición cae fuera de la ventana de
    # estudio. Decirlo con `None` es más honesto que empujarla al plazo largo.
    return None


@dataclass(frozen=True, slots=True)
class Vida:
    end_of_life_year: int | None
    remaining_life_years: int | None
    vencido: bool
    horizonte_code: str | None
    horizonte_name: str | None
    #: Frase lista para leer. Se redacta aquí para que la pantalla, la API y el
    #: informe digan lo mismo sobre el mismo equipo.
    resumen: str


SIN_DATOS = (
    "Sin año de instalación o sin vida útil esperada: no se puede calcular la vida residual."
)


def calcular_vida(
    end_of_life_year: int | None, horizontes: list[Horizonte], *, anio_actual: int
) -> Vida:
    residual = vida_residual(end_of_life_year, anio_actual=anio_actual)
    horizonte = horizonte_de_reposicion(residual, horizontes)

    if residual is None:
        resumen = SIN_DATOS
    elif residual < 0:
        resumen = f"Vida útil agotada hace {abs(residual)} año(s) ({end_of_life_year})."
    elif residual == 0:
        resumen = f"Agota su vida útil este año ({end_of_life_year})."
    else:
        resumen = f"Le quedan {residual} año(s): agota su vida útil en {end_of_life_year}."
    if horizonte is not None:
        resumen = f"{resumen} Reposición en {horizonte.name_es.lower()}."

    return Vida(
        end_of_life_year=end_of_life_year,
        remaining_life_years=residual,
        vencido=residual is not None and residual < 0,
        horizonte_code=horizonte.code if horizonte else None,
        horizonte_name=horizonte.name_es if horizonte else None,
        resumen=resumen,
    )
