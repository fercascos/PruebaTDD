"""Fotografías: API y garantías de la base de datos `[REQ]` §15.

Las tres formas de subir que pidió el cliente —ordenador, carrete del móvil y
cámara en directo— son el mismo endpoint con distinto contenido. Lo que cambia
es lo que trae el fichero, y eso es justo lo que se prueba aquí.

`[REQ]` Ni una fotografía real: todas se generan con Pillow en el momento.
"""

from __future__ import annotations

import io
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import text

from tests.unit.test_imagenes import con_exif, imagen

pytestmark = pytest.mark.db

RUTA = "/api/v1"


@pytest.fixture(scope="module")
def proyecto(datos_base: dict[str, uuid.UUID]) -> str:
    return str(datos_base["proyecto_a"])


@pytest.fixture
def activo(motor_admin: Any, datos_base: dict[str, uuid.UUID]) -> str:
    with motor_admin.begin() as conn:
        tipologia = conn.execute(text("SELECT id FROM asset_typology LIMIT 1")).scalar_one()
        return str(
            conn.execute(
                text(
                    "INSERT INTO asset (organization_id, project_id, typology_id, name) "
                    "VALUES (:o, :p, :t, 'Nave A') RETURNING id"
                ),
                {
                    "o": str(datos_base["org_a"]),
                    "p": str(datos_base["proyecto_a"]),
                    "t": str(tipologia),
                },
            ).scalar_one()
        )


def subir(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    datos: bytes,
    *,
    nombre: str = "IMG_4821.jpg",
    usuario: str = "consultor_a",
    **campos: Any,
) -> Any:
    return cliente.post(
        f"{RUTA}/projects/{proyecto}/photos",
        headers=cab(usuario),
        files={"file": (nombre, io.BytesIO(datos), "image/jpeg")},
        data={k: str(v) for k, v in campos.items()},
    )


def foto_unica(color: tuple[int, int, int] | None = None) -> bytes:
    """Una imagen distinta cada vez: el índice único por `sha256` es real."""
    import random

    return imagen(color=color or (random.randrange(256), random.randrange(256), 90))


# ─────────────────────────────────────────────────────────────────────────────
#  Los tres orígenes
# ─────────────────────────────────────────────────────────────────────────────


def test_subida_desde_el_ordenador(cliente: TestClient, cab: Any, proyecto: str) -> None:
    r = subir(cliente, cab, proyecto, foto_unica(), origin="ORDENADOR")
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["status"] == "LISTA"
    assert cuerpo["origin"] == "ORDENADOR"
    assert cuerpo["file_extension"] == "jpg"
    assert len(cuerpo["sha256"]) == 64


def test_subida_desde_el_carrete_del_movil_con_gps(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """El carrete trae coordenadas. Se promocionan a columnas para poder pintar
    el mapa de fotografías por activo."""
    datos = con_exif(foto_unica(), gps=(40.416775, -3.703790))
    cuerpo = subir(cliente, cab, proyecto, datos, nombre="IMG_0042.HEIC", origin="CARRETE").json()

    assert cuerpo["origin"] == "CARRETE"
    assert cuerpo["gps_latitude"] == pytest.approx(40.416775, abs=1e-4)
    assert cuerpo["gps_longitude"] == pytest.approx(-3.703790, abs=1e-4)
    assert cuerpo["taken_at"] is not None


def test_subida_desde_la_camara_en_directo_con_orientacion(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """La cámara en directo trae orientación EXIF. La miniatura debe salir
    derecha aunque los píxeles lleguen tumbados."""
    datos = con_exif(imagen(800, 400, color=(11, 22, 33)), orientacion=6)
    r = subir(cliente, cab, proyecto, datos, nombre="captura.jpg", origin="CAMARA")

    cuerpo = r.json()
    assert cuerpo["origin"] == "CAMARA"
    assert cuerpo["width_px"] == 800, "el original conserva sus píxeles tal cual"


def test_el_heic_del_carrete_se_sube_y_se_convierte(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Any
) -> None:
    """El formato por defecto de un iPhone entra sin conversión previa, y sus
    derivados salen en JPEG para que los abra cualquiera."""
    salida = io.BytesIO()
    with Image.open(io.BytesIO(foto_unica())) as img:
        img.save(salida, format="HEIF")

    r = subir(cliente, cab, proyecto, salida.getvalue(), nombre="IMG_0117.HEIC", origin="CARRETE")
    assert r.status_code == 201, r.text
    assert r.json()["file_extension"] == "heic"
    assert r.json()["mime_type"] == "image/heic"

    with motor_admin.begin() as conn:
        mimes = (
            conn.execute(
                text(
                    "SELECT DISTINCT o.mime_type FROM photo_derivative d "
                    "JOIN stored_object o ON o.id = d.stored_object_id WHERE d.photo_id = :i"
                ),
                {"i": r.json()["id"]},
            )
            .scalars()
            .all()
        )
    assert mimes == ["image/jpeg"]


def test_un_origen_desconocido_no_rompe_la_subida(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """El servidor no se fía de lo que el cliente diga sobre la procedencia:
    es un dato descriptivo, no un permiso."""
    cuerpo = subir(cliente, cab, proyecto, foto_unica(), origin="TELEPATIA").json()
    assert cuerpo["origin"] == "ORDENADOR"


def test_la_miniatura_se_genera_al_subir(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Any
) -> None:
    foto = subir(cliente, cab, proyecto, imagen(1600, 1200, color=(70, 80, 90))).json()
    with motor_admin.begin() as conn:
        clases = (
            conn.execute(
                text("SELECT kind::text FROM photo_derivative WHERE photo_id = :i ORDER BY kind"),
                {"i": foto["id"]},
            )
            .scalars()
            .all()
        )
    assert clases == ["MINIATURA_320", "VISTA_1600"]


def test_los_derivados_no_llevan_metadatos(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Any
) -> None:
    """`[REQ]` §15.6 · Lo que se inserta en el PPTX son solo píxeles."""
    datos = con_exif(foto_unica(), gps=(40.4, -3.7))
    foto = subir(cliente, cab, proyecto, datos).json()
    with motor_admin.begin() as conn:
        assert conn.execute(
            text("SELECT bool_and(NOT has_metadata) FROM photo_derivative WHERE photo_id = :i"),
            {"i": foto["id"]},
        ).scalar_one()


# ─────────────────────────────────────────────────────────────────────────────
#  Validación de entrada
# ─────────────────────────────────────────────────────────────────────────────


def test_un_fichero_que_no_es_imagen_se_rechaza_con_415(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    r = subir(cliente, cab, proyecto, b"MZ\x90\x00 ejecutable", nombre="virus.jpg")
    assert r.status_code == 415


def test_el_tipo_real_manda_sobre_la_extension_del_nombre(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """Alguien renombra un PNG a `.jpg`. La extensión que se guarda es la del
    contenido, no la del nombre."""
    png = imagen(color=(200, 30, 40), formato="PNG")
    cuerpo = subir(cliente, cab, proyecto, png, nombre="foto.jpg").json()
    assert cuerpo["file_extension"] == "png"
    assert cuerpo["mime_type"] == "image/png"


def test_la_foto_sin_activo_se_acepta_con_aviso(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """`[REQ]` §10.7 regla 4 · Con aviso, no con error: en campo se fotografía
    antes de saber a qué activo corresponde."""
    r = subir(cliente, cab, proyecto, foto_unica())
    assert r.status_code == 201
    assert any("activo" in a for a in r.json()["avisos"])


def test_sin_fecha_exif_el_campo_queda_vacio_y_se_avisa(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """`[REQ]` No se sustituye por `now()`: sería inventar la evidencia."""
    cuerpo = subir(cliente, cab, proyecto, foto_unica()).json()
    assert cuerpo["taken_at"] is None
    assert any("fecha" in a for a in cuerpo["avisos"])


# ─────────────────────────────────────────────────────────────────────────────
#  Duplicados §15.5
# ─────────────────────────────────────────────────────────────────────────────


def test_el_mismo_fichero_dos_veces_se_rechaza_con_409(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    datos = foto_unica()
    assert subir(cliente, cab, proyecto, datos).status_code == 201
    r = subir(cliente, cab, proyecto, datos)
    assert r.status_code == 409
    assert "ya está en el proyecto" in r.json()["detail"]


def test_el_duplicado_exacto_no_se_puede_forzar_y_se_dice_cuál_es(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """No hay «subir de todas formas»: el índice único de §15.5 lo impide en la
    base de datos, así que forzarlo solo produciría un error más feo y más
    tarde. Lo útil es decir **qué** fotografía es la que ya está."""
    datos = foto_unica()
    ya = subir(cliente, cab, proyecto, datos).json()

    r = subir(cliente, cab, proyecto, datos)
    assert r.status_code == 409
    assert ya["id"] in r.json()["detail"]

    # Y la que ya estaba sigue intacta: el rechazo no toca nada.
    sigue = cliente.get(f"{RUTA}/photos/{ya['id']}", headers=cab("consultor_a")).json()
    assert sigue["sha256"] == ya["sha256"]


def test_el_casi_duplicado_se_sube_y_solo_se_avisa(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """La misma foto recomprimida: distinto `sha256`, misma escena."""
    original = imagen(600, 400, color=(31, 41, 59))
    subir(cliente, cab, proyecto, original, nombre="a.jpg")

    salida = io.BytesIO()
    with Image.open(io.BytesIO(original)) as img:
        img.resize((300, 200)).save(salida, format="JPEG", quality=50)

    r = subir(cliente, cab, proyecto, salida.getvalue(), nombre="b.jpg")
    assert r.status_code == 201
    assert r.json()["duplicado"]["tipo"] == "CASI"


def test_el_mismo_fichero_si_puede_estar_en_dos_proyectos(
    cliente: TestClient, cab: Any, datos_base: dict[str, uuid.UUID], motor_admin: Any
) -> None:
    """Dos encargos sobre el mismo edificio es legítimo."""
    with motor_admin.begin() as conn:
        otro = conn.execute(
            text(
                "INSERT INTO project (organization_id, client_id, internal_code, name) "
                "VALUES (:o, :c, :cod, 'Segundo encargo') RETURNING id"
            ),
            {
                "o": str(datos_base["org_a"]),
                "c": str(datos_base["cliente_a"]),
                "cod": f"DUP-{uuid.uuid4().hex[:6]}",
            },
        ).scalar_one()

    datos = foto_unica()
    assert subir(cliente, cab, str(datos_base["proyecto_a"]), datos).status_code == 201
    assert subir(cliente, cab, str(otro), datos).status_code == 201


def test_los_duplicados_se_agrupan_para_revisarlos(
    cliente: TestClient, cab: Any, datos_base: dict[str, uuid.UUID], motor_admin: Any
) -> None:
    with motor_admin.begin() as conn:
        limpio = conn.execute(
            text(
                "INSERT INTO project (organization_id, client_id, internal_code, name) "
                "VALUES (:o, :c, :cod, 'Proyecto de duplicados') RETURNING id"
            ),
            {
                "o": str(datos_base["org_a"]),
                "c": str(datos_base["cliente_a"]),
                "cod": f"GRP-{uuid.uuid4().hex[:6]}",
            },
        ).scalar_one()

    # Dos disparos de la misma escena: distinto fichero, misma foto. El exacto
    # no puede coexistir en un proyecto, así que el grupo lo forman casi
    # duplicados, que es además el caso que de verdad hay que revisar a ojo.
    original = imagen(600, 400, color=(90, 120, 150))
    subir(cliente, cab, str(limpio), original, nombre="a.jpg")

    recomprimida = io.BytesIO()
    with Image.open(io.BytesIO(original)) as img:
        img.resize((300, 200)).save(recomprimida, format="JPEG", quality=40)
    subir(cliente, cab, str(limpio), recomprimida.getvalue(), nombre="b.jpg")

    r = cliente.get(f"{RUTA}/projects/{limpio}/photos/duplicates", headers=cab("consultor_a"))
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert len(r.json()[0]["photo_ids"]) == 2


# ─────────────────────────────────────────────────────────────────────────────
#  La invariante: el original nunca se sobrescribe §15.1
# ─────────────────────────────────────────────────────────────────────────────


def test_renombrar_no_toca_el_binario(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Any
) -> None:
    """`[REQ]` La invariante del bloque. Renombrar es un `UPDATE` de texto: el
    `storage_key` y el `sha256` siguen siendo los mismos."""
    foto = subir(cliente, cab, proyecto, foto_unica()).json()
    with motor_admin.begin() as conn:
        antes = conn.execute(
            text(
                "SELECT o.storage_key, o.sha256 FROM stored_object o "
                "JOIN photo p ON p.stored_object_id = o.id WHERE p.id = :i"
            ),
            {"i": foto["id"]},
        ).one()

    r = cliente.patch(
        f"{RUTA}/photos/{foto['id']}",
        headers=cab("consultor_a"),
        json={"display_name": "Cubierta fisuras 001"},
    )
    assert r.status_code == 200
    assert r.json()["display_name"] == "Cubiertafisuras001"

    with motor_admin.begin() as conn:
        despues = conn.execute(
            text(
                "SELECT o.storage_key, o.sha256 FROM stored_object o "
                "JOIN photo p ON p.stored_object_id = o.id WHERE p.id = :i"
            ),
            {"i": foto["id"]},
        ).one()
    assert despues == antes


def test_la_base_de_datos_rechaza_reapuntar_el_original(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Any
) -> None:
    """Barrera 3. No depende de que la API se acuerde: se prueba saltándose la
    API por completo y escribiendo SQL directamente."""
    foto = subir(cliente, cab, proyecto, foto_unica()).json()
    with motor_admin.begin() as conn, pytest.raises(Exception, match="no se sobrescribe"):
        conn.execute(
            text("UPDATE photo SET sha256 = :s WHERE id = :i"),
            {"s": "f" * 64, "i": foto["id"]},
        )


def test_la_base_de_datos_rechaza_cambiar_la_extension(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Any
) -> None:
    """`[REQ]` La extensión se deriva del MIME real y el usuario nunca la
    controla: cambiarla convertiría un renombrado en una conversión de formato
    que nadie ha pedido."""
    foto = subir(cliente, cab, proyecto, foto_unica()).json()
    with motor_admin.begin() as conn, pytest.raises(Exception, match="no se sobrescribe"):
        conn.execute(
            text("UPDATE photo SET file_extension = 'png' WHERE id = :i"), {"i": foto["id"]}
        )


def test_la_api_rechaza_escribir_el_hash(cliente: TestClient, cab: Any, proyecto: str) -> None:
    """`[REQ]` §10.7 · `storage_key` y `sha256` no son escribibles: `422`. Y se
    rechaza, no se ignora: un cliente que los envíe está construido sobre una
    idea equivocada del modelo."""
    foto = subir(cliente, cab, proyecto, foto_unica()).json()
    r = cliente.patch(
        f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a"), json={"sha256": "0" * 64}
    )
    assert r.status_code == 422


def test_el_nombre_visible_se_envia_sin_extension(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    foto = subir(cliente, cab, proyecto, foto_unica()).json()
    r = cliente.patch(
        f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a"), json={"display_name": "foto.jpg"}
    )
    assert r.status_code == 422
    assert "sin extensión" in r.json()["detail"]


def test_renombrar_deja_una_version_sin_binario(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Any
) -> None:
    """`[REC]` §15.2 · Duplicar bytes por un cambio de nombre multiplicaría el
    coste sin aportar nada."""
    foto = subir(cliente, cab, proyecto, foto_unica()).json()
    cliente.patch(
        f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a"), json={"display_name": "Cubierta"}
    )
    with motor_admin.begin() as conn:
        versiones = conn.execute(
            text(
                "SELECT version_number, version_type::text, stored_object_id, is_current "
                "FROM photo_version WHERE photo_id = :i ORDER BY version_number"
            ),
            {"i": foto["id"]},
        ).all()

    assert [v.version_type for v in versiones] == ["ORIGINAL", "RENOMBRADA"]
    assert versiones[0].stored_object_id is not None
    assert versiones[1].stored_object_id is None
    assert [v.is_current for v in versiones] == [False, True]


def test_la_version_original_no_se_puede_borrar(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Any
) -> None:
    foto = subir(cliente, cab, proyecto, foto_unica()).json()
    with motor_admin.begin() as conn, pytest.raises(Exception, match="no se borra"):
        conn.execute(
            text("DELETE FROM photo_version WHERE photo_id = :i AND version_number = 1"),
            {"i": foto["id"]},
        )


def test_la_version_original_no_se_puede_renombrar(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Any
) -> None:
    """Restaurar una versión anterior crea una nueva; no reescribe la historia."""
    foto = subir(cliente, cab, proyecto, foto_unica()).json()
    with motor_admin.begin() as conn, pytest.raises(Exception, match="no se modifica"):
        conn.execute(
            text(
                "UPDATE photo_version SET display_name = 'otro' WHERE photo_id = :i "
                "AND version_number = 1"
            ),
            {"i": foto["id"]},
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Renombrado en lote §15.4
# ─────────────────────────────────────────────────────────────────────────────


def test_la_previsualizacion_no_escribe_nada(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REQ]` `dry_run` es el valor por defecto: la previsualización es
    obligatoria y no se puede saltar por descuido."""
    foto = subir(cliente, cab, proyecto, foto_unica(), asset_id=activo).json()
    r = cliente.post(
        f"{RUTA}/photos/bulk-rename",
        headers=cab("consultor_a"),
        json={"photo_ids": [foto["id"]], "numerar_desde": 1},
    )
    assert r.status_code == 200
    plan = r.json()
    assert plan["dry_run"] is True
    assert plan["aplicados"] == 0
    assert plan["cambios"][0]["antes"] == foto["display_name"]

    sigue = cliente.get(f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a")).json()
    assert sigue["display_name"] == foto["display_name"]


def test_el_renombrado_en_lote_aplica_la_plantilla(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    ids = [
        subir(cliente, cab, proyecto, foto_unica(), asset_id=activo).json()["id"] for _ in range(3)
    ]
    r = cliente.post(
        f"{RUTA}/photos/bulk-rename",
        headers=cab("consultor_a"),
        json={
            "photo_ids": ids,
            "template": "[Proyecto]_[Activo]_[Numero]",
            "dry_run": False,
            "numerar_desde": 1,
        },
    )
    assert r.status_code == 200
    assert r.json()["aplicados"] == 3
    assert r.json()["fallidos"] == []

    nombres = [
        cliente.get(f"{RUTA}/photos/{i}", headers=cab("consultor_a")).json()["display_name"]
        for i in ids
    ]
    assert nombres == ["2026-014_NaveA_001", "2026-014_NaveA_002", "2026-014_NaveA_003"]


# ─────────────────────────────────────────────────────────────────────────────
#  Papelera §15.9
# ─────────────────────────────────────────────────────────────────────────────


def test_borrar_una_foto_es_siempre_logico(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Any
) -> None:
    foto = subir(cliente, cab, proyecto, foto_unica()).json()
    assert (
        cliente.delete(f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a")).status_code == 204
    )

    with motor_admin.begin() as conn:
        fila = conn.execute(
            text("SELECT status::text, deleted_at FROM photo WHERE id = :i"), {"i": foto["id"]}
        ).one()
    assert fila.status == "PAPELERA"
    assert fila.deleted_at is not None


def test_la_foto_en_la_papelera_desaparece_del_listado_normal(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    foto = subir(cliente, cab, proyecto, foto_unica()).json()
    cliente.delete(f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a"))

    normal = cliente.get(f"{RUTA}/projects/{proyecto}/photos", headers=cab("consultor_a")).json()
    papelera = cliente.get(
        f"{RUTA}/projects/{proyecto}/photos?trash=true", headers=cab("consultor_a")
    ).json()

    assert foto["id"] not in [f["id"] for f in normal]
    assert foto["id"] in [f["id"] for f in papelera]


def test_la_foto_se_recupera_intacta(cliente: TestClient, cab: Any, proyecto: str) -> None:
    foto = subir(cliente, cab, proyecto, foto_unica()).json()
    cliente.delete(f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a"))

    r = cliente.post(f"{RUTA}/photos/{foto['id']}/restore", headers=cab("consultor_a"))
    assert r.status_code == 200
    assert r.json()["status"] == "LISTA"
    assert r.json()["sha256"] == foto["sha256"]


def test_borrar_dos_veces_es_un_conflicto_explicito(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    foto = subir(cliente, cab, proyecto, foto_unica()).json()
    cliente.delete(f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a"))
    r = cliente.delete(f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a"))
    assert r.status_code == 409


def test_la_base_de_datos_impide_el_borrado_fisico(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Any
) -> None:
    """Barrera 3 otra vez: aunque alguien escriba `DELETE` a mano."""
    foto = subir(cliente, cab, proyecto, foto_unica()).json()
    with motor_admin.begin() as conn, pytest.raises(Exception, match="no se borra físicamente"):
        conn.execute(text("DELETE FROM photo WHERE id = :i"), {"i": foto["id"]})


def test_la_foto_en_la_papelera_sale_del_informe(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """Si se quedara seleccionada, el informe fallaría al generarse o —peor—
    saldría con un hueco."""
    foto = subir(cliente, cab, proyecto, foto_unica()).json()
    cliente.patch(
        f"{RUTA}/photos/{foto['id']}",
        headers=cab("consultor_a"),
        json={"include_in_report": True, "caption": "Fisuras"},
    )
    cliente.delete(f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a"))

    en_papelera = cliente.get(f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a")).json()
    assert en_papelera["include_in_report"] is False


# ─────────────────────────────────────────────────────────────────────────────
#  Aislamiento, descarga y auditoría
# ─────────────────────────────────────────────────────────────────────────────


def test_otra_organizacion_no_ve_la_foto(cliente: TestClient, cab: Any, proyecto: str) -> None:
    """La RLS no distingue entre entidades: la foto queda fuera igual que todo
    lo demás. Se comprueba porque es la garantía número uno del sistema."""
    foto = subir(cliente, cab, proyecto, foto_unica()).json()
    r = cliente.get(f"{RUTA}/photos/{foto['id']}", headers=cab("admin_b"))
    assert r.status_code == 404


def test_la_descarga_queda_auditada(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Any
) -> None:
    """`[REQ]` §10.7 regla 3 · Toda descarga genera `audit_log`."""
    datos = foto_unica()
    foto = subir(cliente, cab, proyecto, datos).json()

    r = cliente.get(f"{RUTA}/photos/{foto['id']}/download", headers=cab("consultor_a"))
    assert r.status_code == 200
    assert r.content == datos, "se descarga el original, byte a byte"
    assert foto["display_name"] in r.headers["content-disposition"]

    with motor_admin.begin() as conn:
        acciones = (
            conn.execute(
                text("SELECT action FROM audit_log WHERE entity_id = :i ORDER BY occurred_at"),
                {"i": foto["id"]},
            )
            .scalars()
            .all()
        )
    assert "PHOTO_UPLOADED" in acciones
    assert "PHOTO_DOWNLOADED" in acciones


def test_el_renombrado_queda_auditado_con_el_antes_y_el_despues(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Any
) -> None:
    foto = subir(cliente, cab, proyecto, foto_unica()).json()
    cliente.patch(
        f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a"), json={"display_name": "Cubierta"}
    )
    with motor_admin.begin() as conn:
        traza = conn.execute(
            text(
                "SELECT after_data FROM audit_log WHERE entity_id = :i AND action = 'PHOTO_RENAMED'"
            ),
            {"i": foto["id"]},
        ).scalar_one()
    assert traza["antes"] == foto["display_name"]
    assert traza["despues"] == "Cubierta"


# ─────────────────────────────────────────────────────────────────────────────
#  Clasificación y avisos §15.10
# ─────────────────────────────────────────────────────────────────────────────


def test_se_clasifica_la_foto_y_se_selecciona_para_el_informe(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    foto = subir(cliente, cab, proyecto, foto_unica()).json()
    r = cliente.patch(
        f"{RUTA}/photos/{foto['id']}",
        headers=cab("consultor_a"),
        json={
            "asset_id": activo,
            "caption": "Fisuras en la solera del aparcamiento",
            "include_in_report": True,
            "report_order": 1,
            "tags": ["fisuras", "solera"],
        },
    )
    assert r.status_code == 200
    assert r.json()["include_in_report"] is True
    assert r.json()["tags"] == ["fisuras", "solera"]


def test_una_foto_seleccionada_sin_activo_genera_aviso(
    cliente: TestClient, cab: Any, datos_base: dict[str, uuid.UUID], motor_admin: Any
) -> None:
    with motor_admin.begin() as conn:
        limpio = conn.execute(
            text(
                "INSERT INTO project (organization_id, client_id, internal_code, name) "
                "VALUES (:o, :c, :cod, 'Proyecto de avisos') RETURNING id"
            ),
            {
                "o": str(datos_base["org_a"]),
                "c": str(datos_base["cliente_a"]),
                "cod": f"AVI-{uuid.uuid4().hex[:6]}",
            },
        ).scalar_one()

    foto = subir(cliente, cab, str(limpio), foto_unica()).json()
    cliente.patch(
        f"{RUTA}/photos/{foto['id']}",
        headers=cab("consultor_a"),
        json={"include_in_report": True, "caption": "Detalle"},
    )
    avisos = cliente.get(
        f"{RUTA}/projects/{limpio}/photos/report-warnings", headers=cab("consultor_a")
    ).json()
    assert {a["codigo"] for a in avisos} == {"PHOTO_WITHOUT_ASSET"}


def test_la_foto_se_asocia_a_varias_entidades(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REQ]` Asociación múltiple: la misma foto documenta el activo y sirve
    de evidencia de un hallazgo."""
    foto = subir(cliente, cab, proyecto, foto_unica()).json()
    for tipo, entidad, papel in (
        ("ASSET", activo, "GENERAL"),
        ("REPORT_SECTION", str(uuid.uuid4()), "DETALLE"),
    ):
        r = cliente.post(
            f"{RUTA}/photos/{foto['id']}/links",
            headers=cab("consultor_a"),
            json={"entity_type": tipo, "entity_id": entidad, "role": papel},
        )
        assert r.status_code == 201


def test_el_listado_filtra_por_activo_y_por_gps(
    cliente: TestClient, cab: Any, datos_base: dict[str, uuid.UUID], motor_admin: Any
) -> None:
    with motor_admin.begin() as conn:
        limpio = conn.execute(
            text(
                "INSERT INTO project (organization_id, client_id, internal_code, name) "
                "VALUES (:o, :c, :cod, 'Proyecto de filtros') RETURNING id"
            ),
            {
                "o": str(datos_base["org_a"]),
                "c": str(datos_base["cliente_a"]),
                "cod": f"FIL-{uuid.uuid4().hex[:6]}",
            },
        ).scalar_one()

    subir(cliente, cab, str(limpio), foto_unica(), nombre="sin_gps.jpg")
    subir(
        cliente,
        cab,
        str(limpio),
        con_exif(foto_unica(), gps=(40.4, -3.7)),
        nombre="con_gps.jpg",
    )

    con = cliente.get(
        f"{RUTA}/projects/{limpio}/photos?has_gps=true", headers=cab("consultor_a")
    ).json()
    sin = cliente.get(
        f"{RUTA}/projects/{limpio}/photos?has_gps=false", headers=cab("consultor_a")
    ).json()
    assert len(con) == 1
    assert len(sin) == 1
