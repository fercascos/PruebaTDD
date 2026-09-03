"""`[REQ]` Del capítulo 4 al inventario, y quién puede ver qué.

Dos cosas que salieron del mismo documento:

**El inventario.** El capítulo 4 de la Norma Básica enumera los medios de
protección contra incendios del edificio. Teclearlos a mano después de que un
documento los liste es el trabajo repetido que el cliente pidió evitar. Aceptar
una propuesta **crea la ficha de equipo**, y por eso es la única de las tres
decisiones que exige decir **a qué activo va**: el documento no lo dice.

**La confidencialidad.** Un plan de autoprotección nace `RESTRINGIDO`, y eso
tenía que significar algo más que un adorno en la ficha: **no se manda a un
proveedor de IA**, ni con la revisión del encargo activada.

`[REQ]` No hay ningún documento de cliente en el repositorio. El plan de estas
pruebas se fabrica aquí.
"""

from __future__ import annotations

import io
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

pytestmark = pytest.mark.db

RUTA = "/api/v1"

PLAN = """\
Plan de Autoprotección del complejo logístico
Fecha: 01/06/2025

Índice

1. Capítulo 4: medios de autoprotección

2. Capítulo 5: mantenimiento

1. Capítulo 4: medios de autoprotección

Abastecimiento de agua

Red de agua contra incendios conectada a un depósito aéreo y a un grupo de
presión con bomba eléctrica principal y dos bombas diésel de reserva.

Hidrantes

Dieciséis hidrantes privados distribuidos por el perímetro del complejo.

Extinción automática

Rociadores automáticos sobre la superficie industrial de almacenamiento.

Medios humanos

Director del Plan, Jefe de Emergencia y Equipo de Primera Intervención.

2. Capítulo 5: mantenimiento

El plan contempla revisiones trimestrales, semestrales, anuales y quinquenales
según el tipo de equipo, con registro documental de cada operación.
"""


def plan_pdf(texto: str = PLAN) -> bytes:
    from reportlab.lib.pagesizes import A4  # type: ignore[import-not-found]
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    cuerpo = getSampleStyleSheet()["BodyText"]
    doc.build([Paragraph(linea or "&nbsp;", cuerpo) for linea in texto.split("\n")])
    return buffer.getvalue()


@pytest.fixture
def proyecto(motor_admin: Engine, datos_base: dict[str, uuid.UUID]) -> str:
    with motor_admin.begin() as conn:
        return str(
            conn.execute(
                text(
                    "INSERT INTO project (organization_id, client_id, internal_code, name) "
                    "VALUES (:o, :c, :cod, 'Encargo con inventario') RETURNING id"
                ),
                {
                    "o": str(datos_base["org_a"]),
                    "c": str(datos_base["cliente_a"]),
                    "cod": f"EQ-{uuid.uuid4().hex[:6]}",
                },
            ).scalar_one()
        )


@pytest.fixture(scope="module")
def tipologia(motor_admin: Engine) -> str:
    with motor_admin.begin() as conn:
        return str(
            conn.execute(
                text("SELECT id FROM asset_typology WHERE code = 'INDUSTRIAL'")
            ).scalar_one()
        )


@pytest.fixture
def activo(cliente: TestClient, cab: Any, proyecto: str, tipologia: str) -> str:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={"name": "Nave 2", "typology_id": tipologia},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def subir_plan(cliente: TestClient, cab: Any, proyecto: str, **extra: str) -> dict[str, Any]:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/documents",
        headers=cab("consultor_a"),
        files={"file": ("plan.pdf", plan_pdf(), "application/pdf")},
        data={"doc_type": "PLAN_AUTOPROTECCION", "display_name": "plan.pdf", **extra},
    )
    assert r.status_code == 201, r.text
    return dict(r.json())


def _autorizar_ia(cliente: TestClient, cab: Any, proyecto: str) -> None:
    """Enciende la revisión con IA del encargo, con su autoría."""
    r = cliente.put(
        f"{RUTA}/projects/{proyecto}/ai-doc-review",
        headers=cab("admin_a"),
        json={"activo": True},
    )
    assert r.status_code == 200, r.text


def propuestas(cliente: TestClient, cab: Any, proyecto: str) -> list[dict[str, Any]]:
    documento = subir_plan(cliente, cab, proyecto)
    r = cliente.post(f"{RUTA}/documents/{documento['id']}/extraer", headers=cab("consultor_a"))
    assert r.status_code == 201, r.text
    return list(
        cliente.get(
            f"{RUTA}/projects/{proyecto}/propuestas-de-equipo", headers=cab("consultor_a")
        ).json()
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Del documento a la propuesta
# ─────────────────────────────────────────────────────────────────────────────


def test_el_plan_propone_los_medios_que_enumera(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    documento = subir_plan(cliente, cab, proyecto)
    resultado = cliente.post(
        f"{RUTA}/documents/{documento['id']}/extraer", headers=cab("consultor_a")
    ).json()

    assert resultado["equipos"] >= 3
    lista = cliente.get(
        f"{RUTA}/projects/{proyecto}/propuestas-de-equipo", headers=cab("consultor_a")
    ).json()
    tipos = {p["equipment_type"] for p in lista}
    assert "Hidrante" in tipos
    assert "Rociador automático" in tipos
    # Los medios humanos NO son equipos.
    assert not any("Jefe de Emergencia" in t for t in tipos)


def test_cada_propuesta_trae_su_sistema_tecnico_y_su_procedencia(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    lista = propuestas(cliente, cab, proyecto)
    hidrante = next(p for p in lista if p["equipment_type"] == "Hidrante")

    assert hidrante["technical_system_name"] == "Protección contra incendios"
    assert hidrante["quantity"] == "16.00", "«Dieciséis hidrantes» son dieciséis"
    assert hidrante["seccion"] == "Capítulo 4 · Medios de autoprotección"
    assert hidrante["evidencia"]
    assert hidrante["documento"] == "plan"
    assert hidrante["estado"] == "PENDIENTE"


def test_un_medio_sin_cantidad_llega_sin_cantidad(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """`[REQ]` Un 1 por omisión metería un uno en un inventario que después
    alguien lee como cierto."""
    lista = propuestas(cliente, cab, proyecto)
    rociador = next(p for p in lista if p["equipment_type"] == "Rociador automático")
    assert rociador["quantity"] is None


# ─────────────────────────────────────────────────────────────────────────────
#  De la propuesta a la ficha de equipo
# ─────────────────────────────────────────────────────────────────────────────


def test_aceptar_crea_el_equipo_en_el_activo_que_se_elige(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REQ]` El documento no dice de qué nave son los hidrantes. Lo elige quien
    acepta: adivinarlo lo haría pasar por sabido, y un equipo en la nave
    equivocada es una visita perdida."""
    lista = propuestas(cliente, cab, proyecto)
    hidrante = next(p for p in lista if p["equipment_type"] == "Hidrante")

    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/propuestas-de-equipo/decidir",
        headers=cab("consultor_a"),
        json={"aceptar": [{"id": hidrante["id"], "asset_id": activo, "maintenance_months": 12}]},
    )

    assert r.status_code == 200, r.text
    assert r.json()["aceptadas"] == 1
    equipo_id = r.json()["equipment_ids"][0]

    equipo = cliente.get(f"{RUTA}/equipment/{equipo_id}", headers=cab("consultor_a")).json()
    assert equipo["equipment_type"] == "Hidrante"
    assert equipo["asset_id"] == activo
    assert equipo["quantity"] == "16.00"
    assert equipo["technical_system_name"] == "Protección contra incendios"
    assert equipo["maintenance_months"] == 12
    assert equipo["notes"], "la frase del documento va a las notas"


def test_la_propuesta_aceptada_apunta_al_equipo_que_creo(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """Cierra la trazabilidad al revés: desde la ficha del equipo se llega al
    documento que lo declaró."""
    lista = propuestas(cliente, cab, proyecto)
    primera = lista[0]
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/propuestas-de-equipo/decidir",
        headers=cab("consultor_a"),
        json={"aceptar": [{"id": primera["id"], "asset_id": activo}]},
    )

    tras = cliente.get(
        f"{RUTA}/projects/{proyecto}/propuestas-de-equipo?estado=ACEPTADA",
        headers=cab("consultor_a"),
    ).json()
    assert tras[0]["equipment_id"] == r.json()["equipment_ids"][0]


def test_un_medio_sin_cantidad_nace_con_uno_y_se_puede_corregir(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`equipment.quantity` es NOT NULL. Quien acepta puede poner la buena."""
    lista = propuestas(cliente, cab, proyecto)
    rociador = next(p for p in lista if p["equipment_type"] == "Rociador automático")

    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/propuestas-de-equipo/decidir",
        headers=cab("consultor_a"),
        json={"aceptar": [{"id": rociador["id"], "asset_id": activo, "quantity": "240"}]},
    )
    equipo = cliente.get(
        f"{RUTA}/equipment/{r.json()['equipment_ids'][0]}", headers=cab("consultor_a")
    ).json()
    assert equipo["quantity"] == "240.00"


def test_un_activo_de_otro_encargo_se_rechaza(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    motor_admin: Engine,
    datos_base: Any,
    tipologia: str,
) -> None:
    """La RLS no lo ve como error: las dos filas son de la misma organización."""
    with motor_admin.begin() as conn:
        otro = conn.execute(
            text(
                "INSERT INTO project (organization_id, client_id, internal_code, name) "
                "VALUES (:o, :c, :cod, 'Otro encargo') RETURNING id"
            ),
            {
                "o": str(datos_base["org_a"]),
                "c": str(datos_base["cliente_a"]),
                "cod": f"OT-{uuid.uuid4().hex[:6]}",
            },
        ).scalar_one()
        ajeno = conn.execute(
            text(
                "INSERT INTO asset (organization_id, project_id, typology_id, name) "
                "VALUES (:o, :p, :t, 'Nave ajena') RETURNING id"
            ),
            {"o": str(datos_base["org_a"]), "p": str(otro), "t": tipologia},
        ).scalar_one()

    lista = propuestas(cliente, cab, proyecto)
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/propuestas-de-equipo/decidir",
        headers=cab("consultor_a"),
        json={"aceptar": [{"id": lista[0]["id"], "asset_id": str(ajeno)}]},
    )
    assert r.status_code == 422
    assert "no es de este encargo" in r.json()["detail"]


def test_descartar_no_crea_nada_y_deja_constancia(
    cliente: TestClient, cab: Any, proyecto: str, datos_base: Any
) -> None:
    lista = propuestas(cliente, cab, proyecto)
    cliente.post(
        f"{RUTA}/projects/{proyecto}/propuestas-de-equipo/decidir",
        headers=cab("consultor_a"),
        json={"descartar": [lista[0]["id"]]},
    )

    tras = cliente.get(
        f"{RUTA}/projects/{proyecto}/propuestas-de-equipo?estado=DESCARTADA",
        headers=cab("consultor_a"),
    ).json()
    assert len(tras) == 1
    assert tras[0]["equipment_id"] is None
    assert tras[0]["decidida_por"] == str(datos_base["consultor_a"])


def test_aceptar_y_descartar_la_misma_se_rechaza(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    lista = propuestas(cliente, cab, proyecto)
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/propuestas-de-equipo/decidir",
        headers=cab("consultor_a"),
        json={
            "aceptar": [{"id": lista[0]["id"], "asset_id": activo}],
            "descartar": [lista[0]["id"]],
        },
    )
    assert r.status_code == 422
    assert "repetida" in r.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
#  El mantenimiento preventivo, que faltaba
# ─────────────────────────────────────────────────────────────────────────────


def test_la_proxima_revision_la_calcula_la_base(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, tipologia: str
) -> None:
    """`[REQ]` Se genera, igual que el fin de vida útil y por lo mismo: lo que se
    guarda no caduca y lo derivado no se teclea."""
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/equipment",
        headers=cab("consultor_a"),
        json={
            "asset_id": activo,
            "equipment_type": "Extintor de polvo ABC",
            "maintenance_months": 3,
            "last_maintenance_date": "2024-01-31",
        },
    )
    assert r.status_code == 201, r.text
    # 31 de enero + 3 meses = 30 de abril, no el 31 que no existe.
    assert r.json()["next_maintenance_due"] == "2024-04-30"


def test_el_mantenimiento_vencido_es_otra_pregunta_que_la_vida_agotada(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REQ]` Un extintor de dos años sin revisar desde hace dieciocho meses no
    está al final de su vida útil y sí está fuera de norma. Mezclar los dos
    filtros escondería justo el caso que se busca."""
    nuevo_sin_revisar = cliente.post(
        f"{RUTA}/projects/{proyecto}/equipment",
        headers=cab("consultor_a"),
        json={
            "asset_id": activo,
            "equipment_type": "Extintor sin revisar",
            "install_year": 2023,
            "expected_life_years": 20,
            "maintenance_months": 12,
            "last_maintenance_date": "2020-01-01",
        },
    ).json()
    viejo_al_dia = cliente.post(
        f"{RUTA}/projects/{proyecto}/equipment",
        headers=cab("consultor_a"),
        json={
            "asset_id": activo,
            "equipment_type": "Caldera al día",
            "install_year": 1990,
            "expected_life_years": 15,
        },
    ).json()

    vencido_mantenimiento = cliente.get(
        f"{RUTA}/projects/{proyecto}/equipment?solo_mantenimiento_vencido=true",
        headers=cab("consultor_a"),
    ).json()
    vencida_vida = cliente.get(
        f"{RUTA}/projects/{proyecto}/equipment?solo_vencidos=true", headers=cab("consultor_a")
    ).json()

    assert [e["id"] for e in vencido_mantenimiento] == [nuevo_sin_revisar["id"]]
    assert [e["id"] for e in vencida_vida] == [viejo_al_dia["id"]]


def test_un_equipo_sin_periodicidad_no_esta_vencido(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """No saber cuándo toca no es lo mismo que estar fuera de plazo."""
    cliente.post(
        f"{RUTA}/projects/{proyecto}/equipment",
        headers=cab("consultor_a"),
        json={"asset_id": activo, "equipment_type": "Sin plan de mantenimiento"},
    )
    vencidos = cliente.get(
        f"{RUTA}/projects/{proyecto}/equipment?solo_mantenimiento_vencido=true",
        headers=cab("consultor_a"),
    ).json()
    assert vencidos == []


# ─────────────────────────────────────────────────────────────────────────────
#  Confidencialidad
# ─────────────────────────────────────────────────────────────────────────────


def test_un_restringido_no_se_manda_a_ningun_proveedor_de_ia(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """`[REQ]` **El hueco que faltaba.** La comprobación de confidencialidad
    estaba en `descargar()` y no en la revisión, así que un documento que un
    consultor del equipo no puede ni abrir sí se podía mandar a un proveedor
    externo con solo el interruptor del encargo encendido.
    """
    # Por el endpoint y no por SQL: la base exige que el interruptor lleve su
    # autoría —`project_revision_ia_con_autoria`—, que es justo lo que hace que
    # la autorización sea verificable. Un UPDATE a pelo se lo salta.
    _autorizar_ia(cliente, cab, proyecto)
    documento = subir_plan(cliente, cab, proyecto)
    assert documento["confidentiality"] == "RESTRINGIDO"

    r = cliente.post(
        f"{RUTA}/documents/{documento['id']}/ai-review", headers=cab("consultor_a"), json={}
    )

    assert r.status_code == 403
    assert "RESTRINGIDO" in r.json()["detail"]
    assert "baje su clasificación" in r.json()["detail"]


def test_bajando_la_clasificacion_si_se_revisa_y_queda_el_rastro(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """`[REC]` No hay un segundo interruptor: se baja la clasificación a mano, y
    eso deja rastro. Un interruptor más lo convertiría en un clic sin memoria."""
    _autorizar_ia(cliente, cab, proyecto)
    documento = subir_plan(cliente, cab, proyecto)

    cliente.patch(
        f"{RUTA}/documents/{documento['id']}",
        headers=cab("admin_a"),
        json={"confidentiality": "CONFIDENCIAL"},
    )
    r = cliente.post(
        f"{RUTA}/documents/{documento['id']}/ai-review", headers=cab("consultor_a"), json={}
    )
    assert r.status_code == 201, r.text


def test_el_mapa_de_confidencialidad_se_publica_con_su_motivo(
    cliente: TestClient, cab: Any
) -> None:
    """`[REQ]` Para que la pantalla lo diga **antes** de subir. Un nivel que
    aparece solo en la ficha, ya guardado, no informa la decisión de quien sube:
    informa la sorpresa de quien intenta descargarlo."""
    r = cliente.get(f"{RUTA}/documents/confidencialidad-por-tipo", headers=cab("consultor_a"))

    assert r.status_code == 200
    plan = next(x for x in r.json() if x["doc_type"] == "PLAN_AUTOPROTECCION")
    assert plan["confidentiality"] == "RESTRINGIDO"
    assert "emergencia" in plan["motivo"]
