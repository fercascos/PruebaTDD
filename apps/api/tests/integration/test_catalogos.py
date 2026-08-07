"""La semilla de catálogos, comprobada contra la base de datos.

Estos catálogos son la estructura sobre la que se apoya todo el CAPEX. Sembrar
mal la matriz de zonas obliga a migrar datos reales meses después, así que se
comprueba pieza a pieza y no «que carga sin error».
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.db

RAIZ = Path(__file__).resolve().parents[4]
CATALOGOS = RAIZ / "data" / "catalogos"


def _csv(nombre: str) -> list[dict[str, str]]:
    with (CATALOGOS / nombre).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# ─────────────────────────────────────────────────────────────────────────────
#  El documento de diseño y los datos no pueden divergir
# ─────────────────────────────────────────────────────────────────────────────


def test_los_csv_no_divergen_del_documento_de_diseno() -> None:
    """Los CSV se generan desde `docs/05-catalogos-y-taxonomias.md`.

    Si alguien corrige la matriz de zonas en el documento y no regenera los CSV
    —o al revés—, esta prueba lo detecta. Es lo que impide que el documento que
    revisa el cliente y los datos que se cargan cuenten cosas distintas.
    """
    r = subprocess.run(  # noqa: S603
        [sys.executable, str(RAIZ / "tools" / "generar_catalogos.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, (
        "Los CSV están desfasados respecto de docs/05-catalogos-y-taxonomias.md.\n"
        "Ejecute: python3 tools/generar_catalogos.py\n" + r.stderr
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Recuentos exactos
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("tabla", "esperado", "que_es"),
    [
        ("asset_typology", 6, "tipologías [REQ] P-01"),
        ("zone", 20, "zonas normalizadas"),
        ("capex_code", 161, "nodos del árbol de códigos"),
        ("risk_level", 4, "grados de riesgo"),
        ("capex_concept", 10, "conceptos"),
        ("time_horizon", 5, "horizontes"),
    ],
)
def test_recuentos_de_la_semilla(motor_admin, tabla: str, esperado: int, que_es: str) -> None:
    with motor_admin.connect() as c:
        n = c.execute(
            text(f"SELECT count(*) FROM {tabla} WHERE organization_id IS NULL")  # noqa: S608
        ).scalar_one()
    assert n == esperado, f"Se esperaban {esperado} {que_es}, hay {n}"


def test_la_matriz_tiene_86_relaciones(motor_admin) -> None:
    """`zone_typology` es tabla puente y no lleva organization_id: su recuento
    va aparte."""
    with motor_admin.connect() as c:
        n = c.execute(text("SELECT count(*) FROM zone_typology")).scalar_one()
    assert n == 86


def test_el_arbol_tiene_la_forma_documentada(motor_admin) -> None:
    """6 categorías + 24 capítulos + 131 elementos = 161 nodos.

    Los recuentos crecieron al cerrar P-03 con la plantilla CAPEX vigente:
    Medioambiental pasó de 1 elemento a 13, ESG de 1 a 11, y Soft Costs ganó
    los capítulos `S01`, `S02` y `S03` con su `General` cada uno. Después
    entraron Operativos e Imprevistos, en cuanto la plantilla tuvo dónde
    escribirlos."""
    with motor_admin.connect() as c:
        por_nivel = dict(
            c.execute(
                text(
                    "SELECT level, count(*) FROM capex_code WHERE organization_id IS NULL "
                    "GROUP BY level ORDER BY level"
                )
            ).all()
        )
    assert por_nivel == {1: 6, 2: 24, 3: 131}


# ─────────────────────────────────────────────────────────────────────────────
#  La matriz de zonas, que es la que condiciona la captura en campo
# ─────────────────────────────────────────────────────────────────────────────


def test_las_86_combinaciones_zona_tipologia_son_las_documentadas(motor_admin) -> None:
    esperadas = {(f["zone_code"], f["typology_code"]) for f in _csv("zonas_por_tipologia.csv")}
    with motor_admin.connect() as c:
        reales = {
            (z, t)
            for z, t in c.execute(
                text(
                    "SELECT z.code, t.code FROM zone_typology zt "
                    "JOIN zone z ON z.id = zt.zone_id "
                    "JOIN asset_typology t ON t.id = zt.typology_id"
                )
            ).all()
        }
    assert reales == esperadas
    assert len(reales) == 86


@pytest.mark.parametrize(
    ("tipologia", "n_zonas"),
    [
        ("INDUSTRIAL", 11),
        ("OFICINAS", 10),
        ("HOTEL", 16),
        ("COMERCIAL", 13),
        ("SANITARIO", 16),
        ("OTROS", 20),
    ],
)
def test_cada_tipologia_ofrece_las_zonas_de_la_especificacion(
    motor_admin, tipologia: str, n_zonas: int
) -> None:
    """Los recuentos por tipología de §3.3.2, uno a uno."""
    with motor_admin.connect() as c:
        n = c.execute(
            text(
                "SELECT count(*) FROM zone_typology zt "
                "JOIN asset_typology t ON t.id = zt.typology_id WHERE t.code = :c"
            ),
            {"c": tipologia},
        ).scalar_one()
    assert n == n_zonas


def test_almacen_y_vestuarios_solo_en_industrial_y_otros(motor_admin) -> None:
    """P-01 · Es la razón por la que los activos logísticos se clasifican como
    Industrial: es la única tipología con esas dos zonas."""
    with motor_admin.connect() as c:
        for zona in ("ALMACEN", "VESTUARIOS"):
            tipologias = {
                t
                for (t,) in c.execute(
                    text(
                        "SELECT t.code FROM zone_typology zt "
                        "JOIN zone z ON z.id = zt.zone_id "
                        "JOIN asset_typology t ON t.id = zt.typology_id WHERE z.code = :z"
                    ),
                    {"z": zona},
                ).all()
            }
            assert tipologias == {"INDUSTRIAL", "OTROS"}, f"{zona} en {tipologias}"


def test_nueve_zonas_estan_en_las_seis_tipologias(motor_admin) -> None:
    with motor_admin.connect() as c:
        n = c.execute(
            text(
                "SELECT count(*) FROM (SELECT zone_id FROM zone_typology "
                "GROUP BY zone_id HAVING count(*) = 6) t"
            )
        ).scalar_one()
    assert n == 9


# ─────────────────────────────────────────────────────────────────────────────
#  Integridad del árbol
# ─────────────────────────────────────────────────────────────────────────────


def test_el_arbol_no_tiene_huerfanos_ni_niveles_incoherentes(motor_admin) -> None:
    with motor_admin.connect() as c:
        huerfanos = c.execute(
            text("SELECT count(*) FROM capex_code c WHERE c.level > 1 AND c.parent_id IS NULL")
        ).scalar_one()
        assert huerfanos == 0

        saltos = c.execute(
            text(
                "SELECT count(*) FROM capex_code c JOIN capex_code p ON p.id = c.parent_id "
                "WHERE c.level <> p.level + 1"
            )
        ).scalar_one()
        assert saltos == 0, "Un hijo debe estar exactamente un nivel por debajo de su padre"


def test_el_path_ltree_es_coherente_con_la_jerarquia(motor_admin) -> None:
    """El `path` es lo que permite consultar «todo lo que cuelga de HC.H09»."""
    with motor_admin.connect() as c:
        descolgados = c.execute(
            text(
                "SELECT count(*) FROM capex_code c JOIN capex_code p ON p.id = c.parent_id "
                "WHERE NOT (c.path OPERATOR(public.<@) p.path)"
            )
        ).scalar_one()
        assert descolgados == 0

        n = c.execute(
            text("SELECT count(*) FROM capex_code WHERE path OPERATOR(public.<@) 'HC.H09'")
        ).scalar_one()
        assert n == 16, "H09 Electricidad: el capítulo y sus 15 elementos"


def test_las_categorias_que_cerraron_p03_tienen_su_desglose(motor_admin) -> None:
    """P-03 · MA, ESG y SC se sembraron con un «General» provisional hasta que
    llegó la plantilla CAPEX vigente. Ahora traen su desglose."""
    esperado = {"MA": 13, "ESG": 11, "SC": 4, "OP": 2, "IMP": 1}
    with motor_admin.connect() as c:
        for cat, cuantos in esperado.items():
            n = c.execute(
                text(
                    "SELECT count(*) FROM capex_code "
                    "WHERE path OPERATOR(public.<@) CAST(:c AS ltree) AND level = 3"
                ),
                {"c": cat},
            ).scalar_one()
            assert n == cuantos, f"{cat} debe tener {cuantos} elementos, tiene {n}"


def test_el_general_de_p03_conserva_su_codigo(motor_admin) -> None:
    """`[REQ]` §5.3 prometió cerrar P-03 **sin migración de datos**. Si
    `MA.General.01` dejara de ser «General», toda línea de CAPEX ya codificada
    pasaría a decir otra cosa sin que nadie la tocara."""
    with motor_admin.connect() as c:
        filas = dict(
            c.execute(
                text(
                    "SELECT code, name_es FROM capex_code "
                    "WHERE code IN ('MA.General.01', 'ESG.General.01', 'SC.General.01')"
                )
            ).all()
        )
    assert filas == {
        "MA.General.01": "General",
        "ESG.General.01": "General",
        "SC.General.01": "General",
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Riesgos y horizontes
# ─────────────────────────────────────────────────────────────────────────────


def test_las_definiciones_de_riesgo_estan_integras(motor_admin) -> None:
    """[REQ] Se guardan enteras: se muestran al clasificar y van al informe."""
    with motor_admin.connect() as c:
        filas = c.execute(
            text("SELECT code, score, definition_es FROM risk_level ORDER BY score")
        ).all()
    assert [f.code for f in filas] == ["01", "02", "03", "04"]
    assert [f.score for f in filas] == [1, 2, 3, 4]
    for f in filas:
        assert len(f.definition_es) > 100, f"La definición del grado {f.code} parece truncada"
    assert "irrefutables" in filas[3].definition_es.lower()


def test_el_horizonte_corto_es_de_1_a_2_anos(motor_admin) -> None:
    """P-04 · decidido por el cliente."""
    with motor_admin.connect() as c:
        f = c.execute(
            text("SELECT year_from, year_to FROM time_horizon WHERE code = 'CORTO'")
        ).one()
    assert (f.year_from, f.year_to) == (1, 2)


def test_mejoras_y_otro_no_son_plazos_de_ejecucion(motor_admin) -> None:
    """P-05 · «Mejoras» no es un plazo, es una naturaleza: la decide el cliente."""
    with motor_admin.connect() as c:
        filas = dict(c.execute(text("SELECT code, is_execution_term FROM time_horizon")).all())
    assert filas == {"CORTO": True, "MEDIO": True, "LARGO": True, "MEJORAS": False, "OTRO": False}


def test_los_catalogos_del_sistema_no_son_editables_por_una_organizacion(como) -> None:
    """Las filas del sistema (organization_id IS NULL) no las toca nadie.

    La política las deja **leer** a todos —son la estructura compartida— pero su
    WITH CHECK impide escribirlas, y PostgreSQL lo rechaza con error en vez de
    ignorar la fila en silencio. Mejor así: el intento no pasa desapercibido.
    """
    from sqlalchemy.exc import DBAPIError, ProgrammingError

    with pytest.raises((ProgrammingError, DBAPIError), match="row-level security"):
        with como("admin_a") as s:
            s.execute(text("UPDATE zone SET name_es = 'Manipulada' WHERE code = 'CUBIERTA'"))


# ─────────────────────────────────────────────────────────────────────────────
#  Filtros del árbol de códigos
#
#  Estos filtros no estaban probados y fallaban con un 500 en cuanto se usaban:
#  PostgreSQL no puede inferir el tipo de un parámetro que solo aparece en
#  `IS NULL` y dentro de una concatenación. Se descubrió al recorrer la
#  aplicación de punta a punta, no leyendo el código.
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.db
def test_los_codigos_se_filtran_por_nivel(cliente, cab) -> None:
    r = cliente.get("/api/v1/catalogs/capex-codes?level=3", headers=cab("consultor_a"))
    assert r.status_code == 200, r.text
    assert r.json(), "el nivel 3 son los elementos: no puede estar vacío"
    assert {c["level"] for c in r.json()} == {3}


@pytest.mark.db
def test_los_codigos_se_filtran_por_padre(cliente, cab) -> None:
    capitulos = cliente.get(
        "/api/v1/catalogs/capex-codes?level=2", headers=cab("consultor_a")
    ).json()
    padre = capitulos[0]["id"]
    hijos = cliente.get(
        f"/api/v1/catalogs/capex-codes?parent_id={padre}", headers=cab("consultor_a")
    )
    assert hijos.status_code == 200
    assert all(c["parent_id"] == padre for c in hijos.json())


@pytest.mark.db
def test_los_codigos_se_buscan_por_texto(cliente, cab) -> None:
    r = cliente.get("/api/v1/catalogs/capex-codes?q=cubierta", headers=cab("consultor_a"))
    assert r.status_code == 200
    assert all(
        "cubierta" in c["name_es"].lower() or "cubierta" in c["code"].lower() for c in r.json()
    )


@pytest.mark.db
def test_los_tres_filtros_se_combinan(cliente, cab) -> None:
    r = cliente.get("/api/v1/catalogs/capex-codes?level=3&q=a", headers=cab("consultor_a"))
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
#  Idempotencia de la semilla
#
#  `UNIQUE (organization_id, code)` NO protegía las filas del sistema: en
#  PostgreSQL dos NULL se consideran distintos en un índice único, y las filas
#  del sistema son justo las que llevan `organization_id` NULL. `ON CONFLICT`
#  no disparaba nunca para ellas y volver a sembrar duplicaba el catálogo
#  entero. Se descubrió al reponer los datos de una demostración, no leyendo el
#  código: la suite siempre partía de un esquema recién creado.
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.db
def test_sembrar_dos_veces_no_duplica_el_catalogo(motor_admin) -> None:
    from tdd.catalogs.seeding import sembrar_catalogos

    with motor_admin.begin() as conn:
        antes = {
            tabla: conn.execute(text(f"SELECT count(*) FROM {tabla}")).scalar_one()  # noqa: S608
            for tabla in ("asset_typology", "zone", "capex_code", "risk_level", "time_horizon")
        }

    with motor_admin.begin() as conn:
        sembrar_catalogos(conn)

    with motor_admin.begin() as conn:
        despues = {
            tabla: conn.execute(text(f"SELECT count(*) FROM {tabla}")).scalar_one()  # noqa: S608
            for tabla in antes
        }
    assert despues == antes


@pytest.mark.db
def test_no_puede_haber_dos_filas_del_sistema_con_el_mismo_codigo(motor_admin) -> None:
    """La restricción que faltaba, comprobada intentando saltársela."""
    with motor_admin.begin() as conn, pytest.raises(Exception, match="duplicate key|unique"):
        conn.execute(
            text(
                "INSERT INTO time_horizon (organization_id, code, name_es, sort_order) "
                "SELECT NULL, code, name_es, sort_order FROM time_horizon LIMIT 1"
            )
        )


@pytest.mark.db
def test_una_organizacion_si_puede_tener_su_propio_codigo_igual(motor_admin, datos_base) -> None:
    """Lo que la restricción NO debe impedir: que una organización defina su
    propia versión de un código del sistema. Son filas distintas."""
    with motor_admin.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO capex_concept (organization_id, code, name_es, is_system) "
                "VALUES (:o, 'MANTENIMIENTO', 'Mantenimiento (versión propia)', FALSE)"
            ),
            {"o": str(datos_base["org_a"])},
        )
