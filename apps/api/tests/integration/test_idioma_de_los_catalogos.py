"""Los catálogos salen en el idioma de la petición. `[REQ]` 0030.

La 0029 metió el inglés en la base y la 0030 lo sirve, con una función de SQL
—`nombre(name_es, name_en)`— que lee una variable de sesión. Esto comprueba las
cuatro cosas que pueden salir mal con ese diseño, y las cuatro son invisibles si
nadie mira:

1. Que la cabecera llegue hasta la consulta. Son cuatro saltos —cabecera,
   dependencia, contexto, `set_config`— y basta que falte uno para que todo
   siga funcionando en castellano sin un solo error.
2. Que el respaldo funcione. Un catálogo que una organización añade por su
   cuenta no tiene inglés, y la pantalla tiene que seguir enseñando algo.
3. Que el idioma **no se quede pegado a la conexión**. `set_config(..., TRUE)`
   lo ata a la transacción; si alguien lo pusiera a `FALSE`, una petición en
   inglés contaminaría la siguiente del pool, y el síntoma sería una pantalla
   en castellano que de pronto sale en inglés para otro usuario.
4. Que el **entregable** mande sobre la pantalla. Quien trabaja con la interfaz
   en castellano y pide el CAPEX en inglés quiere el fichero en inglés.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.db

EN = {"Accept-Language": "en"}
ES = {"Accept-Language": "es"}
RUTA = "/api/v1/catalogs"


def _nombres(respuesta) -> dict[str, str]:
    assert respuesta.status_code == 200, respuesta.text
    return {f["code"]: f["name_es"] for f in respuesta.json()}


def test_las_zonas_salen_en_ingles_con_accept_language(cliente, cab) -> None:
    """Y el inglés es el del cliente, no el obvio.

    «Cuartos técnicos» sale *Technical Rooms* porque así lo llama él en su
    propia plantilla. La prueba fija el valor concreto a propósito: si alguien
    «mejora» la traducción, el informe y la pantalla dejan de llamar igual a lo
    mismo, que es justo lo que no puede pasar.
    """
    cabeceras = {**cab("consultor_a"), **EN}
    zonas = _nombres(cliente.get(f"{RUTA}/zones", headers=cabeceras))
    assert zonas["CUARTOS_TECNICOS"] == "Technical Rooms"
    assert zonas["ZONAS_EXTERIORES"] == "External areas"


def test_la_misma_ruta_en_castellano_sigue_en_castellano(cliente, cab) -> None:
    cabeceras = {**cab("consultor_a"), **ES}
    zonas = _nombres(cliente.get(f"{RUTA}/zones", headers=cabeceras))
    assert zonas["CUARTOS_TECNICOS"] == "Cuartos técnicos"


def test_sin_cabecera_sale_en_castellano(cliente, cab) -> None:
    """Castellano por omisión: es el idioma del producto, y olvidarse se ve."""
    zonas = _nombres(cliente.get(f"{RUTA}/zones", headers=cab("consultor_a")))
    assert zonas["CUARTOS_TECNICOS"] == "Cuartos técnicos"


def test_una_cabecera_que_no_entendemos_es_castellano(cliente, cab) -> None:
    """`fr-FR`, basura o vacío: castellano, sin error.

    Un `Accept-Language` raro no es un fallo del usuario ni algo que haya que
    rechazar con un 400: es un navegador configurado en otro idioma. Se sirve
    el idioma del producto.
    """
    for valor in ("fr-FR", "", ";;;", "english"):
        zonas = _nombres(
            cliente.get(f"{RUTA}/zones", headers={**cab("consultor_a"), "Accept-Language": valor})
        )
        assert zonas["CUARTOS_TECNICOS"] == "Cuartos técnicos", valor


def test_el_idioma_no_se_queda_pegado_a_la_conexion(cliente, cab) -> None:
    """Inglés, castellano, inglés, castellano, sobre el mismo pool.

    Es la prueba del `TRUE` de `set_config`. Con `SET` a secas pasaría la
    primera y fallaría la segunda, y en producción el síntoma sería una
    pantalla que sale en el idioma del usuario anterior.
    """
    for cabecera, esperado in ((EN, "Technical Rooms"), (ES, "Cuartos técnicos")) * 2:
        zonas = _nombres(cliente.get(f"{RUTA}/zones", headers={**cab("consultor_a"), **cabecera}))
        assert zonas["CUARTOS_TECNICOS"] == esperado


@pytest.mark.parametrize(
    ("ruta", "code", "en"),
    [
        # Las seis donde la traducción natural es la equivocada, por la ruta
        # que de verdad las sirve.
        ("asset-typologies", "COMERCIAL", "Retail"),
        ("asset-typologies", "SANITARIO", "Healthcare"),
        ("capex-concepts", "VIDA_UTIL", "End of useful life"),
        ("capex-concepts", "NORMATIVA", "Regulatory"),
        ("technical-systems", "FONT", "Plumbing and drainage"),
        ("time-horizons", "MEDIO", "Mid term"),
    ],
)
def test_cada_catalogo_sirve_el_ingles_del_cliente(cliente, cab, ruta, code, en) -> None:
    nombres = _nombres(cliente.get(f"{RUTA}/{ruta}", headers={**cab("consultor_a"), **EN}))
    assert nombres[code] == en


def test_un_catalogo_propio_sin_traducir_sale_en_castellano(cliente, cab, motor_admin) -> None:
    """El respaldo `COALESCE(name_en, name_es)`, con una fila de verdad.

    `name_en` admite nulo porque una organización puede añadir sus propias
    zonas y nadie las traduce al darlas de alta. Lo que no puede es desaparecer
    de la lista ni salir como un hueco: sale en castellano, que **se lee** como
    lo que es —esto no está traducido—.
    """
    with motor_admin.begin() as c:
        org = c.execute(text("SELECT id FROM organization LIMIT 1")).scalar_one()
        c.execute(
            text(
                "INSERT INTO zone (organization_id, code, name_es, is_system, sort_order) "
                "VALUES (:o, 'MUELLE_DE_CARGA', 'Muelle de carga', FALSE, 999) "
                "ON CONFLICT (organization_id, code) DO NOTHING"
            ),
            {"o": str(org)},
        )
    try:
        zonas = _nombres(cliente.get(f"{RUTA}/zones", headers={**cab("consultor_a"), **EN}))
        # Sale, y sale en castellano. Las dos cosas importan.
        assert zonas.get("MUELLE_DE_CARGA") == "Muelle de carga"
        # Y las traducidas siguen traducidas: una fila sin inglés no arrastra
        # a las demás.
        assert zonas["CUARTOS_TECNICOS"] == "Technical Rooms"
    finally:
        with motor_admin.begin() as c:
            c.execute(text("DELETE FROM zone WHERE code = 'MUELLE_DE_CARGA'"))


def test_la_busqueda_del_arbol_capex_encuentra_en_los_dos_idiomas(cliente, cab) -> None:
    """Buscar «cubierta» en una sesión inglesa encuentra «Roof».

    Es a propósito y no un descuido: un técnico español que atiende un encargo
    en inglés escribe en castellano. Buscar solo por el idioma activo le
    quitaría resultados sin decirle por qué.
    """
    cabeceras = {**cab("consultor_a"), **EN}
    en_castellano = cliente.get(f"{RUTA}/capex-codes?q=Cubierta", headers=cabeceras)
    en_ingles = cliente.get(f"{RUTA}/capex-codes?q=Roof", headers=cabeceras)
    assert en_castellano.status_code == 200, en_castellano.text
    assert en_ingles.status_code == 200, en_ingles.text
    codigos_es = {f["code"] for f in en_castellano.json()}
    codigos_en = {f["code"] for f in en_ingles.json()}
    # El capítulo H02 lo encuentran las dos búsquedas.
    assert "HC.H02" in codigos_es
    assert "HC.H02" in codigos_en
    # Y lo que devuelve va en inglés, que es el idioma de la sesión.
    h02 = next(f for f in en_ingles.json() if f["code"] == "HC.H02")
    assert h02["name_es"] == "Roof"


# ─────────────────────────────────────────────────────────────────────────────
#  Las frases que escribe el servidor
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def proyecto(cliente, cab, datos_base) -> str:
    """Un proyecto con sus fases, que es lo que tiene un avance que describir."""
    r = cliente.post(
        "/api/v1/projects",
        headers=cab("consultor_a"),
        json={
            "client_id": str(datos_base["cliente_a"]),
            "internal_code": f"2026-{uuid.uuid4().hex[:6]}",
            "name": "TDD de prueba",
            "applicable_phases": [
                {"code": "SOLICITUD_DOCUMENTACION"},
                {"code": "VISITA"},
                {"code": "RED_FLAG_CAPEX"},
                {"code": "FULL_REPORT"},
            ],
        },
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def test_el_avance_de_las_fases_se_traduce(cliente, cab, proyecto) -> None:
    """«11 de 17 resueltas» no la puede traducir el navegador.

    `[REQ]` Es la tercera capa de texto de la aplicación: ni rótulo del código
    ni dato del catálogo, sino una frase que **compone el servidor** a partir
    del estado del proyecto. Llega ya escrita, así que el frontend no sabe cómo
    se formó y no puede hacer nada con ella.

    Esta prueba existe por cómo falló: el idioma se fijaba en
    `core/deps.obtener_sesion`, una dependencia **generadora síncrona**, que
    FastAPI ejecuta en un hilo del pool con su propio contexto. El `ContextVar`
    que se fijaba ahí no llegaba al endpoint, de modo que la API devolvía
    castellano con `Accept-Language: en` **y no daba ningún error**. Se arregló
    moviéndolo al middleware ASGI, que sí corre en el contexto del que hereda
    el endpoint.
    """
    ruta = f"/api/v1/projects/{proyecto}/phases"
    es = cliente.get(ruta, headers={**cab("consultor_a"), **ES})
    en = cliente.get(ruta, headers={**cab("consultor_a"), **EN})
    assert es.status_code == 200, es.text
    assert en.status_code == 200, en.text

    detalles_es = [f["detalle"] for f in es.json() if f.get("detalle")]
    detalles_en = [f["detalle"] for f in en.json() if f.get("detalle")]
    assert detalles_es, "el proyecto de prueba no tiene ninguna fase con avance"
    # Al menos una cambia, y ninguna se queda a medias en castellano.
    assert detalles_es != detalles_en
    assert not [d for d in detalles_en if "de" in d.split() or "sin" in d.split()]


def test_el_idioma_no_se_hereda_de_la_peticion_anterior(cliente, cab, proyecto) -> None:
    """Inglés y luego sin cabecera: la segunda es castellana.

    Es la prueba del `reset` del `ContextVar`. Sin él el valor se queda en el
    contexto de la tarea, y una petición sin cabecera heredaría el idioma de la
    anterior: la misma clase de fuga que evita el `SET LOCAL` del contexto RLS,
    y con el mismo síntoma difícil de creer —una pantalla que sale en inglés
    para quien no lo pidió—.
    """
    ruta = f"/api/v1/projects/{proyecto}/phases"
    en_ingles = [
        f["detalle"] for f in cliente.get(ruta, headers={**cab("consultor_a"), **EN}).json()
    ]
    sin_cabecera = [f["detalle"] for f in cliente.get(ruta, headers=cab("consultor_a")).json()]
    assert en_ingles != sin_cabecera
