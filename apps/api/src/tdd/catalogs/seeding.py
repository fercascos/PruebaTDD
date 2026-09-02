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

    def __str__(self) -> str:
        return (
            f"{self.typologies} tipologías · {self.zones} zonas · "
            f"{self.zone_typology} relaciones zona×tipología · "
            f"{self.capex_codes} códigos CAPEX · {self.risk_levels} riesgos · "
            f"{self.concepts} conceptos · {self.horizons} horizontes · "
            f"{self.technical_systems} sistemas técnicos · "
            f"{self.memoria_sections} secciones de memoria"
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
    )
