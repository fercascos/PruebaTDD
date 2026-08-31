"""Del snapshot del informe a lo que rellena la plantilla CAPEX.

`plantilla_capex` sabe **dónde** va cada cosa en la hoja y `vocabulario_capex`
sabe **cómo se llama** en cada idioma. Este módulo es el que traduce el
snapshot congelado a esas dos piezas, y está aparte por una razón: es el único
sitio donde el modelo de datos de la aplicación toca la plantilla del cliente.
Cuando la plantilla cambie de forma, se cambia aquí y no en el router.

`[REQ]` Se lee **solo del snapshot**, nunca de la base. Volver a generar el
Excel de un informe de hace seis meses tiene que dar el mismo fichero aunque el
catálogo se haya renombrado desde entonces.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from tdd.evidence.naming import sanear
from tdd.exports.plantilla_capex import Actuacion, Encargo
from tdd.exports.vocabulario_capex import Vocabulario, leer

#: `asset_typology.code` → lo que la plantilla escribe en «00 Datos Activo»!C16.
#: Se resuelve por el vocabulario, que lo lee del propio fichero.


def _decimal(valor: Any) -> Decimal | None:
    if valor in (None, ""):
        return None
    return Decimal(str(valor))


def encargo_de(
    snapshot: dict[str, Any], v: Vocabulario, *, activo_en_el_nombre: bool = False
) -> Encargo:
    """La cabecera que va a «00 Datos Activo».

    `[LIM]` La hoja tiene sitio para **un** activo: un nombre, una dirección,
    unas superficies y **un tipo de edificio**, que además decide qué zonas
    ofrece el desplegable. Un encargo de cartera con varios activos no cabe
    ahí. Hay dos formas de resolverlo y las dos están disponibles:

    * **Un libro por activo** —`separar_por_activo()`—, que es la buena: cada
      libro describe su edificio, con sus superficies y su tipo, y por tanto
      con las zonas que le corresponden.
    * **Un libro conjunto**, que escribe el primer activo en la cabecera y
      deja el resto sin describir. Sigue siendo lo que sale por omisión para
      no cambiarle el fichero a quien ya lo usa, y `avisos_de_cartera()` dice
      en claro lo que se está perdiendo.

    `activo_en_el_nombre` es para el primer caso. La celda está etiquetada
    «Nombre del proyecto» y en un encargo de cartera eso no basta para saber
    qué edificio se tiene delante, así que el libro de un activo escribe
    «Proyecto · Activo». La celda C5 la referencian por fórmula la cabecera de
    la hoja `CapEx` y el pie de las gráficas, de modo que el nombre se propaga
    solo al resto del libro.
    """
    proyecto = snapshot.get("project", {})
    activos = snapshot.get("assets", [])
    primero = activos[0] if activos else {}
    tipologia = str(primero.get("typology_code") or "")

    nombre = str(proyecto.get("name") or "")
    if activo_en_el_nombre and primero.get("name"):
        nombre = f"{nombre} · {primero['name']}" if nombre else str(primero["name"])

    return Encargo(
        nombre=nombre,
        direccion=str(primero.get("address_line") or primero.get("city") or "") or None,
        fecha=str(snapshot.get("generated_at") or "")[:10] or None,
        ano_construccion=primero.get("year_built"),
        superficie_parcela=_decimal(primero.get("plot_area_sqm")),
        superficie_total=_decimal(primero.get("total_built_sqm")),
        superficie_almacen=_decimal(primero.get("warehouse_area_sqm")),
        superficie_oficinas=_decimal(primero.get("office_area_sqm")),
        altura_almacen=_decimal(primero.get("warehouse_height_m")),
        tipo_edificio=v.tipo_de_edificio(tipologia) if tipologia else None,
    )


def actuaciones_de(snapshot: dict[str, Any], v: Vocabulario) -> list[Actuacion]:
    """Una `Actuacion` por hallazgo, con sus importes repartidos por plazo.

    `[REQ]` P-44 · Un hallazgo recurrente tiene varias líneas de CAPEX, una por
    plazo, y en la hoja es **una sola fila con varias columnas rellenas**. Por
    eso se agrupa por hallazgo aquí y no se vuelca línea a línea.
    """
    tipologia_de_activo = {
        a["id"]: str(a.get("typology_code") or "") for a in snapshot.get("assets", [])
    }
    por_hallazgo = {h["id"]: h for h in snapshot.get("findings", [])}

    importes: dict[Any, dict[str, Decimal]] = {}
    orden: list[Any] = []
    for linea in snapshot.get("capex_items", []):
        clave = linea["finding_id"]
        if clave not in por_hallazgo:
            continue
        if clave not in importes:
            importes[clave] = {}
            orden.append(clave)
        plazo = str(linea["time_horizon_code"])
        importes[clave][plazo] = importes[clave].get(plazo, Decimal(0)) + Decimal(
            str(linea["amount"])
        )

    # Un hallazgo sin ninguna línea de CAPEX **también sale**: es una actuación
    # detectada cuyo importe todavía no se ha estimado, y omitirla del Excel la
    # borraría del alcance sin que nadie lo decidiera.
    for clave in por_hallazgo:
        if clave not in importes:
            importes[clave] = {}
            orden.append(clave)

    salida: list[Actuacion] = []
    for clave in orden:
        h = por_hallazgo[clave]
        tipologia = tipologia_de_activo.get(h.get("asset_id"), "")
        salida.append(
            Actuacion(
                categoria=str(h.get("capex_chapter_code") or ""),
                objeto=v.objeto(str(h.get("capex_code") or "") or None),
                zona=_zona(v, str(h.get("zone_code") or ""), tipologia),
                descripcion=str(h.get("title") or ""),
                riesgo=v.riesgo(str(h.get("risk_code") or "") or None),
                comentarios=str(h.get("comments") or "") or None,
                importes=importes[clave],
                concepto=v.concepto(str(h.get("concept_code") or "") or None),
                recuperable=v.recuperable(str(h.get("tenant_recoverable") or "") or None),
            )
        )
    return salida


def _zona(v: Vocabulario, codigo: str, tipologia: str) -> str | None:
    """La etiqueta de la zona, o `None` si la plantilla no la ofrece.

    `[LIM]` La plantilla lista zonas **por tipo de edificio**: «Almacén» existe
    en industrial y no en oficinas. Un hallazgo cuya zona no está en la lista de
    su tipología deja la celda vacía en vez de escribir un valor que el
    desplegable rechazaría y las tablas dinámicas dejarían fuera.
    """
    if not codigo or not tipologia:
        return None
    try:
        return v.zona(codigo, tipologia)
    except KeyError:
        return None


def preparar(
    snapshot: dict[str, Any], *, idioma: str = "es", activo_en_el_nombre: bool = False
) -> tuple[Encargo, list[Actuacion]]:
    v = leer(idioma)
    return (
        encargo_de(snapshot, v, activo_en_el_nombre=activo_en_el_nombre),
        actuaciones_de(snapshot, v),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Carteras: un libro por activo
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Parte:
    """El trozo del encargo que le corresponde a un activo.

    `snapshot` es un snapshot completo y válido —mismos catálogos, misma fecha,
    mismo proyecto— recortado a un solo activo. Se le pasa a `preparar()` igual
    que el entero, así que la plantilla se rellena por el mismo camino y no hay
    una segunda ruta de código que pueda divergir.
    """

    #: `None` solo en la parte de los huérfanos, abajo.
    asset_id: str | None
    nombre: str
    #: `asset_code`, si lo tiene. Va al nombre del fichero antes que el nombre.
    codigo: str | None
    snapshot: dict[str, Any]
    #: Hallazgos cuyo activo ya no está en el encargo. Ver `separar_por_activo`.
    huerfana: bool = False

    @property
    def actuaciones(self) -> int:
        return len(self.snapshot.get("findings", []))

    def nombre_de_fichero(self, prefijo: str) -> str:
        """`CAPEX_2026-014_NaveA.xlsx`. ASCII, sin barras y sin colisiones.

        Se sanea con la misma función que los nombres de fotografía: un activo
        llamado «Nave A / B» rompería la ruta dentro del ZIP, y `CON` es un
        nombre reservado en Windows que impide descomprimirlo entero.
        """
        etiqueta = sanear(self.codigo or self.nombre) or "activo"
        return f"{prefijo}_{etiqueta}.xlsx"


def separar_por_activo(snapshot: dict[str, Any]) -> list[Parte]:
    """Parte el encargo en un snapshot por activo, **sin perder nada**.

    `[REQ]` Es lo que permite entregar el CAPEX «separado por activo»: la
    plantilla del cliente describe un edificio —un nombre, unas superficies y
    un tipo que decide qué zonas ofrece el desplegable—, así que una cartera de
    tres naves son tres libros, no uno con tres cabeceras imposibles.

    Separar arregla de paso dos cosas que el libro conjunto hacía mal:

    * **La zona.** `_zona()` deja la celda vacía cuando la zona no existe para
      la tipología del activo. En un libro conjunto de activos de tipos
      distintos eso vaciaba zonas correctas; aquí cada libro lleva su tipo.
    * **La cabida.** La plantilla admite diez actuaciones por bloque. Repartidas
      entre tres activos son diez por activo, no diez entre los tres.

    Los activos **sin ninguna actuación también salen**, con su parte vacía:
    quien llama decide si genera su libro o lo declara, pero no se entera por
    omisión. Y los hallazgos cuyo activo ya no está en el encargo —se borró
    después de registrarlos— se agrupan en una última parte marcada
    `huerfana`, porque desaparecer del Excel sin que nadie lo decida es
    exactamente el fallo que no se detecta hasta que alguien suma a mano.
    """
    activos = snapshot.get("assets", [])
    hallazgos = snapshot.get("findings", [])
    lineas = snapshot.get("capex_items", [])

    por_activo: dict[str, list[dict[str, Any]]] = {str(a["id"]): [] for a in activos}
    huerfanos: list[dict[str, Any]] = []
    for h in hallazgos:
        clave = str(h.get("asset_id") or "")
        if clave in por_activo:
            por_activo[clave].append(h)
        else:
            huerfanos.append(h)

    def recorte(
        activos_de_la_parte: list[dict[str, Any]], suyos: list[dict[str, Any]]
    ) -> dict[str, Any]:
        ids = {h["id"] for h in suyos}
        return {
            **snapshot,
            "assets": activos_de_la_parte,
            "findings": suyos,
            "capex_items": [linea for linea in lineas if linea["finding_id"] in ids],
        }

    partes = [
        Parte(
            asset_id=str(a["id"]),
            nombre=str(a.get("name") or ""),
            codigo=str(a.get("asset_code") or "") or None,
            snapshot=recorte([a], por_activo[str(a["id"])]),
        )
        for a in activos
    ]
    if huerfanos:
        partes.append(
            Parte(
                asset_id=None,
                nombre="Sin activo en el encargo",
                codigo=None,
                snapshot=recorte([], huerfanos),
                huerfana=True,
            )
        )
    return partes


def avisos_de_cartera(snapshot: dict[str, Any]) -> list[str]:
    """Lo que el libro **conjunto** no puede representar, dicho en claro.

    No bloquea nada: el Excel sale igual y es útil. Lo que no puede pasar es
    que quien lo abre no sepa que la cabecera describe solo uno de los activos.
    Desde que existe la descarga separada por activo, cada aviso dice también
    cuál es la salida, que es la mitad que faltaba: un aviso sin remedio se lee
    una vez y se ignora siempre.
    """
    activos = snapshot.get("assets", [])
    avisos: list[str] = []
    if len(activos) > 1:
        nombres = ", ".join(str(a.get("name") or "") for a in activos[1:])
        avisos.append(
            f"La hoja describe en su cabecera el activo «{activos[0].get('name')}». "
            f"El encargo tiene {len(activos)}: {nombres} salen en las filas de "
            "actuaciones pero no en los datos del edificio. Para que cada uno lleve "
            "su cabecera, descargue el CAPEX separado por activo."
        )
    tipologias = {str(a.get("typology_code") or "") for a in activos}
    if len(tipologias) > 1:
        avisos.append(
            "Los activos del encargo no son todos del mismo tipo de edificio, y la "
            "plantilla ofrece una lista de zonas distinta para cada uno: alguna zona "
            "puede quedar en blanco. Separado por activo no ocurre, porque cada libro "
            "lleva el tipo de edificio del suyo."
        )
    return avisos
