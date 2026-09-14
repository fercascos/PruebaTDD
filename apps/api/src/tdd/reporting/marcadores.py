"""El catálogo de marcadores del informe `[REQ]` §17.2, regla 4.

Un marcador es `{{algo.campo}}` escrito dentro de un cuadro de texto de la
plantilla. La generación lo sustituye por su valor **conservando el formato**:
tipografía, cuerpo, color y posición son los de la plantilla, y lo único que
cambia es el texto.

## Por qué este módulo existe aparte del generador

El catálogo estaba **en tres sitios y con tres tamaños distintos**: `docs/12`
§17.2 describía unos ochenta marcadores, `generator.valores_de_marcadores`
producía dieciséis y `router.CAMPOS_DISPONIBLES` validaba esos dieciséis a mano,
copiados. Un informe que pidiera `{{finding.title}}` —que está en la
especificación desde el primer día— se quedaba con el marcador sin resolver y
nadie sabía si era un fallo de la plantilla o de la aplicación.

Ahora hay **una sola fuente**: las funciones de aquí producen los valores y
`CATALOGO` se deduce de ellas, así que la validación no puede quedarse corta
respecto a lo que se genera.

## Tres ámbitos

| Ámbito | Cuándo vale | Ejemplo |
|---|---|---|
| **Global** | En cualquier diapositiva | `{{project.name}}`, `{{capex.total}}` |
| **Del activo** | En una diapositiva que repite por activo | `{{asset.name}}` |
| **Del hallazgo** | En una que repite por hallazgo | `{{finding.title}}` |

Los de ámbito menor **tapan** a los globales: una diapositiva repetida por
activo ve su propio `{{asset.name}}`, no el del primer activo del proyecto.

`[SUP]` Fuera de una diapositiva repetida, `{{asset.*}}` sigue valiendo y
enseña **el primer activo**, que es lo que hacía la versión anterior. En un
proyecto de un solo edificio —la mayoría— es lo correcto y no obliga a marcar
nada; en uno de cartera, el aviso de generación dice cuántos activos se han
quedado fuera de esa diapositiva.

## Lo que NO sale de aquí

**Las colecciones tabuladas** —la tabla del CAPEX— no son marcadores de texto:
se insertan como tabla nativa, y viven en `capex_layout` y `pptx_table`. Meter
cuarenta filas en un cuadro de texto daría un bloque ilegible.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tdd.reporting import capex_layout as cl

#: `finding.tenant_recoverable` → lo que se lee en el informe. Es la misma
#: inversión que hace el dashboard: el enumerado contesta «¿es repercutible?» y
#: el informe dice quién paga.
PAGADOR = {
    "NO": "Lo asume la propiedad",
    "SI": "Repercutible al inquilino",
    "NA": "Sin determinar",
}

#: Los estados de la checklist documental que **son** una limitación.
LIMITAN = ("NO_DISPONIBLE", "PARCIAL", "SIN_RESPUESTA")


def _texto(valor: Any) -> str:
    """Un valor del snapshot como texto de informe. `None` es cadena vacía.

    Nunca `'None'`: un informe que imprime la palabra «None» en una diapositiva
    delante de un cliente es peor que uno con un hueco, porque el hueco se ve y
    se corrige y aquello parece un dato.
    """
    return "" if valor is None else str(valor)


def _lista(elementos: list[str], *, vineta: str = "· ") -> str:
    """Varias líneas en un solo marcador, una por elemento.

    `\\n` y no `; `: PowerPoint respeta el salto de línea dentro del párrafo, y
    una enumeración de doce limitaciones separadas por punto y coma no se lee.
    """
    return "\n".join(f"{vineta}{e}" for e in elementos if e.strip())


# ─────────────────────────────────────────────────────────────────────────────
#  Ámbito global
# ─────────────────────────────────────────────────────────────────────────────


def globales(snapshot: dict[str, Any]) -> dict[str, str]:
    """Lo que vale en cualquier diapositiva.

    Se construye **solo desde el snapshot**: si un dato no está congelado no
    puede salir en el informe, y eso es exactamente lo que se busca —un informe
    de hace seis meses tiene que poder reconstruirse igual—.
    """
    proyecto = snapshot.get("project", {})
    activos = snapshot.get("assets", [])
    hallazgos = snapshot.get("findings", [])
    totales = _totales_por_horizonte(snapshot)
    total = sum(totales.values(), Decimal("0"))

    valores: dict[str, str] = {
        "project.code": _texto(proyecto.get("internal_code")),
        "project.name": _texto(proyecto.get("name")),
        "project.status": _texto(proyecto.get("status")),
        "project.currency": _texto(proyecto.get("currency") or "EUR"),
        "project.asset_count": str(len(activos)),
        "project.finding_count": str(len(hallazgos)),
        "client.name": _texto(proyecto.get("client_name")),
        # El nombre viejo del mismo dato. Se mantiene porque puede haber
        # plantillas y mapeos que ya lo usen: retirar un marcador que alguien
        # escribió en su PPT rompe su informe sin avisar, y el coste de
        # conservarlo es una línea.
        "project.client": _texto(proyecto.get("client_name")),
        "report.generated_at": _texto(snapshot.get("generated_at")),
        "report.date": _texto(snapshot.get("generated_at"))[:10],
        "capex.total": cl.formatear_importe(total),
    }

    # Totales por horizonte, con el nombre del catálogo congelado.
    for horizonte in snapshot.get("catalogs", {}).get("time_horizons", []):
        codigo = str(horizonte["code"])
        valores[f"capex.{codigo.lower()}"] = cl.formatear_importe(totales.get(codigo, Decimal("0")))
    # Y los que aparecen en las líneas aunque el catálogo no los traiga.
    for codigo, importe in totales.items():
        valores.setdefault(f"capex.{codigo.lower()}", cl.formatear_importe(importe))

    # `[REQ]` §3.3 · Quién paga, agregado. Es de las primeras preguntas de un
    # inversor y en el informe se escribía a mano.
    por_pagador = _por_pagador(snapshot)
    for clave, importe in por_pagador.items():
        valores[f"capex.{clave}"] = cl.formatear_importe(importe)

    valores.update(_riesgo(snapshot))
    valores.update(_limitaciones(snapshot))
    valores.update(_visitas(snapshot))

    # Fuera de una diapositiva repetida, el activo es el primero. Ver el `[SUP]`
    # de la cabecera del módulo.
    if activos:
        valores.update(del_activo(snapshot, activos[0]))
    return valores


def _totales_por_horizonte(snapshot: dict[str, Any]) -> dict[str, Decimal]:
    totales: dict[str, Decimal] = {}
    for linea in snapshot.get("capex_items", []):
        codigo = str(linea["time_horizon_code"])
        totales[codigo] = totales.get(codigo, Decimal("0")) + Decimal(str(linea["amount"]))
    return totales


def _por_pagador(snapshot: dict[str, Any], asset_id: str | None = None) -> dict[str, Decimal]:
    """Los tres pagadores, siempre los tres y con ceros.

    Con ceros porque un informe que dice «repercutible: 0 €» afirma algo; uno
    que se calla no dice si es cero o si nadie lo miró.
    """
    por_hallazgo = {h["id"]: h for h in snapshot.get("findings", [])}
    salida = {"propiedad": Decimal("0"), "inquilino": Decimal("0"), "sin_determinar": Decimal("0")}
    clave = {"NO": "propiedad", "SI": "inquilino", "NA": "sin_determinar"}
    for linea in snapshot.get("capex_items", []):
        hallazgo = por_hallazgo.get(linea["finding_id"])
        if hallazgo is None:
            continue
        if asset_id is not None and str(hallazgo.get("asset_id")) != asset_id:
            continue
        donde = clave.get(str(hallazgo.get("tenant_recoverable") or "NA"), "sin_determinar")
        salida[donde] += Decimal(str(linea["amount"]))
    return salida


def _riesgo(snapshot: dict[str, Any]) -> dict[str, str]:
    """La leyenda de riesgo y el reparto por grado.

    `[REQ]` La **definición íntegra** de cada grado viaja al informe: sin ella
    «Alto» es una palabra sin criterio detrás, y las cuatro definiciones están
    escritas justo para eso.
    """
    grados = snapshot.get("catalogs", {}).get("risk_levels", [])
    leyenda = [
        f"{g['code']} · {g['name_es']}: {g.get('definition_es') or ''}".rstrip(": ") for g in grados
    ]
    por_hallazgo = {h["id"]: h for h in snapshot.get("findings", [])}
    importes: dict[str, Decimal] = {}
    for linea in snapshot.get("capex_items", []):
        hallazgo = por_hallazgo.get(linea["finding_id"])
        if hallazgo is None:
            continue
        codigo = str(hallazgo.get("risk_code") or "SIN_GRADO")
        importes[codigo] = importes.get(codigo, Decimal("0")) + Decimal(str(linea["amount"]))

    valores = {"risk.legend": _lista(leyenda)}
    for grado in grados:
        codigo = str(grado["code"])
        valores[f"risk.{codigo.lower()}"] = cl.formatear_importe(importes.get(codigo, Decimal("0")))
    return valores


def _limitaciones(snapshot: dict[str, Any]) -> dict[str, str]:
    """`[REQ]` Declarar qué no se ha podido revisar es obligación profesional.

    Las tres clases llegan juntas del snapshot y se redactan distinto, así que
    además del bloque entero hay un marcador por origen: «no nos lo dieron», «no
    nos lo contestaron» y «nos lo dieron y dice que no vale» no son lo mismo.
    """
    limitaciones = snapshot.get("limitations", [])

    def redactar(fila: dict[str, Any]) -> str:
        titulo = _texto(fila.get("title"))
        motivo = _texto(fila.get("unavailable_reason")).strip()
        return f"{titulo} — {motivo}" if motivo else titulo

    por_origen: dict[str, list[str]] = {}
    for fila in limitaciones:
        por_origen.setdefault(str(fila.get("origen") or "CHECKLIST"), []).append(redactar(fila))

    return {
        "report.limitations": _lista([redactar(f) for f in limitaciones]),
        "report.limitations_count": str(len(limitaciones)),
        "report.limitations_docs": _lista(por_origen.get("CHECKLIST", [])),
        "report.limitations_qa": _lista(por_origen.get("PREGUNTA", [])),
        "report.limitations_content": _lista(por_origen.get("DOCUMENTO", [])),
    }


def _visitas(snapshot: dict[str, Any]) -> dict[str, str]:
    visitas = snapshot.get("visits", [])
    fechas = sorted({_texto(v.get("actual_date")) for v in visitas if v.get("actual_date")})
    accesos = [_texto(v.get("access_limitations")) for v in visitas if v.get("access_limitations")]
    return {
        "visit.dates": ", ".join(fechas),
        "visit.count": str(len(visitas)),
        "visit.access_limitations": _lista(accesos),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Ámbito del activo
# ─────────────────────────────────────────────────────────────────────────────


def del_activo(snapshot: dict[str, Any], activo: dict[str, Any]) -> dict[str, str]:
    """Los marcadores de UN activo, incluido lo que le corresponde del CAPEX."""
    asset_id = str(activo.get("id"))
    suyos = [h for h in snapshot.get("findings", []) if str(h.get("asset_id")) == asset_id]
    ids = {h["id"] for h in suyos}
    total = sum(
        (
            Decimal(str(linea["amount"]))
            for linea in snapshot.get("capex_items", [])
            if linea["finding_id"] in ids
        ),
        Decimal("0"),
    )
    vacia: dict[str, Any] = {}
    visita = next(
        (v for v in snapshot.get("visits", []) if str(v.get("asset_id")) == asset_id), vacia
    )
    direccion = ", ".join(
        p for p in (_texto(activo.get("address_line")), _texto(activo.get("city"))) if p
    )
    pagador = _por_pagador(snapshot, asset_id)

    return {
        "asset.name": _texto(activo.get("name")),
        "asset.code": _texto(activo.get("asset_code")),
        "asset.typology": _texto(activo.get("typology_name")),
        "asset.address": direccion,
        "asset.city": _texto(activo.get("city")),
        "asset.year_built": _texto(activo.get("year_built")),
        "asset.year_last_refurb": _texto(activo.get("year_last_refurb")),
        "asset.total_built_sqm": _texto(activo.get("total_built_sqm")),
        "asset.plot_area_sqm": _texto(activo.get("plot_area_sqm")),
        "asset.warehouse_area_sqm": _texto(activo.get("warehouse_area_sqm")),
        "asset.office_area_sqm": _texto(activo.get("office_area_sqm")),
        "asset.warehouse_height_m": _texto(activo.get("warehouse_height_m")),
        "asset.floors_above": _texto(activo.get("floors_above")),
        "asset.floors_below": _texto(activo.get("floors_below")),
        "asset.finding_count": str(len(suyos)),
        "asset.capex_total": cl.formatear_importe(total),
        "asset.capex_propiedad": cl.formatear_importe(pagador["propiedad"]),
        "asset.capex_inquilino": cl.formatear_importe(pagador["inquilino"]),
        "asset.visit_date": _texto(visita.get("actual_date")),
        "asset.access_limitations": _texto(visita.get("access_limitations")),
        # `[REQ]` §3.2 d · El descriptivo y la valoración que escribe el gestor
        # técnico objeto a objeto. Son *los textos de la aplicación* que el
        # informe tenía que traer y no traía.
        "asset.descriptivo": _descriptivos(snapshot, asset_id, "texto"),
        "asset.valoracion": _descriptivos(snapshot, asset_id, "valoracion"),
    }


def _descriptivos(snapshot: dict[str, Any], asset_id: str, campo: str) -> str:
    """Los textos del inventario de un activo, uno por objeto y con su nombre.

    `[LIM]` Van **todos seguidos en un marcador**. Una diapositiva por objeto
    saldría de repetir sobre la colección, y para eso hace falta que la
    plantilla lo pida: aquí se ofrece el bloque, que es lo que cabe en la
    diapositiva de descripción general que tienen casi todos los informes.
    """
    lineas = []
    for fila in snapshot.get("descriptivos", []):
        if str(fila.get("asset_id")) != asset_id:
            continue
        texto = _texto(fila.get(campo)).strip()
        if texto:
            lineas.append(f"{_texto(fila.get('capex_name'))}: {texto}")
    return _lista(lineas)


# ─────────────────────────────────────────────────────────────────────────────
#  Ámbito del hallazgo
# ─────────────────────────────────────────────────────────────────────────────


def del_hallazgo(snapshot: dict[str, Any], hallazgo: dict[str, Any]) -> dict[str, str]:
    """Los marcadores de UN hallazgo, con su importe y su definición de riesgo."""
    importe = sum(
        (
            Decimal(str(linea["amount"]))
            for linea in snapshot.get("capex_items", [])
            if linea["finding_id"] == hallazgo["id"]
        ),
        Decimal("0"),
    )
    plazos = sorted(
        {
            str(linea["time_horizon_code"])
            for linea in snapshot.get("capex_items", [])
            if linea["finding_id"] == hallazgo["id"]
        }
    )
    definicion = next(
        (
            _texto(g.get("definition_es"))
            for g in snapshot.get("catalogs", {}).get("risk_levels", [])
            if str(g["code"]) == str(hallazgo.get("risk_code"))
        ),
        "",
    )
    return {
        "finding.title": _texto(hallazgo.get("title")),
        "finding.description": _texto(hallazgo.get("description")),
        "finding.comments": _texto(hallazgo.get("comments")),
        "finding.recommendation": _texto(hallazgo.get("recommendation")),
        "finding.zone": _texto(hallazgo.get("zone_name")),
        "finding.capex_code": _texto(hallazgo.get("capex_code")),
        "finding.capex_type": _texto(hallazgo.get("capex_type_name")),
        "finding.capex_chapter": _texto(hallazgo.get("capex_chapter_name")),
        "finding.capex_item": _texto(hallazgo.get("capex_item_name")),
        "finding.risk_code": _texto(hallazgo.get("risk_code")),
        "finding.risk_name": _texto(hallazgo.get("risk_name")),
        "finding.risk_definition": definicion,
        "finding.concept": _texto(hallazgo.get("concept_name")),
        "finding.amount": cl.formatear_importe(importe),
        "finding.horizons": ", ".join(plazos),
        "finding.payer": PAGADOR.get(str(hallazgo.get("tenant_recoverable") or "NA"), ""),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  El catálogo, deducido
# ─────────────────────────────────────────────────────────────────────────────

#: Las colecciones sobre las que una diapositiva puede repetirse, y de dónde
#: salen sus valores. La clave es lo que se escribe en las notas del orador:
#: `@repeat: asset`.
COLECCIONES: dict[str, tuple[str, Any]] = {
    "asset": ("assets", del_activo),
    "finding": ("findings", del_hallazgo),
}


def catalogo() -> frozenset[str]:
    """Todos los marcadores que la aplicación sabe rellenar.

    **Se deduce ejecutando las funciones sobre un snapshot de muestra**, no se
    escribe a mano. Una lista escrita a mano se queda corta el día que alguien
    añade un campo y se olvida de apuntarlo, y entonces la validación rechaza un
    marcador que el generador sí sabría resolver. Pasó: `CAMPOS_DISPONIBLES`
    tenía dieciséis nombres y `docs/12` describía ochenta.
    """
    muestra: dict[str, Any] = {
        "project": {},
        "assets": [{"id": "x"}],
        "findings": [{"id": "y", "asset_id": "x"}],
        "capex_items": [],
        "photos": [],
        "limitations": [],
        "visits": [],
        "descriptivos": [],
        "catalogs": {
            "risk_levels": [
                {"code": c, "name_es": c, "definition_es": ""} for c in ("01", "02", "03", "04")
            ],
            "time_horizons": [{"code": c} for c in ("CORTO", "MEDIO", "LARGO", "MEJORAS", "OTRO")],
        },
        "generated_at": "",
    }
    nombres = set(globales(muestra))
    nombres |= set(del_activo(muestra, muestra["assets"][0]))
    nombres |= set(del_hallazgo(muestra, muestra["findings"][0]))
    return frozenset(nombres)
