"""API de proyectos.

El alta es el punto donde el cliente **elige las fases aplicables** `[REQ]`
§3.1.5. Se crean solo las marcadas: un proyecto sin Q&A no arrastra una fase
vacía que nadie va a rellenar y que ensucia la ficha.

Tres decisiones del alta que se ven al leer el código:

**El código interno lo genera el servidor.** `AAAA-NNN`, por organización y por
año. Se dejó de teclear porque un código que escribe una persona se repite, y el
segundo que lo intenta se lleva un `409` a mitad del alta. Sigue admitiéndose en
el cuerpo —una migración desde otro sistema trae los suyos— pero la pantalla no
lo ofrece: lo enseña bloqueado. Y **no hay forma de cambiarlo después**: este
módulo no tiene `PATCH`.

**El cliente que no está en la lista no bloquea.** Se elige de un catálogo que
mantiene la administración; si no está, se escribe el nombre, el proyecto se
crea igual y el cliente nace `pending_validation`. El aviso al administrador es
una sugerencia de tipo `CATALOGO` en el buzón que ya existe y que solo ven los
administradores, con RLS. Un segundo mecanismo de avisos sería otro sitio donde
mirar, y nadie mira dos.

**Tres fechas, no una.** Arranque y cierre son del trabajo y salen en la lista;
`report_due_date` es el compromiso de entrega del informe.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tdd.core.deps import SesionDep, UsuarioDep
from tdd.phases.engine import PhaseCode
from tdd.phases.repository import contar_para_transicion
from tdd.projects.state_machine import (
    EstadoDelEncargo,
    GuardaIncumplida,
    ProjectStatus,
    TransicionNoPermitida,
    destinos_posibles,
    validar_transicion,
)

router = APIRouter(tags=["Proyectos"])


class FaseAplicable(BaseModel):
    code: PhaseCode
    owner_user_id: uuid.UUID | None = None


class CrearProyecto(BaseModel):
    """`extra="forbid"`, igual que la ficha de activo: un campo mal escrito se
    rechaza en vez de perderse. Un `fecha_entrega` que la API ignora en silencio
    crea un proyecto sin fecha que nadie detecta hasta que se pasa."""

    model_config = ConfigDict(extra="forbid")

    #: Uno de los dos: el cliente del catálogo, o el nombre de uno que no está.
    client_id: uuid.UUID | None = None
    client_name: str | None = Field(default=None, min_length=1, max_length=200)
    #: Sin él, lo genera el servidor. La pantalla no lo ofrece.
    internal_code: str | None = Field(default=None, min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    start_date: Any | None = None
    close_date: Any | None = None
    report_due_date: Any | None = None
    #: `[REQ]` Las fases se eligen **a la carta** al dar de alta.
    applicable_phases: list[FaseAplicable] = Field(default_factory=list)

    @model_validator(mode="after")
    def _el_cierre_no_precede_al_arranque(self) -> CrearProyecto:
        """Se comprueba **aquí y en la base**, y no es duplicar por gusto.

        La restricción de la tabla es la barrera que ningún camino se salta —una
        carga por SQL, una migración—, pero contesta con un `500`: un error de
        tecleo tiene que devolver un `422` que diga qué fecha está mal.
        """
        if self.start_date and self.close_date and str(self.close_date) < str(self.start_date):
            raise ValueError("La fecha de cierre no puede ser anterior a la de arranque")
        return self


class Proyecto(BaseModel):
    id: uuid.UUID
    internal_code: str
    name: str
    status: str
    currency: str
    client_id: uuid.UUID | None = None
    #: El nombre, no solo el identificador: la lista y la cabecera lo enseñan, y
    #: pedir el cliente aparte por cada fila sería una petición por proyecto.
    client_name: str | None = None
    #: `[REQ]` Que el cliente esté sin validar viaja hasta la pantalla. Un
    #: proyecto colgando de un cliente que nadie ha revisado tiene que verse.
    client_pending_validation: bool = False
    start_date: Any | None = None
    close_date: Any | None = None
    report_due_date: Any | None = None


#: Las columnas del proyecto con su cliente al lado, escritas una vez: estaban
#: repetidas en cuatro consultas y añadir una fecha significaba acordarse de las
#: cuatro.
_COLUMNAS = (
    "p.id, p.internal_code, p.name, CAST(p.status AS text) AS status, p.currency, "
    "p.client_id, c.name AS client_name, "
    "COALESCE(c.pending_validation, FALSE) AS client_pending_validation, "
    "p.start_date, p.close_date, p.report_due_date"
)
_DESDE = "FROM project p LEFT JOIN client c ON c.id = p.client_id"


def _codigo_generado(s: Any, organizacion: uuid.UUID, salto: int = 0) -> str:
    """`AAAA-NNN`, el siguiente libre del año en curso en esta organización.

    Se calcula sobre los códigos que ya existen y no sobre un contador aparte:
    un contador se desincroniza en cuanto alguien borra un proyecto o importa
    una tanda con códigos propios, y entonces genera uno repetido.

    Cuenta **solo los de tres cifras**, que son los que genera él mismo. Un
    código traído de otro sistema —`2026-123456`— dispararía la serie a
    `2026-123457` y dejaría los siguientes ilegibles para siempre.

    `salto` es el número de intentos ya fallidos: sin él, un reintento volvería
    a calcular el mismo número y chocaría otra vez hasta agotarse.

    `[LIM]` Dos altas simultáneas pueden calcular el mismo número. Lo impide el
    `UNIQUE (organization_id, internal_code)` de la tabla, y quien llama
    reintenta: es más simple que un bloqueo y falla del lado seguro.
    """
    anio = date.today().year
    siguiente = s.execute(
        text(
            "SELECT COALESCE(MAX(SUBSTRING(internal_code FROM :patron)::int), 0) + :salto "
            "FROM project WHERE organization_id = :o AND internal_code LIKE :prefijo"
        ),
        {
            "patron": r"^\d{4}-(\d{3})$",
            "o": str(organizacion),
            "prefijo": f"{anio}-%",
            "salto": 1 + salto,
        },
    ).scalar_one()
    return f"{anio}-{int(siguiente):03d}"


#: El nombre que PostgreSQL le pone a `UNIQUE (organization_id, internal_code)`.
_UNICIDAD_DEL_CODIGO = "project_organization_id_internal_code_key"


def _es_choque_de_codigo(exc: IntegrityError) -> bool:
    """Si la restricción violada es la del código, y no otra cualquiera."""
    diagnostico = getattr(getattr(exc, "orig", None), "diag", None)
    nombre = getattr(diagnostico, "constraint_name", None)
    # Sin diagnóstico —otro controlador de base de datos— se mira el texto, que
    # es peor pero sigue siendo específico.
    return nombre == _UNICIDAD_DEL_CODIGO or _UNICIDAD_DEL_CODIGO in str(exc)


def _cliente_del_alta(cuerpo: CrearProyecto, s: Any, usuario: Any) -> tuple[uuid.UUID, bool]:
    """El cliente elegido, o uno nuevo **pendiente de validar**.

    Devuelve `(id, nace_pendiente)`. Escribir un nombre que ya existe en el
    catálogo **reutiliza el que hay** en vez de crear un duplicado: quien teclea
    «Inmobiliaria Ejemplo» no sabe si está o no, y dos clientes con el mismo
    nombre parten la cartera en dos sin que nadie se entere.
    """
    if cuerpo.client_id is not None:
        existe = s.execute(
            text("SELECT 1 FROM client WHERE id = :c AND deleted_at IS NULL"),
            {"c": cuerpo.client_id},
        ).first()
        if existe is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ese cliente no existe")
        return cuerpo.client_id, False

    nombre = (cuerpo.client_name or "").strip()
    if not nombre:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Elija un cliente de la lista o escriba el nombre de uno nuevo",
        )

    ya = s.execute(
        text(
            "SELECT id FROM client WHERE organization_id = :o AND deleted_at IS NULL "
            "AND lower(name) = lower(:n)"
        ),
        {"o": usuario.organization_id, "n": nombre},
    ).scalar_one_or_none()
    if ya is not None:
        return ya, False

    nuevo = s.execute(
        text(
            "INSERT INTO client (organization_id, name, pending_validation) "
            "VALUES (:o, :n, TRUE) RETURNING id"
        ),
        {"o": usuario.organization_id, "n": nombre},
    ).scalar_one()
    return nuevo, True


def _avisar_de_cliente_sin_validar(s: Any, usuario: Any, proyecto: Any, cliente: str) -> None:
    """El aviso al administrador, en el buzón que ya existe.

    `[REQ]` No bloquea el alta y **no se pierde**: la bandeja de sugerencias
    solo la ven los administradores, por RLS, y lleva su propio ciclo de
    atendido/descartado. Un correo se archiva y una tabla nueva es otro sitio
    donde mirar.
    """
    s.execute(
        text(
            "INSERT INTO suggestion (organization_id, type, status, title, body, created_by, "
            "context_project_id, context_entity_type, context_screen) "
            "VALUES (:o, 'CATALOGO', 'NUEVA', :t, :b, :u, :p, 'client', 'Nuevo proyecto')"
        ),
        {
            "o": usuario.organization_id,
            "u": usuario.id,
            "p": proyecto["id"],
            "t": f"Cliente sin validar: {cliente}",
            "b": (
                f"El proyecto {proyecto['internal_code']} · {proyecto['name']} se ha dado de alta "
                f"con el cliente «{cliente}», que no estaba en el catálogo. El proyecto está "
                "creado; falta validar el cliente."
            ),
        },
    )


@router.post("/projects", status_code=status.HTTP_201_CREATED, response_model=Proyecto)
def crear(cuerpo: CrearProyecto, s: SesionDep, usuario: UsuarioDep) -> Any:
    cliente_id, pendiente = _cliente_del_alta(cuerpo, s, usuario)

    # Si el código viene dado se usa tal cual y un choque es un 409 honesto. Si
    # lo genera el servidor, un choque es cosa suya —dos altas a la vez— y lo
    # que corresponde es volver a calcularlo, no echarle la culpa a quien llama.
    intentos = 1 if cuerpo.internal_code else 5
    for intento in range(intentos):
        codigo = cuerpo.internal_code or _codigo_generado(s, usuario.organization_id, intento)
        try:
            with s.begin_nested():
                fila = (
                    s.execute(
                        text(
                            "INSERT INTO project (organization_id, client_id, internal_code, "
                            "name, currency, start_date, close_date, report_due_date) "
                            "VALUES (:o, :c, :ic, :n, :cur, :ini, :fin, :due) "
                            "RETURNING id, internal_code, name, "
                            "CAST(status AS text) AS status, currency, client_id, "
                            "start_date, close_date, report_due_date"
                        ),
                        {
                            "o": usuario.organization_id,
                            "c": cliente_id,
                            "ic": codigo,
                            "n": cuerpo.name,
                            "cur": cuerpo.currency,
                            "ini": cuerpo.start_date,
                            "fin": cuerpo.close_date,
                            "due": cuerpo.report_due_date,
                        },
                    )
                    .mappings()
                    .one()
                )
            break
        except IntegrityError as exc:
            # **Solo** el choque de código se reintenta. Sin esta comprobación,
            # cualquier restricción violada —una fecha de cierre anterior al
            # arranque, por ejemplo— se reintentaba cinco veces y acababa
            # contestando «el código ya está en uso», que es mentira y manda a
            # quien lo lee a buscar el fallo donde no está.
            if not _es_choque_de_codigo(exc):
                raise
            if cuerpo.internal_code or intento == intentos - 1:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, f"El código interno «{codigo}» ya está cogido"
                ) from exc

    cliente = s.execute(
        text("SELECT name FROM client WHERE id = :c"), {"c": cliente_id}
    ).scalar_one()
    if pendiente:
        _avisar_de_cliente_sin_validar(s, usuario, fila, cliente)

    # Solo las fases marcadas. Las demás ni se crean: activarlas después es un
    # POST, y así la ficha no muestra ocho filas cuando el proyecto usa cuatro.
    for orden, fase in enumerate(cuerpo.applicable_phases, 1):
        s.execute(
            text(
                "INSERT INTO project_phase (organization_id, project_id, phase_definition_id, "
                "owner_user_id, display_order) "
                "SELECT :o, :p, pd.id, :u, :ord FROM phase_definition pd WHERE pd.code = :code"
            ),
            {
                "o": usuario.organization_id,
                "p": fila["id"],
                "u": fase.owner_user_id,
                "ord": orden,
                "code": fase.code.value,
            },
        )
    return {**dict(fila), "client_name": cliente, "client_pending_validation": pendiente}


class Transicion(BaseModel):
    to: ProjectStatus


@router.get("/projects", response_model=list[Proyecto])
def listar(
    s: SesionDep,
    estado: str | None = None,
    q: str | None = None,
) -> Any:
    """Los proyectos de la organización. La RLS ya acota lo que se ve."""
    filas = (
        s.execute(
            text(
                f"SELECT {_COLUMNAS} {_DESDE} WHERE p.deleted_at IS NULL "  # noqa: S608
                "  AND (CAST(:estado AS text) IS NULL OR p.status::text = CAST(:estado AS text)) "
                "  AND (CAST(:q AS text) IS NULL "
                "       OR p.name ILIKE '%' || :q || '%' "
                "       OR p.internal_code ILIKE '%' || :q || '%' "
                "       OR c.name ILIKE '%' || :q || '%') "
                "ORDER BY p.created_at DESC"
            ),
            {"estado": estado, "q": q},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


@router.get("/projects/{project_id}", response_model=Proyecto)
def obtener(project_id: uuid.UUID, s: SesionDep) -> Any:
    fila = (
        s.execute(
            text(
                f"SELECT {_COLUMNAS} {_DESDE} "  # noqa: S608
                "WHERE p.id = :i AND p.deleted_at IS NULL"
            ),
            {"i": str(project_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyecto no encontrado")
    return dict(fila)


class DestinoPosible(BaseModel):
    to: ProjectStatus
    permitida: bool
    falta: list[str]


@router.get("/projects/{project_id}/transitions", response_model=list[DestinoPosible])
def transiciones_disponibles(project_id: uuid.UUID, s: SesionDep) -> Any:
    """Qué se puede hacer ahora y **qué falta para lo que no**.

    `[REC]` Alimenta botones deshabilitados con su motivo, en vez de botones
    ausentes. Un botón que no está no se puede preguntar por qué no está.
    """
    actual = s.execute(
        text("SELECT CAST(status AS text) FROM project WHERE id = :p"), {"p": project_id}
    ).scalar_one_or_none()
    if actual is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyecto no encontrado")

    c = contar_para_transicion(s, project_id)
    proyecto = EstadoDelEncargo(
        clientes=c["clientes"],
        activos=c["activos"],
        visitas_agendadas=c["agendadas"],
        visitas_realizadas=c["realizadas"],
    )
    return [
        {"to": destino, "permitida": not falta, "falta": falta}
        for destino, falta in destinos_posibles(ProjectStatus(actual), proyecto).items()
    ]


@router.post("/projects/{project_id}/transitions", response_model=Proyecto)
def transicionar(
    project_id: uuid.UUID, cuerpo: Transicion, s: SesionDep, usuario: UsuarioDep
) -> Any:
    actual = s.execute(
        text("SELECT CAST(status AS text) FROM project WHERE id = :p"), {"p": project_id}
    ).scalar_one_or_none()
    if actual is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyecto no encontrado")

    c = contar_para_transicion(s, project_id)
    proyecto = EstadoDelEncargo(
        clientes=c["clientes"],
        activos=c["activos"],
        visitas_agendadas=c["agendadas"],
        visitas_realizadas=c["realizadas"],
    )
    try:
        validar_transicion(ProjectStatus(actual), cuerpo.to, proyecto)
    except GuardaIncumplida as exc:
        # 422: la transición existe, pero falta trabajo. El mensaje dice cuál.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except TransicionNoPermitida as exc:
        # 409: esa transición no existe desde el estado actual.
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    fila = (
        s.execute(
            text(
                "WITH cambiado AS ("
                "  UPDATE project SET status = CAST(:to AS project_status), updated_at = now() "
                "  WHERE id = :p RETURNING *"
                f") SELECT {_COLUMNAS} FROM cambiado p "  # noqa: S608
                "LEFT JOIN client c ON c.id = p.client_id"
            ),
            {"to": cuerpo.to.value, "p": project_id},
        )
        .mappings()
        .one()
    )

    s.execute(
        text(
            "INSERT INTO audit_log (organization_id, actor_user_id, action, entity_type, "
            "entity_id, project_id, after_data, severity) VALUES (:o, :u, "
            "'PROJECT_STATUS_CHANGED', 'project', :p, :p, CAST(:d AS jsonb), 'AVISO')"
        ),
        {
            "o": usuario.organization_id,
            "u": usuario.id,
            "p": project_id,
            "d": f'{{"from": "{actual}", "to": "{cuerpo.to.value}"}}',
        },
    )
    return dict(fila)
