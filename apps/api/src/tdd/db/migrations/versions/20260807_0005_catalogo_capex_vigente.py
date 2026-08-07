"""El catálogo CAPEX se pone al día con la plantilla vigente.

Revisión: 0005
Anterior: 0004

`[REQ]` Llegó la plantilla CAPEX DDT que usa el equipo, y trae dos cosas que el
catálogo sembrado no tenía: el **desglose de Medioambiental, ESG y Soft Costs**
—que §5.3 dejó abierto como P-03— y **cinco correcciones de literal** que la
comparación con la plantilla dejó a la vista.

De las cinco, dos no son cosméticas:

* La zona `CUADROS_TECNICOS` decía «Cuadros técnicos». La plantilla dice
  «Cuartos Técnicos» y la inglesa lo confirma: *Technical Rooms*. **Son cosas
  distintas**: un cuadro es eléctrico, un cuarto es un local. Se renombra el
  código también, porque `CUADROS_TECNICOS` seguiría induciendo al error cada
  vez que alguien lo leyera.
* «Detección de CO2» y «Extracción de CO2 y ventilación del parking» hablan de
  **monóxido**, no de dióxido: es lo que se detecta en un aparcamiento y lo que
  obliga a ventilar. La plantilla lo escribe bien.

`[REQ]` **Sin renumerar nada.** Es la promesa que §5.3 hizo al posponer P-03.
`MA.General` y `ESG.General` conservan su elemento `General` **en la primera
posición** —`MA.General.01` sigue siendo `MA.General.01`— y los elementos
nuevos se añaden detrás. Ninguna línea de CAPEX ya codificada cambia de código
ni se queda huérfana. `SC.General` se conserva por lo mismo, junto a los tres
capítulos nuevos.

Los nombres se escriben aquí **tal como los trae la plantilla**, erratas
incluidas (`Certificación WIRESCORED`, que debería ser *WiredScore*). Es
deliberado: son los literales que ofrecen sus desplegables, y escribir el
nombre correcto produciría celdas con un valor fuera de lista que las tablas
dinámicas dejarían fuera. Ver la nota de §5.3.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: Correcciones de literal sobre elementos que ya existen. `(código, nombre)`.
RENOMBRADOS: tuple[tuple[str, str], ...] = (
    ("HC.H07.02", "Accesibilidad entre las plantas"),
    ("HC.H08.07", "Ventilación aire primario"),
    ("HC.H10.08", "Detección de CO"),
    ("HC.H10.09", "Extracción de CO y ventilación del parking"),
)

#: Elementos nuevos de Medioambiental, en el orden de la plantilla y **detrás**
#: del `General` que ya estaba en `MA.General.01`.
MEDIOAMBIENTAL: tuple[str, ...] = (
    "Situación legal",
    "Gestión de residuos urbanos",
    "Gestión de residuos peligrosos",
    "Emisiones de gases",
    "Consumo de agua",
    "Sistemas de drenaje",
    "Ruido",
    "Contaminación del suelo",
    "Almacenamiento de sustancias peligrosas",
    "Sustancias reductoras de la capa de ozono (ODS)",
    "Presencia potencial de PCBs",
    "Certificado de sostenibilidad",
)

ESG: tuple[str, ...] = (
    "Análisis CRREM",
    "Análisis de Riesgos Climáticos",
    "Certificación BREEAM",
    "Certificación LEED",
    "Certificación WELL",
    "Certificación WIRESCORED",
    "Certificado de Eficiencia Energética",
    "Auditoría Net Zero",
    "Auditoría Energética",
    "Cumplimiento Nuevo Reglamento EPBD",
)

#: Capítulos de soft costs. `[REC]` No llevan lista de elementos y es fiel a la
#: plantilla: sus filas escriben el concepto en la columna de descripción, no en
#: un desplegable. Se les da un único `General` para que sean seleccionables.
SOFT_COSTS: tuple[tuple[str, str], ...] = (
    ("S01", "Proyectos, Diseño y DO"),
    ("S02", "Trabajos Complementarios"),
    ("S03", "Licencias y Tasas"),
)


def _anadir_elementos(capitulo: str, nombres: tuple[str, ...], desde: int) -> None:
    """Cuelga elementos de un capítulo, numerando a partir de `desde`.

    `ON CONFLICT DO NOTHING` para que la migración sea repetible: una base
    recién sembrada desde los CSV ya los trae, y volver a insertarlos chocaría
    contra la restricción única de `(organization_id, code)`.
    """
    for i, nombre in enumerate(nombres, start=desde):
        op.execute(
            f"""
            INSERT INTO capex_code (organization_id, code, name_es, level, parent_id, path)
            SELECT NULL, '{capitulo}.{i:02d}', $lit${nombre}$lit$, 3, p.id,
                   CAST('{capitulo}.{i:02d}' AS ltree)
            FROM capex_code p WHERE p.code = '{capitulo}' AND p.organization_id IS NULL
            ON CONFLICT (organization_id, code) DO NOTHING
            """
        )


def upgrade() -> None:
    # ── Zona mal nombrada ───────────────────────────────────────────────────
    # El código va con el nombre: dejar `CUADROS_TECNICOS` apuntando a «Cuartos
    # técnicos» sería peor que el fallo original, porque el error quedaría
    # escondido donde nadie lo lee.
    op.execute(
        "UPDATE zone SET code = 'CUARTOS_TECNICOS', name_es = 'Cuartos técnicos' "
        "WHERE code = 'CUADROS_TECNICOS'"
    )
    op.execute("UPDATE zone SET name_es = 'Salas uso sanitario' WHERE code = 'SALAS_USO_SANITARIO'")

    # ── Literales de Hard Costs ─────────────────────────────────────────────
    for codigo, nombre in RENOMBRADOS:
        op.execute(
            f"UPDATE capex_code SET name_es = $lit${nombre}$lit$ "
            f"WHERE code = '{codigo}' AND organization_id IS NULL"
        )

    # ── Desglose que cierra P-03 ────────────────────────────────────────────
    _anadir_elementos("MA.General", MEDIOAMBIENTAL, desde=2)
    _anadir_elementos("ESG.General", ESG, desde=2)

    for sufijo, nombre in SOFT_COSTS:
        op.execute(
            f"""
            INSERT INTO capex_code (organization_id, code, name_es, level, parent_id, path)
            SELECT NULL, 'SC.{sufijo}', $lit${nombre}$lit$, 2, p.id, CAST('SC.{sufijo}' AS ltree)
            FROM capex_code p WHERE p.code = 'SC' AND p.organization_id IS NULL
            ON CONFLICT (organization_id, code) DO NOTHING
            """
        )
        _anadir_elementos(f"SC.{sufijo}", ("General",), desde=1)


def downgrade() -> None:
    """Deshace el desglose y los renombrados.

    Los elementos nuevos solo se borran **si no los usa nadie**: un hallazgo
    codificado como `MA.General.05` bloquea el borrado, y eso es lo correcto —
    perder la clasificación de una actuación para poder retroceder una
    migración sería un mal negocio. El `DELETE` respeta la clave ajena y falla
    si hay referencias, que es exactamente el aviso que hace falta.
    """
    for sufijo, _ in SOFT_COSTS:
        op.execute(f"DELETE FROM capex_code WHERE code = 'SC.{sufijo}.01'")
        op.execute(f"DELETE FROM capex_code WHERE code = 'SC.{sufijo}'")
    op.execute("DELETE FROM capex_code WHERE code ~ '^MA\\.General\\.(0[2-9]|1[0-3])$'")
    op.execute("DELETE FROM capex_code WHERE code ~ '^ESG\\.General\\.(0[2-9]|1[01])$'")

    for codigo, nombre in (
        ("HC.H07.02", "Accesibilidad entre plantas"),
        ("HC.H08.07", "Ventilación de aire primario"),
        ("HC.H10.08", "Detección de CO2"),
        ("HC.H10.09", "Extracción de CO2 y ventilación del parking"),
    ):
        op.execute(
            f"UPDATE capex_code SET name_es = $lit${nombre}$lit$ "
            f"WHERE code = '{codigo}' AND organization_id IS NULL"
        )
    op.execute(
        "UPDATE zone SET name_es = 'Salas de uso sanitario' WHERE code = 'SALAS_USO_SANITARIO'"
    )
    op.execute(
        "UPDATE zone SET code = 'CUADROS_TECNICOS', name_es = 'Cuadros técnicos' "
        "WHERE code = 'CUARTOS_TECNICOS'"
    )
