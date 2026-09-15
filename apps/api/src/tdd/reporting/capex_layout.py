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

#: Cómo reparte la plantilla del cliente sus **dos** tablas de detalle de obra.
#:
#: `[REQ]` No es una invención: es la división que su propio Full Report ya hace
#: en la sección 04, «ANÁLISIS TÉCNICO · ARQUITECTURA» frente a «ANÁLISIS TÉCNICO
#: · INSTALACIONES», y con estos mismos capítulos. La tabla de la diapositiva 55
#: dice «…IN THE PROPERTY: ARCHITECTURE» y la de la 57, «…: INSTALLATIONS».
BLOQUES_DE_OBRA: dict[str, frozenset[str]] = {
    "arquitectura": frozenset(f"HC.H{n:02d}" for n in range(1, 8)),
    "instalaciones": frozenset(f"HC.H{n:02d}" for n in range(8, 16)),
}

NOMBRE_DE_BLOQUE = {
    "arquitectura": ("ARQUITECTURA", "ARCHITECTURE"),
    "instalaciones": ("INSTALACIONES", "INSTALLATIONS"),
}

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
    #: El **código** del capítulo, además de su nombre: es lo que reparte la
    #: línea entre la tabla de arquitectura y la de instalaciones. Por nombre no
    #: se puede, porque el nombre se traduce y el cliente puede renombrarlo.
    capitulo_code: str = ""
    #: `score` del nivel de riesgo, para ordenar el resumen de mayor a menor.
    riesgo_orden: int = 0


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
    #: Celdas de una fila de datos que van sombreadas como si fueran cabecera.
    #: En los resúmenes es la columna del rótulo —«Extremo», «Cubierta»—, que la
    #: plantilla pinta en gris con los importes encima de blanco.
    destacadas: frozenset[str] = frozenset()


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


# ─────────────────────────────────────────────────────────────────────────────
#  Los resúmenes de la sección 07
#
#  `[REQ]` La sección 07 de la plantilla del cliente no tiene una tabla: tiene
#  **cinco**. La de detalle, partida en obra de arquitectura y de instalaciones;
#  la matriz de riesgo por plazo que va detrás de cada una; el resumen por
#  capítulo; y el presupuesto de costes duros y blandos. Estaban las cinco
#  pegadas desde Excel y se quedaban como imagen: números de otro proyecto
#  impresos en un informe firmado.
# ─────────────────────────────────────────────────────────────────────────────


#: Las columnas de importe de los resúmenes, con el mismo reparto de colores y
#: el mismo orden que la tabla de detalle. Se derivan de `COLUMNAS` para que
#: añadir un horizonte no haya que acordarse de tocarlo en cuatro sitios.
def _columnas_de_importe(ancho_in: float, *, con_total: bool = True) -> tuple[Columna, ...]:
    plazos = tuple(
        Columna(c.key, c.titulo_es, c.titulo_en, ancho_in, Alineacion.DERECHA, "capex", True)
        for c in COLUMNAS
        if c.grupo == "capex"
    )
    if not con_total:
        return plazos
    total = Columna("total", "TOTAL", "TOTAL", ancho_in + 0.1, Alineacion.DERECHA, None, True)
    return (*plazos, total)


def _titulo(clave: str, locale: str, sufijo: str = "") -> str:
    es = locale.startswith("es")
    base = {
        "riesgo": ("CAPEX POR GRADO DE RIESGO Y PLAZO", "ESTIMATED CAPEX BY GROUP AND TERM"),
        "capitulo": ("CAPEX POR CAPÍTULO", "ESTIMATED CAPEX BY CHAPTER"),
        "costes": ("RESUMEN DE PRESUPUESTO", "BUDGET SUMMARY"),
    }[clave][0 if es else 1]
    return f"{base}: {sufijo}" if sufijo else base


def _acumular(lineas: list[LineaCapex], claves: list[str]) -> dict[str, Decimal]:
    """Suma las líneas por columna de plazo, y el total de todas."""
    totales = dict.fromkeys([*claves, "total"], Decimal(0))
    for ln in lineas:
        col = HORIZONTE_A_COLUMNA.get(ln.horizonte)
        if col in totales:
            totales[col] += ln.importe
            totales["total"] += ln.importe
    return totales


def resumen_por_riesgo(
    lineas: list[LineaCapex],
    *,
    niveles: list[tuple[str, int]],
    locale: str = "es-ES",
    sufijo: str = "",
) -> CapexTableLayout:
    """La matriz «grado de riesgo × plazo» que va detrás de cada tabla de detalle.

    `niveles` es el catálogo de riesgo del snapshot —`(nombre, score)`—, no los
    niveles que aparezcan en las líneas: la plantilla enseña **los cuatro
    siempre**, y un proyecto sin nada extremo tiene que poder decir que no tiene
    nada extremo. Con solo los presentes, la fila desaparecería y quien lee la
    tabla no sabría si es que no hay o es que se olvidó.
    """
    columnas = (Columna("riesgo", "Riesgo", "Group", 1.40), *_columnas_de_importe(0.80))
    claves = [c.key for c in columnas if c.es_importe and c.key != "total"]

    por_nombre: dict[str, list[LineaCapex]] = {}
    for ln in lineas:
        por_nombre.setdefault(ln.riesgo, []).append(ln)

    filas: list[Fila] = []
    for nombre, _ in sorted(niveles, key=lambda n: -n[1]):
        importes = _acumular(por_nombre.pop(nombre, []), claves)
        filas.append(
            Fila(
                tipo="dato",
                destacadas=frozenset({"riesgo"}),
                celdas={
                    "riesgo": nombre,
                    **{k: formatear_importe(v or None, locale) for k, v in importes.items()},
                },
            )
        )

    # Un riesgo que no está en el catálogo no se descarta: sale con su nombre al
    # final. Descartarlo cuadraría la tabla restando un importe sin decirlo.
    for nombre in sorted(por_nombre):
        importes = _acumular(por_nombre[nombre], claves)
        filas.append(
            Fila(
                tipo="dato",
                destacadas=frozenset({"riesgo"}),
                celdas={
                    "riesgo": nombre or SIN_CLASIFICAR[locale_corto(locale)],
                    **{k: formatear_importe(v or None, locale) for k, v in importes.items()},
                },
            )
        )

    totales = _acumular(lineas, claves)
    filas.append(
        Fila(
            tipo="total",
            celdas={
                "riesgo": "TOTAL",
                **{k: formatear_importe(v or None, locale) for k, v in totales.items()},
            },
        )
    )
    return CapexTableLayout(
        titulo=_titulo("riesgo", locale, sufijo),
        columnas=columnas,
        filas=tuple(filas),
        locale=locale,
        totales=totales,
    )


def resumen_por_capitulo(lineas: list[LineaCapex], *, locale: str = "es-ES") -> CapexTableLayout:
    """Una fila por capítulo, con su total y su desglose por plazo.

    Es la tabla de arriba de la diapositiva 59. Recorre **todos** los capítulos
    con importe, sean de obra o no: el que no cabe en las dos tablas de detalle
    —un coste blando, un imprevisto— aparece aquí, que es donde se ve que el
    presupuesto es mayor que la suma de las dos tablas anteriores.
    """
    columnas = (
        Columna("no", "Nº", "No.", 0.35, Alineacion.CENTRO),
        Columna("capitulo", "Capítulo", "Chapter", 2.40),
        *_columnas_de_importe(0.85),
    )
    claves = [c.key for c in columnas if c.es_importe and c.key != "total"]
    sin_clasificar = SIN_CLASIFICAR[locale_corto(locale)]

    por_capitulo: dict[str, list[LineaCapex]] = {}
    for ln in lineas:
        por_capitulo.setdefault(ln.capitulo or sin_clasificar, []).append(ln)

    filas: list[Fila] = []
    for i, capitulo in enumerate(sorted(por_capitulo), 1):
        importes = _acumular(por_capitulo[capitulo], claves)
        filas.append(
            Fila(
                tipo="dato",
                destacadas=frozenset({"no", "capitulo"}),
                celdas={
                    "no": f"{i}.",
                    "capitulo": capitulo,
                    **{k: formatear_importe(v or None, locale) for k, v in importes.items()},
                },
            )
        )

    totales = _acumular(lineas, claves)
    filas.append(
        Fila(
            tipo="total",
            celdas={
                "no": "",
                "capitulo": "TOTAL",
                **{k: formatear_importe(v or None, locale) for k, v in totales.items()},
            },
        )
    )
    return CapexTableLayout(
        titulo=_titulo("capitulo", locale),
        columnas=columnas,
        filas=tuple(filas),
        locale=locale,
        totales=totales,
    )


#: Qué columnas de plazo son «mejora» y cuáles son CAPEX propiamente dicho, en
#: el resumen de presupuesto. La plantilla separa las dos cosas en dos columnas
#: porque una mejora no es una obligación: se negocia aparte.
CLAVES_DE_MEJORA = ("mejoras",)


def resumen_de_costes(lineas: list[LineaCapex], *, locale: str = "es-ES") -> CapexTableLayout:
    """Costes duros, costes blandos y total, como la diapositiva 60.

    `[LIM]` El **coste duro va sin desglose**, con una sola línea de total: su
    desglose por capítulo es la tabla de la diapositiva anterior y repetirlo
    aquí solo alargaría la página. Los demás tipos de coste sí se desglosan por
    capítulo, que es donde la plantilla enseña los honorarios y las tasas.

    `[SUP]` La plantilla del cliente lista **siete** líneas de coste blando
    —dirección facultativa, DEO, project monitoring, PRL, ECLU, ICIO y otras
    licencias—. Nuestro árbol tiene cuatro capítulos de coste blando y **no**
    esos siete conceptos, así que se enseñan los nuestros: inventar sus siete
    etiquetas y repartir importes entre ellas sería fabricar un desglose.
    """
    es = locale.startswith("es")
    columnas = (
        Columna("concepto", "Concepto", "Item", 3.60),
        Columna("capex", "CAPEX", "CAPEX", 1.40, Alineacion.DERECHA, None, True),
        Columna("mejoras", "Mejoras", "Improvements", 1.40, Alineacion.DERECHA, None, True),
        Columna("total", "TOTAL", "TOTAL", 1.40, Alineacion.DERECHA, None, True),
    )
    sin_clasificar = SIN_CLASIFICAR[locale_corto(locale)]

    def _partir(grupo: list[LineaCapex]) -> dict[str, Decimal]:
        """Separa mejora de CAPEX. Un plazo desconocido cuenta como CAPEX."""
        salida = {"capex": Decimal(0), "mejoras": Decimal(0), "total": Decimal(0)}
        for ln in grupo:
            col = HORIZONTE_A_COLUMNA.get(ln.horizonte)
            destino = "mejoras" if col in CLAVES_DE_MEJORA else "capex"
            salida[destino] += ln.importe
            salida["total"] += ln.importe
        return salida

    por_tipo: dict[str, dict[str, list[LineaCapex]]] = {}
    for ln in lineas:
        por_tipo.setdefault(ln.tipo_de_coste or sin_clasificar, {}).setdefault(
            ln.capitulo or sin_clasificar, []
        ).append(ln)

    def _celdas(importes: dict[str, Decimal]) -> dict[str, str]:
        return {k: formatear_importe(v or None, locale) for k, v in importes.items()}

    filas: list[Fila] = []
    for tipo in sorted(por_tipo):
        capitulos = por_tipo[tipo]
        del_tipo = _partir([ln for grupo in capitulos.values() for ln in grupo])
        filas.append(
            Fila(
                tipo="seccion",
                nivel=1,
                capitulo=tipo,
                celdas={"concepto": tipo.upper(), **_celdas(del_tipo)},
            )
        )
        # El coste duro se queda en su línea de total: su desglose es la tabla
        # por capítulo de la diapositiva anterior.
        if _es_coste_duro(capitulos):
            continue
        for capitulo in sorted(capitulos):
            filas.append(
                Fila(
                    tipo="dato",
                    celdas={"concepto": capitulo, **_celdas(_partir(capitulos[capitulo]))},
                )
            )

    totales = _partir(lineas)
    filas.append(
        Fila(
            tipo="total",
            celdas={
                "concepto": "TOTAL PRESUPUESTO (SIN IVA)" if es else "TOTAL BUDGET (W/O VAT)",
                **_celdas(totales),
            },
        )
    )
    return CapexTableLayout(
        titulo=_titulo("costes", locale),
        columnas=columnas,
        filas=tuple(filas),
        locale=locale,
        totales=totales,
    )


def _es_coste_duro(capitulos: dict[str, list[LineaCapex]]) -> bool:
    """¿Este tipo de coste es el de obra? Se mira por el **código**, no por el
    nombre, que se traduce y el cliente puede cambiar."""
    return any(
        ln.capitulo_code.startswith("HC.")
        for grupo in capitulos.values()
        for ln in grupo
        if ln.capitulo_code
    )


def del_bloque(lineas: list[LineaCapex], bloque: str) -> list[LineaCapex]:
    """Las líneas de obra de un bloque: arquitectura o instalaciones."""
    codigos = BLOQUES_DE_OBRA[bloque]
    return [ln for ln in lineas if ln.capitulo_code in codigos]


def fuera_de_los_bloques(lineas: list[LineaCapex]) -> list[LineaCapex]:
    """Las de obra que **no caen en ninguno de los dos bloques**.

    No son las de coste blando —esas tienen su sitio en el resumen de
    presupuesto— sino capítulos de obra que alguien ha añadido al árbol después
    de escribirse este reparto. Se devuelven para avisar: sumarían en los
    resúmenes y no aparecerían en ninguna tabla de detalle.
    """
    conocidos = BLOQUES_DE_OBRA["arquitectura"] | BLOQUES_DE_OBRA["instalaciones"]
    return [
        ln
        for ln in lineas
        if ln.capitulo_code.startswith("HC.") and ln.capitulo_code not in conocidos
    ]


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
