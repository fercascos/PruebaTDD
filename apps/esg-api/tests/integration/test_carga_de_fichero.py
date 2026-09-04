"""Carga manual de consumos: proponer, simular y aplicar."""

from __future__ import annotations

import io
from decimal import Decimal

import pytest
from openpyxl import Workbook
from sqlalchemy import text

pytestmark = pytest.mark.db

CSV = (
    "CUPS;Fecha inicio;Fecha fin;Consumo;Unidad;Tipo\n"
    "ES0031000000001;01/01/2022;31/01/2022;10.240,50;kWh;Electricidad\n"
    "ES0031000000001;01/02/2022;28/02/2022;9.100;kWh;Electricidad\n"
).encode("cp1252")


def subir(cliente, cab, contenido: bytes, *, nombre="consumos.csv", **datos):
    return cliente.post(
        "/api/v1/cargas",
        files={"fichero": (nombre, contenido, "text/csv")},
        data=datos,
        headers=cab,
    )


def lecturas_de(motor_admin, cups: str) -> int:
    with motor_admin.begin() as conn:
        return conn.execute(
            text(
                "SELECT count(*) FROM lectura l JOIN punto_de_suministro p ON p.id = l.punto_id "
                "WHERE p.codigo = :c"
            ),
            {"c": cups},
        ).scalar_one()


def test_el_mapeo_se_propone_sin_escribir_nada(cliente, cab) -> None:
    respuesta = cliente.post(
        "/api/v1/cargas/proponer-mapeo",
        files={"fichero": ("consumos.csv", CSV, "text/csv")},
        headers=cab("gestor_a"),
    )
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["columnas"]["suministro"] == "CUPS"
    assert cuerpo["faltan"] == []


def test_simular_no_deja_ni_una_fila(cliente, cab, motor_admin) -> None:
    antes = lecturas_de(motor_admin, "ES0031000000001")
    respuesta = subir(cliente, cab("gestor_a"), CSV, aplicar="false")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["aplicada"] is False
    assert cuerpo["filas_aceptadas"] == 2
    assert lecturas_de(motor_admin, "ES0031000000001") == antes


def test_aplicar_carga_las_lecturas_y_deja_su_procedencia(cliente, cab, motor_admin) -> None:
    respuesta = subir(cliente, cab("gestor_a"), CSV, aplicar="true")
    cuerpo = respuesta.json()
    assert cuerpo["aplicada"] is True
    assert cuerpo["filas_aceptadas"] == 2
    with motor_admin.begin() as conn:
        fila = conn.execute(
            text(
                "SELECT l.inicio, l.fin, l.cantidad, l.cantidad_normalizada, l.origen::text, "
                "       l.fila_origen, c.nombre, c.hash_sha256 "
                "FROM lectura l JOIN carga c ON c.id = l.carga_id "
                "JOIN punto_de_suministro p ON p.id = l.punto_id "
                "WHERE p.codigo = 'ES0031000000001' AND l.inicio = '2022-01-01'"
            )
        ).one()
    assert str(fila.fin) == "2022-02-01"  # la fecha del fichero era inclusiva
    assert fila.cantidad == fila.cantidad_normalizada  # kWh ya es la unidad de agregación
    assert fila.origen == "FICHERO"
    assert fila.fila_origen == 2
    assert fila.nombre == "consumos.csv"
    assert fila.hash_sha256


def test_cargar_dos_veces_el_mismo_fichero_lo_para_la_base_de_datos(cliente, cab) -> None:
    """El fallo más caro del dominio: duplicar un consumo sin que nada avise."""
    respuesta = subir(cliente, cab("gestor_a"), CSV, aplicar="true")
    cuerpo = respuesta.json()
    assert cuerpo["ya_cargado_antes"] is True
    assert cuerpo["filas_aceptadas"] == 0
    assert cuerpo["filas_rechazadas"] == 2
    codigos = {i["codigo"] for i in cuerpo["incidencias"]}
    assert codigos == {"periodo_solapado"}
    assert "ya se cargó" in cuerpo["incidencias"][0]["mensaje"]


def test_la_simulacion_detecta_el_solape_porque_lo_intenta_de_verdad(cliente, cab) -> None:
    """Una simulación que solo mirase el fichero diría «2 filas correctas»."""
    cuerpo = subir(cliente, cab("gestor_a"), CSV, aplicar="false").json()
    assert cuerpo["filas_rechazadas"] == 2


def test_un_cups_que_no_existe_no_se_da_de_alta_solo(cliente, cab) -> None:
    fichero = (
        b"CUPS;Fecha inicio;Fecha fin;Consumo;Unidad;Tipo\n"
        b"ES-INVENTADO;01/03/2022;31/03/2022;500;kWh;Electricidad\n"
    )
    cuerpo = subir(cliente, cab("gestor_a"), fichero, aplicar="true").json()
    assert cuerpo["filas_aceptadas"] == 0
    incidencia = cuerpo["incidencias"][0]
    assert incidencia["codigo"] == "suministro_desconocido"
    assert "dé" in incidencia["mensaje"] or "alta" in incidencia["mensaje"]


def test_el_gas_en_metros_cubicos_sin_pcs_entra_pero_no_suma(cliente, cab, motor_admin) -> None:
    fichero = (
        b"CUPS;Fecha inicio;Fecha fin;Consumo;Unidad;Tipo\n"
        b"ES0021000000001;01/01/2022;31/01/2022;380;m3;Gas\n"
    )
    cuerpo = subir(cliente, cab("gestor_a"), fichero, aplicar="true").json()
    assert cuerpo["filas_aceptadas"] == 1
    assert cuerpo["filas_sin_normalizar"] == 1
    assert cuerpo["incidencias"][0]["codigo"] == "sin_normalizar"
    with motor_admin.begin() as conn:
        normalizada = conn.execute(
            text(
                "SELECT cantidad_normalizada FROM lectura l "
                "JOIN punto_de_suministro p ON p.id = l.punto_id "
                "WHERE p.codigo = 'ES0021000000001' AND l.inicio = '2022-01-01'"
            )
        ).scalar_one()
    assert normalizada is None


def test_el_gas_con_el_pcs_de_la_factura_si_se_convierte(cliente, cab, motor_admin) -> None:
    fichero = (
        b"CUPS;Fecha inicio;Fecha fin;Consumo;Unidad;Tipo;PCS\n"
        b"ES0021000000001;01/02/2022;28/02/2022;380;m3;Gas;11,32\n"
    )
    cuerpo = subir(cliente, cab("gestor_a"), fichero, aplicar="true").json()
    assert cuerpo["filas_sin_normalizar"] == 0
    with motor_admin.begin() as conn:
        fila = conn.execute(
            text(
                "SELECT cantidad_normalizada, unidad_normalizada, factor_de_conversion "
                "FROM lectura l JOIN punto_de_suministro p ON p.id = l.punto_id "
                "WHERE p.codigo = 'ES0021000000001' AND l.inicio = '2022-02-01'"
            )
        ).one()
    assert fila.cantidad_normalizada == Decimal("4301.6000")
    assert fila.unidad_normalizada == "kWh"
    assert fila.factor_de_conversion == Decimal("11.32")


def test_un_xlsx_se_carga_igual_que_un_csv(cliente, cab) -> None:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Consumos"
    hoja.append(["CUPS", "Fecha inicio", "Fecha fin", "Consumo", "Unidad", "Tipo"])
    hoja.append(["CT-AGUA-01", "2022-01-01", "2022-01-31", 1250.5, "m3", "Agua"])
    memoria = io.BytesIO()
    libro.save(memoria)
    respuesta = subir(
        cliente, cab("gestor_a"), memoria.getvalue(), nombre="consumos.xlsx", aplicar="true"
    )
    cuerpo = respuesta.json()
    assert cuerpo["filas_aceptadas"] == 1


def test_un_lector_no_puede_cargar_datos(cliente, cab) -> None:
    assert subir(cliente, cab("lector_a"), CSV, aplicar="true").status_code == 403


def test_las_incidencias_quedan_guardadas_y_se_pueden_volver_a_leer(cliente, cab) -> None:
    fichero = (
        b"CUPS;Fecha inicio;Fecha fin;Consumo;Unidad;Tipo\n"
        b"ES0031000000001;01/04/2022;30/04/2022;ochocientos;kWh;Electricidad\n"
    )
    carga = subir(cliente, cab("gestor_a"), fichero, aplicar="false").json()
    guardadas = cliente.get(
        f"/api/v1/cargas/{carga['carga_id']}/incidencias", headers=cab("gestor_a")
    ).json()
    assert [i["codigo"] for i in guardadas] == ["cantidad_invalido"]
    assert guardadas[0]["fila"] == 2
