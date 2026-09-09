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
        ("capex_code", 175, "nodos del árbol de códigos"),
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
    """6 tipos de coste + 28 categorías + 141 objetos = 175 nodos.

    Es la estructura que mantiene el cliente en su hoja y que entró con la
    revisión del prototipo. Lo que la hizo crecer respecto de los 161 anteriores
    fue **el «Otros»**: cada categoría acaba con un objeto «Otros» y cada tipo
    con una categoría «Otros», que antes se leían como una fila de relleno y se
    descartaban. Ver `docs/05` §5.3 y `tools/importar_arbol_capex.py`."""
    with motor_admin.connect() as c:
        por_nivel = dict(
            c.execute(
                text(
                    "SELECT level, count(*) FROM capex_code WHERE organization_id IS NULL "
                    "GROUP BY level ORDER BY level"
                )
            ).all()
        )
    assert por_nivel == {1: 6, 2: 28, 3: 141}


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
        assert n == 17, "H09 Electricidad: el capítulo y sus 16 objetos"


def test_cada_tipo_de_coste_trae_los_objetos_de_la_hoja_del_cliente(motor_admin) -> None:
    """La estructura que mantiene el cliente, comprobada tipo a tipo.

    Los soft costs, operativos e imprevistos **no traen objetos**: sus
    categorías son la hoja del árbol y ahí se codifica el hallazgo. No es un
    olvido de la hoja, es cómo trabajan: el concepto —«Honorarios ECLU»— se
    escribe en la descripción."""
    esperado = {"MA": 14, "ESG": 12, "SC": 0, "OP": 0, "IMP": 0}
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


def test_los_codigos_viejos_se_renombraron_sin_dejar_nada_huerfano(motor_admin) -> None:
    """`[REQ]` El cliente pidió **sus** códigos, y eso obligó a renombrar.

    Esto sustituye a una prueba anterior que fijaba lo contrario —que
    `MA.General.01` conservaría su código para siempre—, y la sustituye porque
    la decisión cambió, no porque estorbara. Lo que hay que seguir garantizando
    es lo de siempre: **que nada se quede sin código**. Renombrar la fila en vez
    de crear otra es lo que lo consigue, porque conserva su `id`.
    """
    with motor_admin.connect() as c:
        viejos = c.execute(
            text(
                "SELECT count(*) FROM capex_code "
                "WHERE code IN ('MA.General', 'ESG.General', 'OP.C01', 'OP.C02', 'IMP.General')"
            )
        ).scalar_one()
        assert viejos == 0, "los códigos viejos tenían que haberse renombrado"

        nuevos = dict(
            c.execute(
                text(
                    "SELECT code, name_es FROM capex_code "
                    "WHERE code IN ('MA.MA1', 'ESG.ES1', 'OP.OP1', 'OP.OP2', 'IMP.IM1')"
                )
            ).all()
        )
        assert nuevos == {
            "MA.MA1": "Medioambiente",
            "ESG.ES1": "ESG",
            "OP.OP1": "Consumos obra",
            "OP.OP2": "Limpieza",
            "IMP.IM1": "General",
        }

        # Y el objeto que ya estaba codificado sigue diciendo lo mismo: cambió
        # su código, no su significado.
        assert (
            c.execute(text("SELECT name_es FROM capex_code WHERE code = 'MA.MA1.07'")).scalar_one()
            == "Ruido"
        )


def test_cada_categoria_tiene_su_salida_otros(motor_admin) -> None:
    """`[REQ]` Decisión del cliente: el `-` de su hoja es «Otros» y se modela.

    Antes se descartaba como relleno. Es la salida que necesita un consultor en
    campo cuando lo que ve no está en la lista, y sin ella acaba metiéndolo en
    «General», que significa otra cosa.
    """
    with motor_admin.connect() as c:
        sin_salida = c.execute(
            text(
                "SELECT count(*) FROM capex_code cat "
                "WHERE cat.level = 2 AND cat.organization_id IS NULL "
                "  AND EXISTS (SELECT 1 FROM capex_code o WHERE o.parent_id = cat.id) "
                "  AND NOT EXISTS (SELECT 1 FROM capex_code o "
                "                   WHERE o.parent_id = cat.id AND o.name_es = 'Otros')"
            )
        ).scalar_one()
    assert sin_salida == 0, "toda categoría con objetos tiene que ofrecer «Otros»"


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


@pytest.mark.db
def test_las_categorias_de_solicitud_se_sirven_por_api(cliente, cab) -> None:
    """`[REQ]` §3.1.5 · Existían en la base desde el principio, pero no se
    servían: dar de alta una línea de la checklist exigía conocer su
    `category_id` de memoria, y la pantalla no podía ofrecer un desplegable."""
    r = cliente.get("/api/v1/catalogs/doc-request-categories", headers=cab("consultor_a"))
    assert r.status_code == 200
    categorias = r.json()
    codigos = {c["code"] for c in categorias}
    assert "LICENCIAS_URBANISTICAS" in codigos
    assert len(categorias) == 6
    # `[REQ]` La memoria técnica va la PRIMERA, y no por orden alfabético: es el
    # documento del que salen los datos del edificio y el esqueleto del CAPEX,
    # así que pedirla tarde retrasa todo lo demás. El orden de la checklist es
    # lo que le dice al consultor por dónde empezar.
    assert categorias[0]["code"] == "MEMORIA_TECNICA"
