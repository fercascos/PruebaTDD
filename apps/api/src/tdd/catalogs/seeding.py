"""Carga la semilla de catálogos desde `data/catalogos/*.csv`.

`[REC]` La fuente de verdad es el CSV, y el CSV se genera desde
`docs/05-catalogos-y-taxonomias.md` con `tools/generar_catalogos.py`. Así el
documento que revisa el cliente y los datos que se cargan **no pueden divergir**:
hay una prueba que lo comprueba.

La carga es **idempotente**: ejecutarla dos veces no duplica nada.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection

RAIZ = Path(__file__).resolve().parents[5]
CATALOGOS = RAIZ / "data" / "catalogos"


@dataclass(frozen=True, slots=True)
class ResumenSemilla:
    typologies: int
    zones: int
    zone_typology: int
    capex_codes: int
    risk_levels: int
    concepts: int
    horizons: int
    technical_systems: int
    #: `[REQ]` §5.9 · secciones de memoria → capítulos CAPEX.
    memoria_sections: int = 0
    #: `[REQ]` §5.10 · los 73 nodos del árbol documental del cliente.
    doc_tree_nodes: int = 0
    #: `[REQ]` 0029 · nombres en inglés aplicados a los catálogos.
    traducciones: int = 0

    def __str__(self) -> str:
        return (
            f"{self.typologies} tipologías · {self.zones} zonas · "
            f"{self.zone_typology} relaciones zona×tipología · "
            f"{self.capex_codes} códigos CAPEX · {self.risk_levels} riesgos · "
            f"{self.concepts} conceptos · {self.horizons} horizontes · "
            f"{self.technical_systems} sistemas técnicos · "
            f"{self.memoria_sections} secciones de memoria · "
            f"{self.doc_tree_nodes} nodos del árbol documental · "
            f"{self.traducciones} traducciones al inglés"
        )


def _leer(nombre: str, base: Path | None = None) -> list[dict[str, str]]:
    ruta = (base or CATALOGOS) / nombre
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encuentra {ruta}. Ejecute `python3 tools/generar_catalogos.py`."
        )
    with ruta.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def sembrar_catalogos(conn: Connection, *, base: Path | None = None) -> ResumenSemilla:
    """Siembra los catálogos del sistema (`organization_id IS NULL`)."""

    def _simple(tabla: str, fichero: str, extra: str = "", extra_vals: str = "") -> int:
        filas = _leer(fichero, base)
        for i, fila in enumerate(filas):
            conn.execute(
                text(
                    f"INSERT INTO {tabla} (organization_id, code, name_es, is_system, sort_order"
                    f"{extra}) VALUES (NULL, :code, :name_es, TRUE, :sort_order{extra_vals}) "
                    "ON CONFLICT (organization_id, code) DO NOTHING"
                ),
                {**fila, "sort_order": i},
            )
        return len(filas)

    n_tip = _simple("asset_typology", "tipologias.csv")
    n_zon = _simple("zone", "zonas.csv")

    # Matriz zona × tipología: las 86 relaciones de §5.2
    matriz = _leer("zonas_por_tipologia.csv", base)
    for rel in matriz:
        conn.execute(
            text(
                "INSERT INTO zone_typology (zone_id, typology_id) "
                "SELECT z.id, t.id FROM zone z, asset_typology t "
                "WHERE z.code = :zone_code AND t.code = :typology_code "
                "  AND z.organization_id IS NULL AND t.organization_id IS NULL "
                "ON CONFLICT DO NOTHING"
            ),
            rel,
        )

    # Árbol de códigos. Se insertan **ordenados por nivel** y resolviendo el
    # padre en la misma sentencia: el CHECK `capex_code_parent_coherente` exige
    # que todo nodo de nivel > 1 tenga padre desde el primer momento, así que no
    # sirve insertar suelto y enlazar después.
    codigos = sorted(_leer("codigos_capex.csv", base), key=lambda f: int(f["level"]))
    for fila in codigos:
        conn.execute(
            text(
                "INSERT INTO capex_code (organization_id, code, name_es, level, parent_id, "
                "is_system) SELECT NULL, :code, :name_es, :level, "
                "  (SELECT p.id FROM capex_code p "
                "   WHERE p.code = :parent_code AND p.organization_id IS NULL), TRUE "
                "WHERE :parent_code = '' OR EXISTS ("
                "  SELECT 1 FROM capex_code p "
                "  WHERE p.code = :parent_code AND p.organization_id IS NULL) "
                "ON CONFLICT (organization_id, code) DO NOTHING"
            ),
            fila,
        )
    # `path` legible y ordenable: HC.H09.10. Los puntos del código ya son los
    # separadores de ltree, y «General» se sanea porque ltree no admite tildes
    # ni espacios.
    conn.execute(
        text(
            "UPDATE capex_code SET path = "
            "  text2ltree(regexp_replace(code, '[^A-Za-z0-9.]', '_', 'g')) "
            "WHERE organization_id IS NULL"
        )
    )

    riesgos = _leer("riesgos.csv", base)
    for fila in riesgos:
        conn.execute(
            text(
                "INSERT INTO risk_level (organization_id, code, name_es, score, definition_es, "
                "is_system) VALUES (NULL, :code, :name_es, :score, :definition_es, TRUE) "
                "ON CONFLICT (organization_id, code) DO NOTHING"
            ),
            fila,
        )

    conceptos = _leer("conceptos.csv", base)
    for fila in conceptos:
        conn.execute(
            text(
                "INSERT INTO capex_concept (organization_id, code, name_es, is_system) "
                "VALUES (NULL, :code, :name_es, TRUE) "
                "ON CONFLICT (organization_id, code) DO NOTHING"
            ),
            fila,
        )

    horizontes = _leer("horizontes.csv", base)
    for i, fila in enumerate(horizontes):
        conn.execute(
            text(
                "INSERT INTO time_horizon (organization_id, code, name_es, year_from, year_to, "
                "is_execution_term, sort_order, is_system) "
                "VALUES (NULL, :code, :name_es, :year_from, :year_to, :is_execution_term, "
                ":sort_order, TRUE) ON CONFLICT (organization_id, code) DO NOTHING"
            ),
            {
                **fila,
                "year_from": fila["year_from"] or None,
                "year_to": fila["year_to"] or None,
                "is_execution_term": fila["is_execution_term"] == "true",
                "sort_order": i,
            },
        )

    # Los 14 sistemas técnicos de §3.2. `capex_chapter` se guarda tal cual —hay
    # uno que vale «H06 + H10»— porque el mapeo no siempre es a un solo capítulo.
    sistemas = _leer("sistemas_tecnicos.csv", base)
    for fila in sistemas:
        conn.execute(
            text(
                "INSERT INTO technical_system (organization_id, code, name_es, capex_chapter, "
                "sort_order, is_system) "
                "VALUES (NULL, :code, :name_es, :capex_chapter, :sort_order, TRUE) "
                "ON CONFLICT (organization_id, code) DO NOTHING"
            ),
            fila,
        )

    # `[REQ]` §5.9 · Qué capítulos del CAPEX toca cada sección de una memoria
    # técnica. Una fila sin `capex_code` significa «no mapea, y está decidido»:
    # `MC.0 Trabajos previos` es coste de obra, no del activo que se compra.
    secciones = _leer("secciones_memoria.csv", base)
    for fila in secciones:
        conn.execute(
            text(
                "INSERT INTO memoria_seccion (organization_id, seccion_code, name_es, "
                "capex_code_id, is_system) SELECT NULL, :seccion_code, :name_es, "
                "cc.id, TRUE FROM (SELECT 1) AS _ "
                "LEFT JOIN capex_code cc ON cc.code = NULLIF(:capex_code, '') "
                "  AND cc.organization_id IS NULL "
                "ON CONFLICT (organization_id, seccion_code, capex_code_id) DO NOTHING"
            ),
            fila,
        )

    # `[REQ]` §5.10 · El árbol documental del activo: 73 nodos, 60 casillas.
    #
    # `display_order` es la posición en el CSV y no se calcula al leer, porque el
    # orden correcto **no** es el alfabético: `S2.10` va detrás de `S2.9`, y
    # ordenar por `code` lo pondría entre `S2.1` y `S2.2`. El CSV sale de
    # `docs/05` §5.10 ya en el orden de la hoja del cliente, así que la posición
    # de la fila es el dato.
    #
    # Ni `level` ni el padre se guardan: se leen del propio código. Un nodo con
    # nivel 3 y padre de nivel 1 sería una contradicción que aquí no cabe.
    arbol = _leer("arbol_documental.csv", base)
    for i, fila in enumerate(arbol):
        conn.execute(
            text(
                "INSERT INTO doc_request_category (organization_id, code, name_es, "
                "display_order, is_system) VALUES (NULL, :code, :name_es, :orden, TRUE) "
                "ON CONFLICT (organization_id, code) DO UPDATE "
                "   SET name_es = EXCLUDED.name_es, display_order = EXCLUDED.display_order"
            ),
            {"code": fila["code"], "name_es": fila["name_es"], "orden": i},
        )

    traducidas = sembrar_traducciones(conn, base=base)

    return ResumenSemilla(
        typologies=n_tip,
        zones=n_zon,
        zone_typology=len(matriz),
        capex_codes=len(codigos),
        risk_levels=len(riesgos),
        concepts=len(conceptos),
        horizons=len(horizontes),
        technical_systems=len(sistemas),
        memoria_sections=len(secciones),
        doc_tree_nodes=len(arbol),
        traducciones=traducidas,
    )


#: `[REQ]` 0029 · Las tablas que llevan nombre inglés, y la columna donde va.
#: Es una lista blanca: el CSV nombra la tabla y el campo, y lo que no esté
#: aquí **falla** en vez de ejecutarse. Un fichero de datos no decide a qué
#: columna de qué tabla se escribe.
TRADUCIBLES: dict[str, frozenset[str]] = {
    "asset_typology": frozenset({"name_en"}),
    "zone": frozenset({"name_en"}),
    "capex_code": frozenset({"name_en"}),
    "risk_level": frozenset({"name_en", "definition_en"}),
    "capex_concept": frozenset({"name_en"}),
    "time_horizon": frozenset({"name_en"}),
    "technical_system": frozenset({"name_en"}),
    "phase_definition": frozenset({"name_en"}),
    "doc_request_category": frozenset({"name_en"}),
    "doc_check_type": frozenset({"name_en"}),
    "memoria_seccion": frozenset({"name_en"}),
}

#: `phase_definition` es del sistema entera y **no tiene** `organization_id`:
#: son las 8 fases de un encargo, iguales para todos. `memoria_seccion` sí lo
#: tiene, pero su clave no se llama `code`.
SIN_ORGANIZACION = frozenset({"phase_definition"})
CLAVE = {"memoria_seccion": "seccion_code"}


def sembrar_traducciones(conn: Connection, *, base: Path | None = None) -> int:
    """Rellena `name_en` de los catálogos del sistema. `[REQ]` 0029.

    Va en una pasada aparte y al final, y no dentro de cada `INSERT`, por una
    razón práctica: los `INSERT` de arriba llevan `ON CONFLICT DO NOTHING`, así
    que en una base que ya tenga los catálogos **no escribirían nada**. Esto es
    un `UPDATE`, de modo que sirve igual para una base nueva y para una que ya
    estaba sembrada —que es el caso de todas las que existen hoy—.

    Solo toca las filas del sistema (`organization_id IS NULL`). Lo que una
    organización haya añadido por su cuenta se queda como está: su traducción
    no la tenemos, y el respaldo `COALESCE(name_en, name_es)` enseña el
    castellano, que se lee como lo que es.

    `[LIM]` Si falta el CSV **no falla**, devuelve 0. Una instalación a la que
    le falte un fichero de datos tiene que poder arrancar; lo que no puede es
    dar por traducido lo que no está.
    """
    ruta = (base or CATALOGOS) / "traducciones_en.csv"
    if not ruta.exists():
        return 0
    with ruta.open(encoding="utf-8", newline="") as fh:
        filas = list(csv.DictReader(fh))

    for fila in filas:
        tabla, campo = fila["tabla"], fila["campo"]
        if campo not in TRADUCIBLES.get(tabla, frozenset()):
            raise ValueError(
                f"{ruta.name} apunta a {tabla}.{campo}, que no es una columna traducible"
            )
        clave = CLAVE.get(tabla, "code")
        filtro = "" if tabla in SIN_ORGANIZACION else " AND organization_id IS NULL"
        conn.execute(
            text(f"UPDATE {tabla} SET {campo} = :texto WHERE {clave} = :code{filtro}"),
            {"texto": fila["texto_en"], "code": fila["code"]},
        )
    return len(filas)
