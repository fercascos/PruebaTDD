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

from decimal import Decimal
from typing import Any

from tdd.exports.plantilla_capex import Actuacion, Encargo
from tdd.exports.vocabulario_capex import Vocabulario, leer

#: `asset_typology.code` → lo que la plantilla escribe en «00 Datos Activo»!C16.
#: Se resuelve por el vocabulario, que lo lee del propio fichero.


def _decimal(valor: Any) -> Decimal | None:
    if valor in (None, ""):
        return None
    return Decimal(str(valor))


def encargo_de(snapshot: dict[str, Any], v: Vocabulario) -> Encargo:
    """La cabecera que va a «00 Datos Activo».

    `[LIM]` La hoja tiene sitio para **un** activo: un nombre, una dirección,
    unas superficies y **un tipo de edificio**, que además decide qué zonas
    ofrece el desplegable. Un encargo de cartera con varios activos no cabe
    ahí, así que se escribe el primero y el resto viaja en las filas de
    actuaciones, que sí llevan su zona. `avisos_de_cartera()` lo declara.
    """
    proyecto = snapshot.get("project", {})
    activos = snapshot.get("assets", [])
    primero = activos[0] if activos else {}
    tipologia = str(primero.get("typology_code") or "")

    return Encargo(
        nombre=str(proyecto.get("name") or ""),
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


def preparar(snapshot: dict[str, Any], *, idioma: str = "es") -> tuple[Encargo, list[Actuacion]]:
    v = leer(idioma)
    return encargo_de(snapshot, v), actuaciones_de(snapshot, v)


def avisos_de_cartera(snapshot: dict[str, Any]) -> list[str]:
    """Lo que la hoja no puede representar de este encargo, dicho en claro.

    No bloquea nada: el Excel sale igual y es útil. Lo que no puede pasar es
    que quien lo abre no sepa que la cabecera describe solo uno de los activos.
    """
    activos = snapshot.get("assets", [])
    avisos: list[str] = []
    if len(activos) > 1:
        nombres = ", ".join(str(a.get("name") or "") for a in activos[1:])
        avisos.append(
            f"La hoja describe en su cabecera el activo «{activos[0].get('name')}». "
            f"El encargo tiene {len(activos)}: {nombres} salen en las filas de "
            "actuaciones pero no en los datos del edificio."
        )
    tipologias = {str(a.get("typology_code") or "") for a in activos}
    if len(tipologias) > 1:
        avisos.append(
            "Los activos del encargo no son todos del mismo tipo de edificio, y la "
            "plantilla ofrece una lista de zonas distinta para cada uno: alguna zona "
            "puede quedar en blanco."
        )
    return avisos
