"""Fotografías: versiones, clasificación en lote, ZIP y purga.

Lo que se comprueba aquí es la parte del bloque 2 que solo se nota cuando el
proyecto ya tiene cientos de fotos: anotar sin tocar el original, clasificar en
lote, exportar sin metadatos y purgar con autorización.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.unit.test_imagenes import con_exif, imagen

pytestmark = pytest.mark.db

RUTA = "/api/v1"


@pytest.fixture
def proyecto(motor_admin: Engine, datos_base: dict[str, uuid.UUID]) -> str:
    with motor_admin.begin() as conn:
        return str(
            conn.execute(
                text(
                    "INSERT INTO project (organization_id, client_id, internal_code, name) "
                    "VALUES (:o, :c, :cod, 'Encargo con muchas fotos') RETURNING id"
                ),
                {
                    "o": str(datos_base["org_a"]),
                    "c": str(datos_base["cliente_a"]),
                    "cod": f"AVZ-{uuid.uuid4().hex[:6]}",
                },
            ).scalar_one()
        )


def foto_unica() -> bytes:
    import random

    return imagen(color=(random.randrange(256), random.randrange(256), 77))


def subir(cliente: TestClient, cab: Any, proyecto: str, datos: bytes | None = None, **campos: Any):
    return cliente.post(
        f"{RUTA}/projects/{proyecto}/photos",
        headers=cab("consultor_a"),
        files={"file": ("f.jpg", io.BytesIO(datos or foto_unica()), "image/jpeg")},
        data={k: str(v) for k, v in campos.items()},
    ).json()


# ─────────────────────────────────────────────────────────────────────────────
#  Versiones §15.2
# ─────────────────────────────────────────────────────────────────────────────


def test_la_primera_version_es_el_original(cliente: TestClient, cab: Any, proyecto: str) -> None:
    foto = subir(cliente, cab, proyecto)
    versiones = cliente.get(
        f"{RUTA}/photos/{foto['id']}/versions", headers=cab("consultor_a")
    ).json()
    assert len(versiones) == 1
    assert versiones[0]["version_type"] == "ORIGINAL"
    assert versiones[0]["stored_object_id"] is not None


def test_anotar_crea_una_version_sin_duplicar_el_binario(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """`[REC]` §15.2 · Capa vectorial, no píxeles quemados: editable,
    reversible, ocupa bytes en lugar de megabytes y el original sigue limpio."""
    foto = subir(cliente, cab, proyecto)
    r = cliente.post(
        f"{RUTA}/photos/{foto['id']}/versions/annotate",
        headers=cab("consultor_a"),
        json={
            "annotations": {
                "canvas": {"width": 640, "height": 480},
                "shapes": [
                    {"type": "rect", "x": 100, "y": 80, "w": 200, "h": 120, "stroke": "#E53935"}
                ],
            },
            "notes": "Corrosión activa en el soporte",
        },
    )
    assert r.status_code == 201, r.text
    anotada = r.json()[-1]
    assert anotada["version_type"] == "ANOTADA"
    assert anotada["stored_object_id"] is None, "no se duplica el binario"
    assert anotada["is_current"] is True
    assert len(anotada["annotations"]["shapes"]) == 1


def test_una_capa_sin_formas_se_rechaza(cliente: TestClient, cab: Any, proyecto: str) -> None:
    foto = subir(cliente, cab, proyecto)
    r = cliente.post(
        f"{RUTA}/photos/{foto['id']}/versions/annotate",
        headers=cab("consultor_a"),
        json={"annotations": {"canvas": {"width": 1, "height": 1}}},
    )
    assert r.status_code == 422


def test_solo_hay_una_version_vigente(cliente: TestClient, cab: Any, proyecto: str) -> None:
    foto = subir(cliente, cab, proyecto)
    for _ in range(2):
        cliente.post(
            f"{RUTA}/photos/{foto['id']}/versions/annotate",
            headers=cab("consultor_a"),
            json={"annotations": {"shapes": []}},
        )
    versiones = cliente.get(
        f"{RUTA}/photos/{foto['id']}/versions", headers=cab("consultor_a")
    ).json()
    assert sum(1 for v in versiones if v["is_current"]) == 1


def test_restaurar_crea_una_version_nueva_y_no_reescribe_la_historia(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """`[REQ]` §15.2 · Que el estado anterior desapareciera del historial sería
    exactamente lo que una evidencia técnica no puede permitirse."""
    foto = subir(cliente, cab, proyecto)
    cliente.patch(
        f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a"), json={"display_name": "Cubierta"}
    )
    versiones = cliente.get(
        f"{RUTA}/photos/{foto['id']}/versions", headers=cab("consultor_a")
    ).json()
    original = versiones[0]

    r = cliente.post(f"{RUTA}/photo-versions/{original['id']}/restore", headers=cab("consultor_a"))
    assert r.status_code == 200
    assert len(r.json()) == 3, "restaurar añade, no sustituye"
    assert r.json()[-1]["display_name"] == original["display_name"]

    actual = cliente.get(f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a")).json()
    assert actual["display_name"] == original["display_name"]


def test_la_version_original_sigue_ahi_despues_de_todo(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    foto = subir(cliente, cab, proyecto)
    cliente.post(
        f"{RUTA}/photos/{foto['id']}/versions/annotate",
        headers=cab("consultor_a"),
        json={"annotations": {"shapes": []}},
    )
    cliente.patch(
        f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a"), json={"display_name": "Otro"}
    )
    versiones = cliente.get(
        f"{RUTA}/photos/{foto['id']}/versions", headers=cab("consultor_a")
    ).json()
    assert versiones[0]["version_type"] == "ORIGINAL"
    assert versiones[0]["version_number"] == 1


# ─────────────────────────────────────────────────────────────────────────────
#  Clasificación en lote
# ─────────────────────────────────────────────────────────────────────────────


def test_se_clasifican_varias_fotos_de_una_vez(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Engine
) -> None:
    """Es la operación que hace usable una visita de 400 fotos: seleccionar las
    de la cubierta y asignarlas de una vez."""
    with motor_admin.begin() as conn:
        tipologia = conn.execute(text("SELECT id FROM asset_typology LIMIT 1")).scalar_one()
    activo = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={"name": "Nave A", "typology_id": str(tipologia)},
    ).json()

    ids = [subir(cliente, cab, proyecto)["id"] for _ in range(4)]
    r = cliente.post(
        f"{RUTA}/photos/bulk-update",
        headers=cab("consultor_a"),
        json={
            "photo_ids": ids,
            "asset_id": activo["id"],
            "photo_category": "Cubierta",
            "include_in_report": True,
        },
    )
    assert r.status_code == 200
    assert all(f["asset_id"] == activo["id"] for f in r.json())
    assert all(f["include_in_report"] for f in r.json())


def test_las_etiquetas_se_anaden_sin_borrar_las_existentes(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """Sustituirlas borraría en silencio el trabajo de clasificación de otra
    persona."""
    foto = subir(cliente, cab, proyecto)
    cliente.patch(
        f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a"), json={"tags": ["fisuras"]}
    )
    r = cliente.post(
        f"{RUTA}/photos/bulk-update",
        headers=cab("consultor_a"),
        json={"photo_ids": [foto["id"]], "add_tags": ["solera", "aparcamiento"]},
    )
    assert set(r.json()[0]["tags"]) == {"fisuras", "solera", "aparcamiento"}


def test_una_etiqueta_repetida_no_se_duplica(cliente: TestClient, cab: Any, proyecto: str) -> None:
    foto = subir(cliente, cab, proyecto)
    for _ in range(2):
        cliente.post(
            f"{RUTA}/photos/bulk-update",
            headers=cab("consultor_a"),
            json={"photo_ids": [foto["id"]], "add_tags": ["corrosion"]},
        )
    r = cliente.get(f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a")).json()
    assert r["tags"] == ["corrosion"]


# ─────────────────────────────────────────────────────────────────────────────
#  Descarga en lote §15.6 y §15.7
# ─────────────────────────────────────────────────────────────────────────────


def test_el_zip_lleva_las_fotos_con_su_nombre_visible(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """Es lo que hace navegable un ZIP de 400 fotos."""
    ids = []
    for nombre in ("Cubierta 001", "Cubierta 002"):
        foto = subir(cliente, cab, proyecto)
        cliente.patch(
            f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a"), json={"display_name": nombre}
        )
        ids.append(foto["id"])

    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/photos/download-batch",
        headers=cab("consultor_a"),
        json={"photo_ids": ids, "use_display_names": True},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        assert sorted(z.namelist()) == ["Cubierta001.jpg", "Cubierta002.jpg"]


def test_el_zip_no_lleva_gps_por_defecto(cliente: TestClient, cab: Any, proyecto: str) -> None:
    """`[REQ]` §15.6 · La exportación para el cliente elimina GPS y número de
    serie del dispositivo. Se comprueba releyendo lo que sale del ZIP."""
    from tdd.evidence.images import leer

    foto = subir(cliente, cab, proyecto, con_exif(foto_unica(), gps=(40.416775, -3.703790)))
    assert foto["gps_latitude"] is not None, "la original sí trae coordenadas"

    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/photos/download-batch",
        headers=cab("consultor_a"),
        json={"photo_ids": [foto["id"]]},
    )
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        exportada = z.read(z.namelist()[0])
    assert leer(exportada).coordenadas is None
    assert leer(exportada).camara is None


def test_la_descarga_interna_si_conserva_el_exif(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """La descarga del original es la evidencia: ahí el EXIF completo se
    conserva, y esa asimetría es deliberada."""
    from tdd.evidence.images import leer

    datos = con_exif(foto_unica(), gps=(40.4, -3.7))
    foto = subir(cliente, cab, proyecto, datos)
    r = cliente.get(f"{RUTA}/photos/{foto['id']}/download", headers=cab("consultor_a"))
    assert leer(r.content).coordenadas is not None


def test_los_nombres_repetidos_no_se_pisan_dentro_del_zip(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """Dentro de un ZIP dos ficheros pueden llamarse igual, y al descomprimir
    uno pisa al otro sin avisar."""
    ids = []
    for _ in range(3):
        foto = subir(cliente, cab, proyecto)
        cliente.patch(
            f"{RUTA}/photos/{foto['id']}",
            headers=cab("consultor_a"),
            json={"display_name": "Igual"},
        )
        ids.append(foto["id"])

    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/photos/download-batch",
        headers=cab("consultor_a"),
        json={"photo_ids": ids},
    )
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        assert len(set(z.namelist())) == 3


def test_pedir_fotos_que_no_estan_da_404(cliente: TestClient, cab: Any, proyecto: str) -> None:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/photos/download-batch",
        headers=cab("consultor_a"),
        json={"photo_ids": [str(uuid.uuid4())]},
    )
    assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
#  Purga §15.9
# ─────────────────────────────────────────────────────────────────────────────


def _a_la_papelera_hace(motor_admin: Engine, photo_id: str, dias: int) -> None:
    """Envejece la papelera sin esperar. La alternativa sería no probar nunca
    la retención."""
    with motor_admin.begin() as conn:
        conn.execute(
            text(
                "UPDATE photo SET status = 'PAPELERA', "
                "deleted_at = now() - make_interval(days => :d) WHERE id = :i"
            ),
            {"d": dias, "i": photo_id},
        )


def test_la_purga_exige_confirmacion_explicita(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Engine
) -> None:
    foto = subir(cliente, cab, proyecto)
    _a_la_papelera_hace(motor_admin, foto["id"], 40)
    r = cliente.post(
        f"{RUTA}/photos/{foto['id']}/purge",
        headers=cab("admin_a"),
        json={"confirmar": False, "motivo": "Solicitud de borrado del cliente"},
    )
    assert r.status_code == 422


def test_la_purga_exige_motivo(cliente: TestClient, cab: Any, proyecto: str) -> None:
    foto = subir(cliente, cab, proyecto)
    r = cliente.post(
        f"{RUTA}/photos/{foto['id']}/purge",
        headers=cab("admin_a"),
        json={"confirmar": True, "motivo": "corto"},
    )
    assert r.status_code == 422


def test_un_consultor_no_puede_purgar(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Engine
) -> None:
    foto = subir(cliente, cab, proyecto)
    _a_la_papelera_hace(motor_admin, foto["id"], 40)
    r = cliente.post(
        f"{RUTA}/photos/{foto['id']}/purge",
        headers=cab("consultor_a"),
        json={"confirmar": True, "motivo": "Solicitud de borrado del cliente"},
    )
    assert r.status_code == 403


def test_no_se_purga_antes_de_cumplir_la_retencion(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Engine
) -> None:
    foto = subir(cliente, cab, proyecto)
    _a_la_papelera_hace(motor_admin, foto["id"], 3)
    r = cliente.post(
        f"{RUTA}/photos/{foto['id']}/purge",
        headers=cab("admin_a"),
        json={"confirmar": True, "motivo": "Solicitud de borrado del cliente"},
    )
    assert r.status_code == 409
    assert r.headers["X-Motivo"] == "RETENTION_NOT_ELAPSED"


def test_no_se_purga_lo_que_esta_en_un_informe_emitido(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Engine
) -> None:
    """`[REC]` Un informe emitido debe seguir siendo reproducible. Esta guarda
    se aplica aunque la retención esté cumplida de sobra."""
    foto = subir(cliente, cab, proyecto)
    cliente.post(
        f"{RUTA}/photos/{foto['id']}/links",
        headers=cab("consultor_a"),
        json={"entity_type": "REPORT_SECTION", "entity_id": str(uuid.uuid4())},
    )
    _a_la_papelera_hace(motor_admin, foto["id"], 400)

    r = cliente.post(
        f"{RUTA}/photos/{foto['id']}/purge",
        headers=cab("admin_a"),
        json={"confirmar": True, "motivo": "Solicitud de borrado del cliente"},
    )
    assert r.status_code == 409
    assert r.headers["X-Motivo"] == "REFERENCED_BY_ISSUED_REPORT"


def test_la_purga_conserva_el_registro_de_auditoria_sin_contenido(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Engine
) -> None:
    """`[REQ]` §15.9 · Queda identificador, hash, quién la subió, quién la
    purgó y con qué autorización. Sin contenido."""
    foto = subir(cliente, cab, proyecto, con_exif(foto_unica(), gps=(40.4, -3.7)))
    _a_la_papelera_hace(motor_admin, foto["id"], 40)

    r = cliente.post(
        f"{RUTA}/photos/{foto['id']}/purge",
        headers=cab("admin_a"),
        json={"confirmar": True, "motivo": "Solicitud expresa del cliente por escrito"},
    )
    assert r.status_code == 204

    with motor_admin.begin() as conn:
        traza = conn.execute(
            text(
                "SELECT after_data FROM audit_log WHERE entity_id = :i AND action = 'PHOTO_PURGED'"
            ),
            {"i": foto["id"]},
        ).scalar_one()
        fila = conn.execute(
            text(
                "SELECT CAST(status AS text) AS status, gps_latitude, caption, exif_raw, sha256 "
                "FROM photo WHERE id = :i"
            ),
            {"i": foto["id"]},
        ).one()

    assert traza["sha256"] == foto["sha256"]
    assert "cliente" in traza["motivo"]
    assert fila.status == "PURGADA"
    assert fila.gps_latitude is None, "el contenido personal desaparece"
    assert fila.sha256 == foto["sha256"], "la huella se conserva para la auditoría"


def test_una_foto_purgada_no_vuelve(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Engine
) -> None:
    foto = subir(cliente, cab, proyecto)
    _a_la_papelera_hace(motor_admin, foto["id"], 40)
    cliente.post(
        f"{RUTA}/photos/{foto['id']}/purge",
        headers=cab("admin_a"),
        json={"confirmar": True, "motivo": "Solicitud expresa del cliente por escrito"},
    )
    r = cliente.post(f"{RUTA}/photos/{foto['id']}/restore", headers=cab("consultor_a"))
    assert r.status_code == 409
