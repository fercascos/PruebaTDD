"""Las fotografías situadas sobre el terreno `[REQ]` §15.9.

Lo que más importa aquí no es que devuelva las coordenadas: es que **diga
cuántas fotografías no las tienen**. Un mapa con cuatro chinchetas parece decir
«se hicieron cuatro fotos» cuando lo que dice es «cuatro traían GPS», y en una
visita a un sótano no hay señal ni localización.
"""

from __future__ import annotations

import io
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.unit.test_imagenes import con_exif, imagen

pytestmark = pytest.mark.db

RUTA = "/api/v1"

#: Coordenadas de sitios que no son de ningún cliente: el Retiro y Chamartín.
#: `[REQ]` No se usan datos reales de activos identificables.
RETIRO = (40.4153, -3.6844)
CHAMARTIN = (40.4720, -3.6828)
#: Hemisferio sur y occidental: es donde se ve si el signo se pierde por el
#: camino. Montevideo.
SUR = (-34.9011, -56.1645)


@pytest.fixture
def proyecto(motor_admin: Engine, datos_base: dict[str, uuid.UUID]) -> str:
    with motor_admin.begin() as conn:
        return str(
            conn.execute(
                text(
                    "INSERT INTO project (organization_id, client_id, internal_code, name) "
                    "VALUES (:o, :c, :cod, 'Encargo con mapa') RETURNING id"
                ),
                {
                    "o": str(datos_base["org_a"]),
                    "c": str(datos_base["cliente_a"]),
                    "cod": f"MAP-{uuid.uuid4().hex[:6]}",
                },
            ).scalar_one()
        )


@pytest.fixture
def activo(cliente: TestClient, cab: Any, proyecto: str, motor_admin: Engine) -> str:
    with motor_admin.begin() as conn:
        tipologia = conn.execute(text("SELECT id FROM asset_typology LIMIT 1")).scalar_one()
    return str(
        cliente.post(
            f"{RUTA}/projects/{proyecto}/assets",
            headers=cab("consultor_a"),
            json={"name": "Edificio Norte", "typology_id": str(tipologia)},
        ).json()["id"]
    )


def subir(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    coordenadas: tuple[float, float] | None = None,
    **campos: Any,
) -> Any:
    import random

    base = imagen(color=(random.randrange(256), 90, 40))
    datos = con_exif(base, gps=coordenadas) if coordenadas else base
    return cliente.post(
        f"{RUTA}/projects/{proyecto}/photos",
        headers=cab("consultor_a"),
        files={"file": ("f.jpg", io.BytesIO(datos), "image/jpeg")},
        data={k: str(v) for k, v in campos.items()},
    ).json()


def mapa(cliente: TestClient, cab: Any, proyecto: str, **consulta: Any) -> Any:
    cadena = "&".join(f"{k}={v}" for k, v in consulta.items())
    r = cliente.get(
        f"{RUTA}/projects/{proyecto}/photos/map" + (f"?{cadena}" if cadena else ""),
        headers=cab("consultor_a"),
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_una_foto_con_gps_sale_en_el_mapa(cliente: TestClient, cab: Any, proyecto: str) -> None:
    subir(cliente, cab, proyecto, RETIRO)
    resultado = mapa(cliente, cab, proyecto)
    assert len(resultado["puntos"]) == 1
    punto = resultado["puntos"][0]
    assert abs(punto["latitude"] - RETIRO[0]) < 0.001
    assert abs(punto["longitude"] - RETIRO[1]) < 0.001


def test_las_fotos_sin_gps_se_cuentan_en_vez_de_desaparecer(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """`[REQ]` §15.6 · Es lo que impide que el mapa mienta por omisión.

    En un sótano no hay señal y muchos móviles llegan con la localización
    apagada. Sin este número, cuatro chinchetas parecen decir «se hicieron
    cuatro fotos».
    """
    subir(cliente, cab, proyecto, RETIRO)
    for _ in range(3):
        subir(cliente, cab, proyecto)

    resultado = mapa(cliente, cab, proyecto)
    assert len(resultado["puntos"]) == 1
    assert resultado["sin_coordenadas"] == 3


def test_el_hemisferio_sur_y_occidental_conserva_el_signo(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """El fallo clásico del EXIF: las coordenadas llegan en grados absolutos y
    el hemisferio va aparte, en `GPSLatitudeRef`. Perder ese signo coloca el
    activo en el hemisferio contrario y nadie lo nota hasta ver el mapa."""
    subir(cliente, cab, proyecto, SUR)
    punto = mapa(cliente, cab, proyecto)["puntos"][0]
    assert punto["latitude"] < 0, "la latitud sur debe ser negativa"
    assert punto["longitude"] < 0, "la longitud oeste debe ser negativa"


def test_el_encuadre_cubre_todas_las_fotos(cliente: TestClient, cab: Any, proyecto: str) -> None:
    """Sin encuadre, el mapa abre centrado en el Atlántico y hay que buscar las
    chinchetas a mano."""
    subir(cliente, cab, proyecto, RETIRO)
    subir(cliente, cab, proyecto, CHAMARTIN)

    encuadre = mapa(cliente, cab, proyecto)["encuadre"]
    assert encuadre["sur"] <= RETIRO[0] <= encuadre["norte"]
    assert encuadre["sur"] <= CHAMARTIN[0] <= encuadre["norte"]
    assert encuadre["oeste"] <= RETIRO[1] <= encuadre["este"]


def test_sin_ninguna_foto_situada_no_hay_encuadre(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """`None` y no un encuadre de cero por cero: el cliente tiene que poder
    distinguir «no hay nada que enseñar» de «todo está en el mismo punto»."""
    subir(cliente, cab, proyecto)
    resultado = mapa(cliente, cab, proyecto)
    assert resultado["puntos"] == []
    assert resultado["encuadre"] is None
    assert resultado["sin_coordenadas"] == 1


def test_el_punto_trae_con_qué_identificar_la_foto(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """Una chincheta sin nombre no sirve de nada: hay que saber a qué activo
    pertenece antes de pincharla."""
    subir(cliente, cab, proyecto, RETIRO, asset_id=activo)
    punto = mapa(cliente, cab, proyecto)["puntos"][0]
    assert punto["asset_name"] == "Edificio Norte"
    assert punto["display_name"]
    assert punto["id"]


def test_se_puede_filtrar_por_activo(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    subir(cliente, cab, proyecto, RETIRO, asset_id=activo)
    subir(cliente, cab, proyecto, CHAMARTIN)

    todas = mapa(cliente, cab, proyecto)
    solo_una = mapa(cliente, cab, proyecto, asset_id=activo)

    assert len(todas["puntos"]) == 2
    assert len(solo_una["puntos"]) == 1
    assert solo_una["puntos"][0]["asset_name"] == "Edificio Norte"


def test_una_foto_en_la_papelera_no_aparece(cliente: TestClient, cab: Any, proyecto: str) -> None:
    """Lo borrado no está: un mapa que enseña fotos de la papelera haría dudar
    de todo lo demás."""
    foto = subir(cliente, cab, proyecto, RETIRO)
    cliente.delete(f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a"))
    resultado = mapa(cliente, cab, proyecto)
    assert resultado["puntos"] == []
    # Y tampoco engorda el recuento de las que no tienen coordenadas.
    assert resultado["sin_coordenadas"] == 0


def test_otra_organizacion_no_ve_el_mapa(cliente: TestClient, cab: Any, proyecto: str) -> None:
    subir(cliente, cab, proyecto, RETIRO)
    r = cliente.get(f"{RUTA}/projects/{proyecto}/photos/map", headers=cab("admin_b"))
    assert r.status_code == 404


def test_un_proyecto_inexistente_es_un_404(cliente: TestClient, cab: Any) -> None:
    r = cliente.get(f"{RUTA}/projects/{uuid.uuid4()}/photos/map", headers=cab("consultor_a"))
    assert r.status_code == 404
