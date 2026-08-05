"""`CapexTableLayout` · el diseño de la tabla de CAPEX, en un solo sitio.

`[REQ]` P-31. La **tabla nativa del informe** y la **hoja `CAPEX` del Excel
exportado** consumen esta misma estructura. Sin ella, en seis meses el PPTX y el
Excel que viajan en el mismo correo tendrían columnas distintas y nadie se
daría cuenta hasta que lo notase un cliente. Hay una prueba de contrato que
falla si alguien añade una columna en un solo generador.

**La estructura de esta tabla se ha verificado sobre el render real de la
plantilla del cliente**, no solo sobre los registros de texto del metarchivo.
Ver `docs/20-poc-pptx.md` §20.3: el render destapó dos columnas (`No.` y
`Group`) que la lectura de texto no daba, y un orden distinto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum


class Alineacion(StrEnum):
    IZQUIERDA = "left"
    CENTRO = "center"
    DERECHA = "right"


@dataclass(frozen=True, slots=True)
class Columna:
    key: str
    titulo_es: str
    titulo_en: str
    ancho_in: float
    alineacion: Alineacion = Alineacion.IZQUIERDA
    #: Las columnas de plazo cuelgan de la cabecera combinada «ESTIMATED CAPEX».
    grupo: str | None = None
    es_importe: bool = False


#: Anchos medidos sobre el render de la plantilla real (9,06 in de ancho total).
COLUMNAS: tuple[Columna, ...] = (
    Columna("no", "Nº", "No.", 0.32, Alineacion.CENTRO),
    Columna("zona", "Zona afectada", "Affected area", 0.78),
    Columna("concepto", "Concepto", "Purpose", 0.90),
    Columna("descripcion", "Descripción", "Description", 1.32),
    # `Group` es el grado de riesgo. El análisis por texto no lo detectó y llevó
    # a afirmar que la tabla no llevaba riesgo; el render demostró lo contrario.
    Columna("riesgo", "Grupo", "Group", 0.55, Alineacion.CENTRO),
    Columna("comentarios", "Comentarios", "Comments", 1.90),
    Columna("corto", "Corto plazo", "Short term", 0.72, Alineacion.DERECHA, "capex", True),
    Columna("medio", "Medio plazo", "Mid term", 0.72, Alineacion.DERECHA, "capex", True),
    Columna("largo", "Largo plazo", "Long term", 0.72, Alineacion.DERECHA, "capex", True),
    Columna("mejoras", "Mejoras", "Improvements", 0.72, Alineacion.DERECHA, "capex", True),
    # [REQ] P-37 · «Otro» se muestra siempre: el Excel de trabajo la tiene y es
    # la versión más actualizada. La imagen de la plantilla estaba desfasada.
    Columna("otro", "Otro", "Other", 0.72, Alineacion.DERECHA, "capex", True),
)

TITULO_GRUPO = {"capex": ("CAPEX ESTIMADO", "ESTIMATED CAPEX")}

#: Código de horizonte → clave de columna.
HORIZONTE_A_COLUMNA = {
    "CORTO": "corto",
    "MEDIO": "medio",
    "LARGO": "largo",
    "MEJORAS": "mejoras",
    "OTRO": "otro",
}


@dataclass(frozen=True, slots=True)
class LineaCapex:
    """Una línea de CAPEX, tal como sale del modelo de datos.

    `[REQ]` P-05 · **un horizonte y un importe**. Eso no ha cambiado.

    `[REQ]` P-44 · Varias líneas pueden compartir `finding_id`: es una actuación
    **recurrente**, que hace falta ahora y otra vez más adelante. En la tabla se
    presentan como **una sola fila con varias columnas de plazo rellenas**, que
    es como aparecen en el Excel del cliente.
    """

    numero: str
    zona: str
    concepto: str
    descripcion: str
    riesgo: str
    comentarios: str
    horizonte: str
    importe: Decimal
    #: Agrupa las líneas de una misma actuación. Si es `None`, la línea va sola.
    finding_id: str | None = None


@dataclass(frozen=True, slots=True)
class Fila:
    tipo: str  # "seccion" | "dato" | "subtotal" | "total"
    celdas: dict[str, str]
    #: Solo en filas de sección: el capítulo al que pertenecen.
    capitulo: str | None = None


@dataclass(frozen=True, slots=True)
class CapexTableLayout:
    """Lo que consumen el generador de PPTX y el exportador de XLSX."""

    titulo: str
    columnas: tuple[Columna, ...]
    filas: tuple[Fila, ...]
    locale: str
    totales: dict[str, Decimal] = field(default_factory=dict)

    @property
    def ancho_total_in(self) -> float:
        return round(sum(c.ancho_in for c in self.columnas), 4)

    def titulo_columna(self, c: Columna) -> str:
        return c.titulo_es if self.locale.startswith("es") else c.titulo_en


def formatear_importe(valor: Decimal | None, locale: str = "es-ES") -> str:
    """`#.##0,00 €`. **Vacío, no «0,00 €»**, cuando no hay importe.

    Es como está en la plantilla del cliente, y distingue «no aplica» de «cero»:
    un cero explícito afirma que la actuación cuesta cero, que no es lo mismo.
    """
    if valor is None:
        return ""
    entero, _, dec = f"{valor:,.2f}".partition(".")
    if locale.startswith("es"):
        entero = entero.replace(",", ".")
        return f"{entero},{dec} €"
    return f"{entero}.{dec} €"


def construir(
    lineas: list[LineaCapex],
    *,
    capitulo: str,
    locale: str = "es-ES",
    incluir_otro: bool = True,
) -> CapexTableLayout:
    """Convierte líneas de CAPEX en el diseño de tabla, agrupadas por sección."""
    columnas = tuple(c for c in COLUMNAS if incluir_otro or c.key != "otro")
    titulo = (
        f"VALORACIÓN DE LAS ACTUACIONES NECESARIAS EN EL INMUEBLE: {capitulo.upper()}"
        if locale.startswith("es")
        else f"ESTIMATE ASSESSMENT OF THE ACTIONS REQUIRED IN THE PROPERTY: {capitulo.upper()}"
    )

    # [REQ] P-44 · Las líneas de una misma actuación se funden en una fila. La
    # clave de agrupación es el hallazgo; sin él, cada línea va por su cuenta.
    actuaciones: list[list[LineaCapex]] = []
    por_hallazgo: dict[str, list[LineaCapex]] = {}
    for ln in lineas:
        if ln.finding_id is None:
            actuaciones.append([ln])
        elif ln.finding_id in por_hallazgo:
            por_hallazgo[ln.finding_id].append(ln)
        else:
            grupo = [ln]
            por_hallazgo[ln.finding_id] = grupo
            actuaciones.append(grupo)

    por_seccion: dict[str, list[list[LineaCapex]]] = {}
    for grupo in actuaciones:
        por_seccion.setdefault(grupo[0].zona or "GENERAL", []).append(grupo)

    filas: list[Fila] = []
    totales: dict[str, Decimal] = {c.key: Decimal(0) for c in columnas if c.es_importe}

    for i, (seccion, grupo) in enumerate(sorted(por_seccion.items()), 1):
        subtotal = {c.key: Decimal(0) for c in columnas if c.es_importe}
        for actuacion in grupo:
            for ln in actuacion:
                col = HORIZONTE_A_COLUMNA.get(ln.horizonte)
                if col in subtotal:
                    subtotal[col] += ln.importe
                    totales[col] += ln.importe

        filas.append(
            Fila(
                tipo="seccion",
                capitulo=seccion,
                celdas={
                    "no": f"{i}.",
                    "zona": seccion.upper(),
                    **{k: formatear_importe(v or None, locale) for k, v in subtotal.items()},
                },
            )
        )
        for j, actuacion in enumerate(grupo, 1):
            # Una actuación = una fila, aunque tenga varias líneas [REQ] P-44.
            # Los datos descriptivos los aporta la primera; los importes, todas.
            cabeza = actuacion[0]
            importes: dict[str, Decimal] = {}
            for ln in actuacion:
                col = HORIZONTE_A_COLUMNA.get(ln.horizonte)
                if col:
                    importes[col] = importes.get(col, Decimal(0)) + ln.importe
            filas.append(
                Fila(
                    tipo="dato",
                    celdas={
                        "no": f"{i}.{j}",
                        "zona": cabeza.zona,
                        "concepto": cabeza.concepto,
                        "descripcion": cabeza.descripcion,
                        "riesgo": cabeza.riesgo,
                        "comentarios": cabeza.comentarios,
                        **{
                            c.key: formatear_importe(importes.get(c.key), locale)
                            for c in columnas
                            if c.es_importe
                        },
                    },
                )
            )

    filas.append(
        Fila(
            tipo="total",
            celdas={
                "no": "",
                "zona": "TOTAL" if locale.startswith("es") else "TOTAL",
                **{k: formatear_importe(v or None, locale) for k, v in totales.items()},
            },
        )
    )
    return CapexTableLayout(
        titulo=titulo, columnas=columnas, filas=tuple(filas), locale=locale, totales=totales
    )


def particionar(
    layout: CapexTableLayout, filas_por_diapositiva: int = 18
) -> list[CapexTableLayout]:
    """Parte la tabla en varias diapositivas, repitiendo la cabecera.

    `[REC]` No se parte una sección dejando una fila huérfana: si no caben al
    menos dos filas de la sección, la sección entera pasa a la diapositiva
    siguiente.
    """
    if len(layout.filas) <= filas_por_diapositiva:
        return [layout]

    trozos: list[list[Fila]] = [[]]
    for fila in layout.filas:
        actual = trozos[-1]
        if len(actual) >= filas_por_diapositiva:
            # ¿La sección en curso quedaría con una sola fila? Entonces se
            # arrastra entera al trozo siguiente.
            arrastre: list[Fila] = []
            if actual and actual[-1].tipo == "seccion":
                arrastre = [actual.pop()]
            trozos.append(arrastre)
            actual = trozos[-1]
        actual.append(fila)

    n = len(trozos)
    return [
        CapexTableLayout(
            titulo=f"{layout.titulo} ({i}/{n})" if n > 1 else layout.titulo,
            columnas=layout.columnas,
            filas=tuple(t),
            locale=layout.locale,
            totales=layout.totales if i == n else {},
        )
        for i, t in enumerate(trozos, 1)
    ]
