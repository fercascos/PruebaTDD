"""API del CAPEX.

Dos endpoints merecen atención:

* `POST /capex/preview-calculation` calcula **sin persistir**. Alimenta el bloque
  «Cómo se calcula» de la interfaz, que muestra la fórmula con sus operandos.
* `POST /capex-items/{id}/carry-measurement` es la **acción explícita** con la
  que el consultor traslada el resultado de la medición al importe de la línea.
  P-05b exige que sea explícita: la cascada nunca se aplica sola sobre un
  importe tecleado.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.capex.engine import CascadeConfig, apply_tax, run_cascade
from tdd.core import concurrencia as cc
from tdd.core.deps import SesionDep, UsuarioDep
from tdd.exports.plantilla_capex import Idioma

if TYPE_CHECKING:  # `capex_desde_snapshot` arrastra `openpyxl`: se importa al usarlo.
    from tdd.exports.capex_desde_snapshot import Parte

router = APIRouter(tags=["CAPEX"])


class Porcentajes(BaseModel):
    indirect_pct: Decimal = Field(ge=0)
    overhead_pct: Decimal = Field(ge=0)
    profit_pct: Decimal = Field(ge=0)
    fees_pct: Decimal = Field(ge=0)
    contingency_pct: Decimal = Field(ge=0)


class PeticionCalculo(BaseModel):
    quantity: Decimal = Field(ge=0)
    unit_price: Decimal = Field(ge=0)
    percentages: Porcentajes
    tax_pct: Decimal = Field(default=Decimal("0"), ge=0)
    rounding_mode: str = "HALF_UP"
    round_each_step: bool = True


class PeldanoCalculado(BaseModel):
    key: str
    label: str
    base_amount: Decimal
    pct: Decimal
    amount: Decimal


class ResultadoCalculo(BaseModel):
    direct_cost: Decimal
    steps: list[PeldanoCalculado]
    pem: Decimal | None
    pec: Decimal | None
    computed_base: Decimal
    tax_amount: Decimal
    total_with_tax: Decimal
    calc_version: int
    nota: str


@router.post("/capex/preview-calculation", response_model=ResultadoCalculo)
def previsualizar_calculo(cuerpo: PeticionCalculo) -> Any:
    """Calcula la cascada **sin tocar la base de datos**.

    No exige sesión de base de datos a propósito: es una función pura expuesta
    por HTTP, y el usuario puede jugar con los porcentajes sin efectos.
    """
    try:
        config = CascadeConfig.spanish_default(
            **cuerpo.percentages.model_dump(),
            rounding_mode=cuerpo.rounding_mode,
            round_each_step=cuerpo.round_each_step,
        )
        resultado = run_cascade(
            quantity=cuerpo.quantity, unit_price=cuerpo.unit_price, config=config
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    totales = apply_tax(resultado.computed_base, cuerpo.tax_pct)
    return {
        "direct_cost": resultado.direct_cost,
        "steps": [
            {
                "key": line.key.value,
                "label": line.label,
                "base_amount": line.base_amount,
                "pct": line.pct,
                "amount": line.amount,
            }
            for line in resultado.lines
        ],
        "pem": resultado.pem,
        "pec": resultado.pec,
        "computed_base": resultado.computed_base,
        "tax_amount": totales.tax_amount,
        "total_with_tax": totales.total_cost,
        "calc_version": resultado.calc_version,
        "nota": (
            "La cascada llega hasta la base imponible. El impuesto se aplica una sola vez, "
            "sobre el importe de la línea. Este cálculo no se ha guardado: para usarlo, "
            "trasládelo al importe con el botón correspondiente."
        ),
    }


class LineaCapex(BaseModel):
    id: uuid.UUID
    amount: Decimal
    tax_pct: Decimal
    tax_amount: Decimal
    total_cost: Decimal
    amount_source: str
    computed_base: Decimal | None
    time_horizon_code: str


_SELECT = (
    "SELECT ci.id, ci.amount, ci.tax_pct, ci.tax_amount, ci.total_cost, "
    "CAST(ci.amount_source AS text) AS amount_source, ci.computed_base, "
    "th.code AS time_horizon_code "
    "FROM capex_item ci JOIN time_horizon th ON th.id = ci.time_horizon_id"
)


@router.get("/projects/{project_id}/capex-items", response_model=list[LineaCapex])
def listar(project_id: uuid.UUID, s: SesionDep) -> Any:
    filas = (
        s.execute(
            text(f"{_SELECT} WHERE ci.project_id = :p ORDER BY ci.created_at"),  # noqa: S608
            {"p": project_id},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


class ResumenPorActivo(BaseModel):
    asset_id: uuid.UUID
    asset_name: str
    asset_code: str | None
    typology_name: str
    findings: int
    lines: int
    amount: Decimal
    tax_amount: Decimal
    total_cost: Decimal


@router.get(
    "/projects/{project_id}/capex/summary/by-asset",
    response_model=list[ResumenPorActivo],
)
def resumen_por_activo(project_id: uuid.UUID, s: SesionDep) -> Any:
    """`[REQ]` El CAPEX **separado por activo**, que es como se decide.

    En un encargo de cartera la pregunta que se hace el cliente no es cuánto
    suma el proyecto, sino cuánto cuesta cada edificio: es el número que entra
    en la negociación del precio de cada uno. Sin esta vista había que sumar a
    mano desde la rejilla de hallazgos, y ahí es donde aparecen los descuadres.

    Sale **un activo por fila aunque no tenga ninguna actuación**, con ceros.
    Un activo que desaparece de la tabla porque todavía no se ha visitado se
    confunde con uno que se visitó y no tenía nada, y no son lo mismo.
    """
    filas = (
        s.execute(
            text(
                "SELECT a.id AS asset_id, a.name AS asset_name, a.asset_code, "
                "t.name_es AS typology_name, "
                "count(DISTINCT f.id) AS findings, count(ci.id) AS lines, "
                "COALESCE(sum(ci.amount), 0) AS amount, "
                "COALESCE(sum(ci.tax_amount), 0) AS tax_amount, "
                "COALESCE(sum(ci.total_cost), 0) AS total_cost "
                "FROM asset a "
                "JOIN asset_typology t ON t.id = a.typology_id "
                "LEFT JOIN finding f ON f.asset_id = a.id AND f.deleted_at IS NULL "
                "LEFT JOIN capex_item ci ON ci.finding_id = f.id "
                "WHERE a.project_id = :p AND a.deleted_at IS NULL "
                "GROUP BY a.id, a.name, a.asset_code, t.name_es ORDER BY a.name"
            ),
            {"p": project_id},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


class ResumenPorHorizonte(BaseModel):
    time_horizon_code: str
    time_horizon_name: str
    lines: int
    amount: Decimal
    tax_amount: Decimal
    total_cost: Decimal


@router.get(
    "/projects/{project_id}/capex/summary/by-horizon",
    response_model=list[ResumenPorHorizonte],
)
def resumen_por_horizonte(project_id: uuid.UUID, s: SesionDep) -> Any:
    """P-05 · Con un horizonte por línea, esto es un `GROUP BY`.

    Con cinco columnas editables serían cinco sumas independientes que podrían
    descuadrar entre sí; así es imposible.

    `[REQ]` **Excluye los hallazgos borrados**, y no lo hacía. El borrado de un
    hallazgo es lógico —`deleted_at`, porque borrar del informe algo que se
    llegó a valorar deja a nadie sabiendo que existió—, así que sus líneas de
    CAPEX siguen en la tabla. Esta consulta unía `capex_item` con `time_horizon`
    sin pasar por `finding`, de modo que las contaba: el mismo encargo sumaba
    una cosa por horizonte y otra por activo, que sí lo excluía.

    No se veía porque nada ponía los dos cortes en la misma pantalla. La vista
    de resumen los pone uno debajo del otro, y ahí el descuadre lo encuentra el
    cliente con la calculadora. Hay una prueba que compara los cuatro cortes
    entre sí.
    """
    filas = (
        s.execute(
            text(
                "SELECT th.code AS time_horizon_code, th.name_es AS time_horizon_name, "
                "count(ci.id) AS lines, COALESCE(sum(ci.amount), 0) AS amount, "
                "COALESCE(sum(ci.tax_amount), 0) AS tax_amount, "
                "COALESCE(sum(ci.total_cost), 0) AS total_cost "
                "FROM time_horizon th "
                "LEFT JOIN finding f ON f.deleted_at IS NULL "
                "LEFT JOIN capex_item ci "
                "  ON ci.time_horizon_id = th.id AND ci.project_id = :p "
                "  AND ci.finding_id = f.id "
                "GROUP BY th.code, th.name_es, th.sort_order ORDER BY th.sort_order"
            ),
            {"p": project_id},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


class ResumenPorConcepto(BaseModel):
    capex_concept_code: str
    capex_concept_name: str
    findings: int
    lines: int
    amount: Decimal
    total_cost: Decimal


@router.get(
    "/projects/{project_id}/capex/summary/by-concept",
    response_model=list[ResumenPorConcepto],
)
def resumen_por_concepto(
    project_id: uuid.UUID,
    s: SesionDep,
    #: `[REQ]` Sin él, el reparto es el del **encargo entero**; con él, el de un
    #: solo edificio.
    #:
    #: Son dos preguntas distintas y las dos se hacen en la misma reunión. En
    #: una cartera, «en qué se va el dinero» agregado dice cómo se comporta el
    #: parque —si es un problema de mantenimiento diferido o de normativa—;
    #: por activo dice qué le pasa a ESE edificio, que es sobre el que se
    #: negocia el precio. Un parque con un 40 % de normativa puede tener ese
    #: 40 % concentrado en una sola nave, y agregado eso no se ve.
    asset_id: uuid.UUID | None = None,
) -> Any:
    """`[REQ]` El CAPEX por **concepto de gasto**: en qué se va el dinero.

    Es la pregunta que separa un edificio caro de uno mal mantenido. Doscientos
    mil euros de «Normativa» y doscientos mil de «Mejora» valen lo mismo en la
    hoja y significan cosas opuestas: lo primero hay que pagarlo, lo segundo se
    puede decidir. Sin este corte, el total del encargo no distingue una cosa
    de la otra.

    **Solo salen los conceptos con importe.** Los diez del catálogo con ceros
    llenarían el gráfico de porciones invisibles; los que faltan es que no hay.
    Y las líneas de un hallazgo **sin concepto** no se pierden: salen agrupadas
    como «Sin concepto», que es un dato —alguien no lo clasificó— y no un hueco.

    `[REC]` `asset_id` **solo filtra**, como en la matriz de riesgos: un activo
    de otro encargo devuelve una lista vacía en vez de un error. Es la
    convención de la casa para los filtros de lectura, y aquí además es lo
    correcto: la pantalla construye el desplegable con los activos del propio
    encargo, así que un identificador ajeno solo llega escribiendo la URL a
    mano.
    """
    filas = (
        s.execute(
            text(
                "SELECT COALESCE(cc.code, 'SIN_CONCEPTO') AS capex_concept_code, "
                "COALESCE(cc.name_es, 'Sin concepto') AS capex_concept_name, "
                "count(DISTINCT f.id) AS findings, count(ci.id) AS lines, "
                "COALESCE(sum(ci.amount), 0) AS amount, "
                "COALESCE(sum(ci.total_cost), 0) AS total_cost "
                "FROM capex_item ci "
                "JOIN finding f ON f.id = ci.finding_id AND f.deleted_at IS NULL "
                "LEFT JOIN capex_concept cc ON cc.id = f.capex_concept_id "
                "WHERE ci.project_id = :p "
                # El activo está en el HALLAZGO, no en la línea: una actuación
                # recurrente (P-44) tiene varias líneas y un solo edificio.
                "  AND (CAST(:a AS uuid) IS NULL OR f.asset_id = CAST(:a AS uuid)) "
                "GROUP BY cc.code, cc.name_es "
                # De mayor a menor: es el orden en el que se lee un reparto, y
                # el que permite doblar la cola en «Otros» sin recalcular nada.
                "ORDER BY sum(ci.amount) DESC"
            ),
            {"p": project_id, "a": str(asset_id) if asset_id else None},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


class ResumenPorCapitulo(BaseModel):
    chapter_code: str
    chapter_name: str
    findings: int
    lines: int
    amount: Decimal
    total_cost: Decimal


@router.get(
    "/projects/{project_id}/capex/summary/by-chapter",
    response_model=list[ResumenPorCapitulo],
)
def resumen_por_capitulo(project_id: uuid.UUID, s: SesionDep) -> Any:
    """El CAPEX por **capítulo** del árbol: qué parte del edificio se lleva el
    dinero.

    El capítulo es el **nivel 2** y un hallazgo puede estar codificado en el
    nivel 3, así que se sube por el árbol hasta el capítulo en vez de agrupar
    por el código del hallazgo: agrupando por el código directo, un encargo con
    hallazgos a distintos niveles saldría partido en trozos que no suman nada
    reconocible.
    """
    filas = (
        s.execute(
            text(
                "SELECT cap.code AS chapter_code, cap.name_es AS chapter_name, "
                "count(DISTINCT f.id) AS findings, count(ci.id) AS lines, "
                "COALESCE(sum(ci.amount), 0) AS amount, "
                "COALESCE(sum(ci.total_cost), 0) AS total_cost "
                "FROM capex_item ci "
                "JOIN finding f ON f.id = ci.finding_id AND f.deleted_at IS NULL "
                "JOIN capex_code cod ON cod.id = f.capex_code_id "
                # Si el hallazgo está en el nivel 3, su padre es el capítulo; si
                # ya está en el 2, es él mismo.
                "JOIN capex_code cap ON cap.id = CASE WHEN cod.level = 3 "
                "                                     THEN cod.parent_id ELSE cod.id END "
                "WHERE ci.project_id = :p "
                "GROUP BY cap.code, cap.name_es ORDER BY sum(ci.amount) DESC"
            ),
            {"p": project_id},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


@router.get(
    "/projects/{project_id}/capex/export.xlsx",
    tags=["CAPEX"],
    response_class=Response,
    responses={
        200: {
            "content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}},
            "description": "Libro con la hoja CAPEX.",
        }
    },
)
def exportar_xlsx(
    project_id: uuid.UUID,
    s: SesionDep,
    idioma: Idioma = Idioma.ES,
    asset_id: uuid.UUID | None = None,
) -> Response:
    """`[REQ]` P-31 · El botón de **exportar el CAPEX a XLSX**.

    Lo pidió el cliente para poder adjuntar el fichero en el envío que el equipo
    hace fuera de la plataforma. El generador existía y estaba probado, pero no
    había ninguna ruta que lo sirviera: el botón no habría tenido a dónde
    llamar. Se detectó recorriendo la aplicación en marcha.

    `[REQ]` **Rellena la plantilla CAPEX DDT del cliente**, no un libro
    construido a mano. Sale con sus gráficos, sus tablas dinámicas y sus
    fórmulas, y el equipo lo adjunta tal cual.

    `asset_id` acota el libro a **un activo**: su cabecera, su tipo de edificio
    —y por tanto sus zonas— y solo sus actuaciones. Sin él sale el encargo
    entero en un libro, que es lo que había y sigue siendo lo que ocurre por
    omisión. Para bajarse todos los activos de una cartera de golpe, cada uno
    en su libro, está `export.zip`.

    `[LIM]` Exporta el estado **actual** del proyecto, no una versión emitida.
    Para el CAPEX congelado de un informe ya publicado está la descarga de esa
    versión, que lee de su snapshot. El nombre del fichero lo dice.
    """
    from tdd.exports import capex_desde_snapshot as puente

    datos = _snapshot_de_trabajo(s, project_id)
    proyecto = datos["project"]
    prefijo = f"CAPEX_{proyecto.get('internal_code') or project_id}"

    if asset_id is None:
        contenido = _libro(datos, idioma, quien="El encargo")
        nombre = f"{prefijo}_actual.xlsx"
    else:
        partes = {p.asset_id: p for p in puente.separar_por_activo(datos)}
        parte = partes.get(str(asset_id))
        if parte is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "El activo no pertenece a este encargo")
        contenido = _libro(
            parte.snapshot, idioma, quien=f"El activo «{parte.nombre}»", del_activo=True
        )
        nombre = parte.nombre_de_fichero(prefijo)

    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


def _snapshot_de_trabajo(s: Session, project_id: uuid.UUID) -> dict[str, Any]:
    """El estado actual del encargo, con los borradores dentro.

    Estados de TRABAJO, no los publicables: el equipo comparte el CAPEX
    mientras todavía lo construye, y un fichero que se deja fuera las líneas en
    borrador da un total que no cuadra con la pantalla desde la que se pulsó el
    botón. Lo descartado sigue fuera.
    """
    from tdd.reporting import snapshot as snap

    return snap.construir(s, project_id, estados=snap.ESTADOS_DE_TRABAJO)


def _libro(datos: dict[str, Any], idioma: Idioma, *, quien: str, del_activo: bool = False) -> bytes:
    """Rellena la plantilla del cliente, o dice por qué no puede.

    Está aparte porque lo llaman las tres descargas —encargo entero, un activo
    y el ZIP de la cartera— y las tres tienen que traducir los mismos dos
    errores al mismo código HTTP. Con el cuerpo duplicado, el día que cambie el
    mensaje solo cambiaría en una.
    """
    from tdd.exports import capex_desde_snapshot as puente
    from tdd.exports.plantilla_capex import NoCabe, generar

    encargo, actuaciones = puente.preparar(
        datos, idioma=idioma.value, activo_en_el_nombre=del_activo
    )
    if not actuaciones:
        # 409 y no un libro vacío: un Excel con la cabecera y ninguna fila se
        # adjunta a un correo sin que nadie note que no lleva nada dentro.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{quien} todavía no tiene ninguna actuación que exportar",
        )
    try:
        return generar(encargo, actuaciones, idioma=idioma.value)
    except NoCabe as exc:
        # 409 y no 500: no es un fallo del servidor, es que el encargo tiene
        # más actuaciones de las que admite la plantilla. El mensaje dice qué
        # capítulo se pasa y por cuánto, que es lo accionable.
        raise HTTPException(status.HTTP_409_CONFLICT, f"{quien}: {exc}") from exc


@router.get(
    "/projects/{project_id}/capex/export.zip",
    tags=["CAPEX"],
    response_class=Response,
    responses={
        200: {
            "content": {"application/zip": {}},
            "description": "Un libro CAPEX por activo, más un LEEME con lo que quedó fuera.",
        }
    },
)
def exportar_cartera_zip(
    project_id: uuid.UUID, s: SesionDep, idioma: Idioma = Idioma.ES
) -> Response:
    """`[REQ]` El CAPEX de una cartera, **un libro por activo**.

    La plantilla del cliente describe **un** edificio: un nombre, unas
    superficies y un tipo que decide qué zonas ofrece el desplegable. Metidos
    tres activos en un solo libro, la cabecera describe al primero y los otros
    dos quedan sin identificar; si además son de tipos distintos, sus zonas se
    vacían. Un activo por libro es lo que la plantilla admite de verdad, y de
    paso multiplica la cabida: diez actuaciones por bloque **y por activo**.

    El ZIP lleva también un `LEEME.txt` con los activos que no llevan libro
    porque todavía no tienen ninguna actuación. Omitirlos en silencio haría que
    un edificio sin visitar y otro visitado sin hallazgos se vieran igual desde
    fuera, que es justo lo que no puede pasar en un envío al cliente.
    """
    import zipfile
    from io import BytesIO

    from tdd.exports import capex_desde_snapshot as puente

    datos = _snapshot_de_trabajo(s, project_id)
    proyecto = datos["project"]
    prefijo = f"CAPEX_{proyecto.get('internal_code') or project_id}"
    partes = puente.separar_por_activo(datos)

    con_actuaciones = [p for p in partes if p.actuaciones]
    if not con_actuaciones:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El encargo todavía no tiene ninguna actuación que exportar",
        )

    buffer = BytesIO()
    usados: set[str] = set()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for parte in con_actuaciones:
            nombre = parte.nombre_de_fichero(prefijo)
            # Dos activos pueden llamarse igual, y el segundo sobrescribiría al
            # primero dentro del ZIP sin decir nada. El `asset_code` los separa
            # cuando lo hay; cuando no, se desempata aquí.
            if nombre in usados:
                nombre = f"{nombre[:-5]}_{str(parte.asset_id)[:8]}.xlsx"
            usados.add(nombre)
            zf.writestr(
                nombre,
                _libro(
                    parte.snapshot, idioma, quien=f"El activo «{parte.nombre}»", del_activo=True
                ),
            )
        zf.writestr("LEEME.txt", _leeme(proyecto, partes, con_actuaciones))

    nombre_zip = f"{prefijo}_por_activo.zip"
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{nombre_zip}"'},
    )


def _leeme(proyecto: dict[str, Any], partes: list[Parte], con_actuaciones: list[Parte]) -> bytes:
    """Qué lleva el ZIP y, sobre todo, **qué no lleva y por qué**."""
    lineas = [
        f"CAPEX de «{proyecto.get('name')}» ({proyecto.get('internal_code') or '—'})",
        "",
        "Un libro por activo. Cada libro es la plantilla CAPEX del cliente con la",
        "cabecera, el tipo de edificio y las zonas de SU activo, y solo sus actuaciones.",
        "",
        f"Libros incluidos ({len(con_actuaciones)}):",
    ]
    lineas += [f"  · {p.nombre} — {p.actuaciones} actuaciones" for p in con_actuaciones]

    vacios = [p for p in partes if not p.actuaciones]
    if vacios:
        lineas += [
            "",
            f"Activos SIN libro ({len(vacios)}), porque no tienen ninguna actuación",
            "registrada todavía. No es lo mismo que no tener CAPEX: puede que aún no",
            "se hayan visitado.",
        ]
        lineas += [f"  · {p.nombre}" for p in vacios]

    huerfanas = [p for p in partes if p.huerfana]
    if huerfanas:
        lineas += [
            "",
            "AVISO: hay actuaciones cuyo activo ya no está en el encargo (se borró",
            "después de registrarlas). Van en su propio libro para no perderse, pero",
            "su cabecera está vacía y sus zonas pueden estarlo también.",
        ]
    return "\n".join(lineas).encode("utf-8")


class TrasladarMedicion(BaseModel):
    confirmar: bool = Field(
        description=(
            "Debe ser true. El traslado es una acción explícita del usuario: la "
            "aplicación nunca sustituye un importe tecleado por su cuenta [REQ] P-05b."
        )
    )


@router.post("/capex-items/{item_id}/carry-measurement")
def trasladar_medicion(
    item_id: uuid.UUID,
    cuerpo: TrasladarMedicion,
    s: SesionDep,
    usuario: UsuarioDep,
    request: Request,
) -> Any:
    """Traslada `computed_base` al importe de la línea. **Acción explícita.**

    `[REQ]` Devuelve **el hallazgo con los totales recalculados**, igual que
    cualquier otro cambio sobre una línea. Devolvía solo la línea, y era una
    incoherencia con su propia regla: la interfaz habría tenido que rehacer la
    suma por su cuenta justo después de que el servidor cambiara un importe, y
    ese cálculo duplicado es donde aparecen los descuadres entre lo que se ve en
    pantalla y lo que se entrega.
    """
    if not cuerpo.confirmar:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "El traslado exige confirmación explícita del usuario",
        )
    fila = (
        s.execute(
            text("SELECT computed_base, amount, row_version FROM capex_item WHERE id = :i"),
            {"i": item_id},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Línea no encontrada")
    # `If-Match` se honra si viene. Trasladar la base pisa un importe que otro
    # pudo teclear con un presupuesto real delante, así que quien manda su
    # versión queda protegido de eso; no se exige porque el traslado ya lleva
    # su propia confirmación explícita.
    cc.comprobar(
        request,
        s,
        tabla="capex_item",
        fila_id=item_id,
        version_actual=fila["row_version"],
        que="una línea de CAPEX",
    )
    if fila["computed_base"] is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Esta línea no tiene desglose por medición: no hay nada que trasladar",
        )

    s.execute(
        text(
            "UPDATE capex_item SET amount = computed_base, amount_source = 'MEDICION', "
            "updated_at = now() WHERE id = :i"
        ),
        {"i": item_id},
    )
    s.execute(
        text(
            "INSERT INTO audit_log (organization_id, actor_user_id, action, entity_type, "
            "entity_id, before_data, after_data, severity) VALUES (:o, :u, 'CAPEX_UPDATED', "
            "'capex_item', :i, CAST(:antes AS jsonb), CAST(:despues AS jsonb), 'INFO')"
        ),
        {
            "o": usuario.organization_id,
            "u": usuario.id,
            "i": item_id,
            "antes": f'{{"amount": "{fila["amount"]}"}}',
            "despues": f'{{"amount": "{fila["computed_base"]}", "amount_source": "MEDICION"}}',
        },
    )
    # Se importa aquí y no arriba para no crear un ciclo entre los dos módulos:
    # `findings` ya conoce el CAPEX, y el CAPEX solo necesita esta lectura.
    from tdd.findings.router import leer_hallazgo

    finding_id = s.execute(
        text("SELECT finding_id FROM capex_item WHERE id = :i"), {"i": item_id}
    ).scalar_one()
    return leer_hallazgo(s, finding_id)
