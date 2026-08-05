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
    """Una línea, tal como sale del modelo de datos."""

    numero: str
    zona: str
    concepto: str
    descripcion: str
    riesgo: str
    comentarios: str
    horizonte: str
    importe: Decimal


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

    por_seccion: dict[str, list[LineaCapex]] = {}
    for ln in lineas:
        por_seccion.setdefault(ln.zona or "GENERAL", []).append(ln)

    filas: list[Fila] = []
    totales: dict[str, Decimal] = {c.key: Decimal(0) for c in columnas if c.es_importe}

    for i, (seccion, grupo) in enumerate(sorted(por_seccion.items()), 1):
        subtotal = {c.key: Decimal(0) for c in columnas if c.es_importe}
        for ln in grupo:
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
        for j, ln in enumerate(grupo, 1):
            col = HORIZONTE_A_COLUMNA.get(ln.horizonte)
            filas.append(
                Fila(
                    tipo="dato",
                    celdas={
                        "no": f"{i}.{j}",
                        "zona": ln.zona,
                        "concepto": ln.concepto,
                        "descripcion": ln.descripcion,
                        "riesgo": ln.riesgo,
                        "comentarios": ln.comentarios,
                        **{
                            c.key: (formatear_importe(ln.importe, locale) if c.key == col else "")
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
