"""`[REQ]` P-31 · El botón de exportar el CAPEX a XLSX.

> *«añade en la aplicación un botón de exportar el CAPEX a xlsx para que el
> equipo pueda adjuntar el fichero en el posterior envío que hagan fuera de la
> plataforma»*

El generador del libro estaba escrito y probado desde el principio, pero **no
había ninguna ruta que lo sirviera**: el botón no habría tenido a dónde llamar.
Se detectó recorriendo la aplicación en marcha, y estas pruebas son lo que lo
habría detectado antes.

Lo que se comprueba no es solo que devuelva 200: que el fichero sea un libro
de verdad, que **incluya las líneas en borrador** —el equipo comparte el CAPEX
mientras lo está construyendo— y que **excluya las descartadas**.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

pytestmark = pytest.mark.db

RUTA = "/api/v1"
EXPORTACION = f"{RUTA}/projects/{{}}/capex/export.xlsx"
TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture(scope="module")
def catalogo(motor_admin: Engine) -> dict[str, str]:
    with motor_admin.begin() as conn:
        tipologia = conn.execute(
            text("SELECT id FROM asset_typology ORDER BY sort_order LIMIT 1")
        ).scalar_one()
        zona = conn.execute(
            text(
                "SELECT z.id FROM zone z JOIN zone_typology zt ON zt.zone_id = z.id "
                "WHERE zt.typology_id = :t ORDER BY z.sort_order LIMIT 1"
            ),
            {"t": tipologia},
        ).scalar_one()
        codigo = conn.execute(
            text("SELECT id FROM capex_code WHERE level = 3 ORDER BY code LIMIT 1")
        ).scalar_one()
    return {"tipologia": str(tipologia), "zona": str(zona), "codigo": str(codigo)}


@pytest.fixture
def proyecto(motor_admin: Engine, datos_base: dict[str, uuid.UUID]) -> str:
    with motor_admin.begin() as conn:
        return str(
            conn.execute(
                text(
                    "INSERT INTO project (organization_id, client_id, internal_code, name) "
                    "VALUES (:o, :c, :cod, 'Encargo exportable') RETURNING id"
                ),
                {
                    "o": str(datos_base["org_a"]),
                    "c": str(datos_base["cliente_a"]),
                    "cod": f"EXP-{uuid.uuid4().hex[:6]}",
                },
            ).scalar_one()
        )


@pytest.fixture
def activo(cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, str]) -> str:
    return str(
        cliente.post(
            f"{RUTA}/projects/{proyecto}/assets",
            headers=cab("consultor_a"),
            json={"name": "Nave A", "typology_id": catalogo["tipologia"]},
        ).json()["id"]
    )


def crear_hallazgo(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    catalogo: dict[str, str],
    activo: str,
    *,
    titulo: str,
    importe: str,
) -> str:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/findings",
        headers=cab("consultor_a"),
        json={
            "asset_id": activo,
            "capex_code_id": catalogo["codigo"],
            "zone_id": catalogo["zona"],
            "title": titulo,
            "description": "Anotado en visita.",
            "capex_lines": [{"time_horizon_code": "CORTO", "amount": importe}],
        },
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def hojas(contenido: bytes) -> list[str]:
    """Los nombres de hoja, leyendo el XLSX como el ZIP que es.

    Se abre el fichero de verdad en vez de fiarse del `Content-Type`: una
    cabecera correcta sobre un cuerpo corrupto es exactamente el fallo que un
    adjunto de correo no perdona.
    """
    import re
    from xml.sax.saxutils import unescape

    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        libro = z.read("xl/workbook.xml").decode("utf-8")
    # Solo los `<sheet name=...>`: `name=` también lo llevan los nombres
    # definidos, y la plantilla del cliente trae veintitantos.
    return [unescape(n) for n in re.findall(r'<sheet name="([^"]+)"', libro)]


def test_el_libro_se_descarga_y_se_abre(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, str], activo: str
) -> None:
    crear_hallazgo(
        cliente, cab, proyecto, catalogo, activo, titulo="Cubierta agotada", importe="36125.00"
    )

    r = cliente.get(EXPORTACION.format(proyecto), headers=cab("consultor_a"))

    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == TIPO_XLSX
    assert r.content[:2] == b"PK", "no es un ZIP: el libro está corrupto"
    # Sale la plantilla del cliente entera, no una hoja construida a mano: sus
    # siete hojas con los gráficos, las dinámicas y las listas.
    assert hojas(r.content) == [
        "00 Datos Categorías",
        "00 Datos Objeto",
        "00 Datos Activo",
        "Leyenda",
        "CapEx",
        "Resumen CapEx",
        "Gráficas & Desglose Hard Costs",
    ]


def test_el_nombre_del_fichero_lleva_el_codigo_del_encargo(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    catalogo: dict[str, str],
    activo: str,
    motor_admin: Engine,
) -> None:
    """El equipo adjunta varios en el mismo correo: `export.xlsx` repetido no
    sirve para nada."""
    crear_hallazgo(cliente, cab, proyecto, catalogo, activo, titulo="Fisuras", importe="1200.00")
    with motor_admin.begin() as conn:
        codigo = conn.execute(
            text("SELECT internal_code FROM project WHERE id = :p"), {"p": proyecto}
        ).scalar_one()

    r = cliente.get(EXPORTACION.format(proyecto), headers=cab("consultor_a"))
    assert codigo in r.headers["content-disposition"]


def test_un_encargo_sin_capex_no_devuelve_un_libro_vacio(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """`[REQ]` Un Excel con la cabecera y ninguna fila se adjunta a un correo
    sin que nadie note que no lleva nada dentro."""
    r = cliente.get(EXPORTACION.format(proyecto), headers=cab("consultor_a"))
    assert r.status_code == 409
    assert "actuación" in r.json()["detail"]


def test_incluye_los_hallazgos_en_borrador(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, str], activo: str
) -> None:
    """`[REQ]` El informe deja fuera los borradores; **esta exportación no**.

    Es un fichero de trabajo: si se dejara fuera lo que aún está en borrador, el
    total del Excel no cuadraría con el de la pantalla desde la que se pulsó el
    botón, y nadie sabría cuál de los dos creer.
    """
    crear_hallazgo(
        cliente, cab, proyecto, catalogo, activo, titulo="Recién anotado", importe="7500.00"
    )
    # Sin ninguna transición: el hallazgo sigue en BORRADOR.
    r = cliente.get(EXPORTACION.format(proyecto), headers=cab("consultor_a"))
    assert r.status_code == 200, r.text


def test_lo_descartado_se_queda_fuera(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    catalogo: dict[str, str],
    activo: str,
    motor_admin: Engine,
) -> None:
    """Descartar una actuación es decir que no se hace. Sumarla al total del
    fichero que se envía la resucitaría por la puerta de atrás."""
    descartado = crear_hallazgo(
        cliente, cab, proyecto, catalogo, activo, titulo="Descartado", importe="99999.00"
    )
    with motor_admin.begin() as conn:
        conn.execute(
            text("UPDATE finding SET status = 'DESCARTADO' WHERE id = :i"), {"i": descartado}
        )

    r = cliente.get(EXPORTACION.format(proyecto), headers=cab("consultor_a"))
    assert r.status_code == 409, "sin más hallazgos, el único que quedaba estaba descartado"


def test_otra_organizacion_no_exporta_el_capex_ajeno(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, str], activo: str
) -> None:
    crear_hallazgo(cliente, cab, proyecto, catalogo, activo, titulo="Privado", importe="500.00")
    r = cliente.get(EXPORTACION.format(proyecto), headers=cab("admin_b"))
    assert r.status_code in (404, 409), r.text
    assert r.status_code != 200


def test_el_lector_tambien_puede_exportar(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, str], activo: str
) -> None:
    """`[SUP]` Exportar es leer. Un `LECTOR` que ve la tabla en pantalla puede
    llevársela en Excel: negárselo no protegería nada."""
    crear_hallazgo(cliente, cab, proyecto, catalogo, activo, titulo="Legible", importe="800.00")
    r = cliente.get(EXPORTACION.format(proyecto), headers=cab("lector_a"))
    assert r.status_code == 200, r.text


# ─────────────────────────────────────────────────────────────────────────────
#  La plantilla del cliente, rellenada
# ─────────────────────────────────────────────────────────────────────────────


def _capex(contenido: bytes):
    from openpyxl import load_workbook

    return load_workbook(io.BytesIO(contenido))["CapEx"]


def test_la_actuacion_llega_a_su_bloque_de_la_plantilla(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, str], activo: str
) -> None:
    """No basta con que el fichero se abra: hay que ver el dato dentro, y en la
    fila que le toca por su capítulo."""
    crear_hallazgo(
        cliente, cab, proyecto, catalogo, activo, titulo="Cubierta agotada", importe="36125.00"
    )
    r = cliente.get(EXPORTACION.format(proyecto), headers=cab("consultor_a"))
    hoja = _capex(r.content)

    descripciones = [hoja[f"G{fila}"].value for fila in range(14, 255) if hoja[f"G{fila}"].value]
    assert "Cubierta agotada" in descripciones


def test_el_idioma_elige_la_plantilla(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, str], activo: str
) -> None:
    """`[REQ]` Al extraer el informe se elige español o inglés, y el Excel tiene
    que salir en el mismo idioma que el PowerPoint que lo acompaña."""
    crear_hallazgo(cliente, cab, proyecto, catalogo, activo, titulo="Roof", importe="1000.00")

    es = cliente.get(EXPORTACION.format(proyecto), headers=cab("consultor_a"))
    en = cliente.get(f"{EXPORTACION.format(proyecto)}?idioma=en", headers=cab("consultor_a"))
    assert (es.status_code, en.status_code) == (200, 200)

    from openpyxl import load_workbook

    assert load_workbook(io.BytesIO(es.content)).sheetnames[0] == "00 Datos Categorías"
    assert load_workbook(io.BytesIO(en.content)).sheetnames[0] == "00 Category Data"


def test_un_idioma_sin_plantilla_se_rechaza_con_422(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """Y no con un 500 al no encontrar el fichero: el error es de quien llama."""
    r = cliente.get(f"{EXPORTACION.format(proyecto)}?idioma=fr", headers=cab("consultor_a"))
    assert r.status_code == 422
    assert "es" in r.text and "en" in r.text


def test_mas_actuaciones_de_las_que_caben_dan_409_y_dicen_cual(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, str], activo: str
) -> None:
    """`[LIM]` Cada capítulo admite diez filas. La undécima no cabe, y lo que no
    puede pasar es que se pierda en silencio: se corta la descarga diciendo qué
    capítulo se pasa y por cuánto."""
    for i in range(11):
        crear_hallazgo(
            cliente, cab, proyecto, catalogo, activo, titulo=f"Actuación {i}", importe="100.00"
        )
    r = cliente.get(EXPORTACION.format(proyecto), headers=cab("consultor_a"))
    assert r.status_code == 409
    assert "11 de 10" in r.json()["detail"]
