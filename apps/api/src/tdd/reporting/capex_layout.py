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


#: Anchos medidos sobre el render de la plantilla real. La diapositiva es
#: **10 × 7,5 in (4:3)**, así que la tabla dispone de 9,37 in y ni uno más.
#:
#: `[REQ]` El desglose es el de la plantilla CAPEX DDT vigente, con una
#: diferencia deliberada: **el tipo de coste y el capítulo no son columnas, son
#: filas de sección.** En la hoja de Excel se repiten en cada fila porque allí
#: sobra ancho y las tablas dinámicas los necesitan en columna; en una
#: diapositiva de 4:3 esas dos columnas se comerían 1,7 in para repetir el mismo
#: texto quince veces seguidas. La plantilla ya los enseña como cabecera de
#: bloque —«HARD COSTS», «H01.Estructura»—, así que la tabla del informe hace lo
#: mismo y gasta el ancho en lo que cambia de fila a fila.
COLUMNAS: tuple[Columna, ...] = (
    Columna("no", "Nº", "No.", 0.30, Alineacion.CENTRO),
    Columna("objeto", "Objeto", "Item", 0.84),
    Columna("zona", "Zona afectada", "Affected area", 0.66),
    Columna("descripcion", "Descripción", "Description", 1.22),
    # `Group` es el grado de riesgo. El análisis por texto no lo detectó y llevó
    # a afirmar que la tabla no llevaba riesgo; el render demostró lo contrario.
    Columna("riesgo", "Grupo", "Group", 0.44, Alineacion.CENTRO),
    Columna("comentarios", "Comentarios", "Comments", 1.26),
    Columna("concepto", "Concepto", "Purpose", 0.60),
    Columna("recuperable", "Recup.", "Recov.", 0.42, Alineacion.CENTRO),
    Columna("corto", "Corto plazo", "Short term", 0.58, Alineacion.DERECHA, "capex", True),
    Columna("medio", "Medio plazo", "Mid term", 0.58, Alineacion.DERECHA, "capex", True),
    Columna("largo", "Largo plazo", "Long term", 0.58, Alineacion.DERECHA, "capex", True),
    Columna("mejoras", "Mejoras", "Improvements", 0.58, Alineacion.DERECHA, "capex", True),
    # [REQ] P-37 · «Otro» se muestra siempre: el Excel de trabajo la tiene y es
    # la versión más actualizada. La imagen de la plantilla estaba desfasada.
    Columna("otro", "Otro", "Other", 0.58, Alineacion.DERECHA, "capex", True),
    # El TOTAL de la fila. La plantilla lo lleva en la columna O y es lo que
    # mira quien lee: sin él hay que sumar cinco casillas con la vista.
    Columna("total", "TOTAL", "TOTAL", 0.62, Alineacion.DERECHA, None, True),
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
    #: `[REQ]` Los tres niveles del árbol de códigos, como en la plantilla. Los
    #: dos primeros agrupan —salen como filas de sección— y el tercero es una
    #: columna. Van con valor por defecto para no romper a quien construya la
    #: línea sin ellos: una tabla sin capítulo se agrupa bajo «Sin clasificar»,
    #: que es visible, en vez de repartir las filas en silencio.
    tipo_de_coste: str = ""
    capitulo: str = ""
    objeto: str = ""
    #: «SI» / «NO» / «N.A.», tal como lo escribe la plantilla.
    recuperable: str = ""


#: Dónde caen las actuaciones a las que les falta el tipo de coste o el
#: capítulo. Se agrupan bajo un rótulo **visible**: repartirlas en silencio
#: entre las demás secciones es cómo se pierde una actuación en una tabla.
SIN_CLASIFICAR = {"es": "Sin clasificar", "en": "Unclassified"}


def locale_corto(locale: str) -> str:
    return "es" if locale.startswith("es") else "en"


@dataclass(frozen=True, slots=True)
class Fila:
    tipo: str  # "seccion" | "dato" | "subtotal" | "total"
    celdas: dict[str, str]
    #: Solo en filas de sección: el capítulo al que pertenecen.
    capitulo: str | None = None
    #: Solo en filas de sección: 1 = tipo de coste, 2 = capítulo. Lo usa el
    #: renderizador para darles peso distinto, como hace la plantilla.
    nivel: int = 0


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

    # `[REQ]` Dos niveles de agrupación, los mismos que la hoja `CapEx` de la
    # plantilla: primero el tipo de coste —«HARD COSTS»— y dentro el capítulo
    # —«H01.Estructura»—. Antes se agrupaba por zona, que no está en la
    # plantilla y hacía que dos actuaciones del mismo sistema saliesen
    # separadas por estar en plantas distintas.
    sin_clasificar = SIN_CLASIFICAR[locale_corto(locale)]
    por_tipo: dict[str, dict[str, list[list[LineaCapex]]]] = {}
    for grupo in actuaciones:
        cabeza = grupo[0]
        tipo = cabeza.tipo_de_coste or sin_clasificar
        cap = cabeza.capitulo or sin_clasificar
        por_tipo.setdefault(tipo, {}).setdefault(cap, []).append(grupo)

    filas: list[Fila] = []
    claves_importe = [c.key for c in columnas if c.es_importe]
    totales: dict[str, Decimal] = dict.fromkeys(claves_importe, Decimal(0))

    def _formateados(importes: dict[str, Decimal], locale: str) -> dict[str, str]:
        """Las cinco columnas de importe, ya en texto. Un cero es «—», no «0,00»."""
        return {clave: formatear_importe(v or None, locale) for clave, v in importes.items()}

    def _sumar(destino: dict[str, Decimal], actuacion: list[LineaCapex]) -> None:
        for ln in actuacion:
            col = HORIZONTE_A_COLUMNA.get(ln.horizonte)
            if col in destino:
                destino[col] += ln.importe
                destino["total"] += ln.importe

    for i, tipo in enumerate(sorted(por_tipo), 1):
        capitulos = por_tipo[tipo]
        del_tipo = dict.fromkeys(claves_importe, Decimal(0))
        for grupos in capitulos.values():
            for actuacion in grupos:
                _sumar(del_tipo, actuacion)
        for clave, v in del_tipo.items():
            totales[clave] += v

        filas.append(
            Fila(
                tipo="seccion",
                capitulo=tipo,
                nivel=1,
                celdas={
                    "no": f"{i}.",
                    "objeto": tipo.upper(),
                    **_formateados(del_tipo, locale),
                },
            )
        )

        for j, capitulo_actual in enumerate(sorted(capitulos), 1):
            grupos = capitulos[capitulo_actual]
            del_capitulo = dict.fromkeys(claves_importe, Decimal(0))
            for actuacion in grupos:
                _sumar(del_capitulo, actuacion)

            filas.append(
                Fila(
                    tipo="seccion",
                    capitulo=capitulo_actual,
                    nivel=2,
                    celdas={
                        "no": f"{i}.{j}",
                        "objeto": capitulo_actual,
                        **_formateados(del_capitulo, locale),
                    },
                )
            )
            for k, actuacion in enumerate(grupos, 1):
                # Una actuación = una fila, aunque tenga varias líneas [REQ]
                # P-44. Los datos descriptivos los aporta la primera; los
                # importes, todas.
                cabeza = actuacion[0]
                importes = dict.fromkeys(claves_importe, Decimal(0))
                _sumar(importes, actuacion)
                filas.append(
                    Fila(
                        tipo="dato",
                        celdas={
                            "no": f"{i}.{j}.{k}",
                            "objeto": cabeza.objeto,
                            "zona": cabeza.zona,
                            "descripcion": cabeza.descripcion,
                            "riesgo": cabeza.riesgo,
                            "comentarios": cabeza.comentarios,
                            "concepto": cabeza.concepto,
                            "recuperable": cabeza.recuperable,
                            **{
                                clave: formatear_importe(importes.get(clave) or None, locale)
                                for clave in claves_importe
                            },
                        },
                    )
                )

    filas.append(
        Fila(
            tipo="total",
            celdas={
                "no": "",
                "objeto": "TOTAL",
                **_formateados(totales, locale),
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
