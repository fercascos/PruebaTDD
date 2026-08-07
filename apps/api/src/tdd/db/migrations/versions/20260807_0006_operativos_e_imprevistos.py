"""Operativos e Imprevistos entran en el catálogo.

Revisión: 0006
Anterior: 0005

`[REQ]` La plantilla CAPEX declara seis tipos de coste en «00 Datos
Categorías», pero la 0005 solo sembró cuatro. Los dos que faltaban —Operativos
e Imprevistos— se dejaron fuera **porque la hoja `CapEx` no tenía ninguna fila
donde escribirlos**: darles código sin sitio habría creado actuaciones
imposibles de exportar.

Ese impedimento ya no existe: `tools/anadir_bloques_plantillas.py` les da su
bloque en las dos plantillas, al final de la hoja y sobre filas que estaban
vacías. Así que ahora sí se siembran.

* **Operativos** es un bloque itemizado normal, con los dos capítulos que
  declara la plantilla: `Consumos Obra` y `Limpieza`. Comparten las mismas diez
  filas —la plantilla no da más—, y `comprobar_cabida` las cuenta juntas.
* **Imprevistos** se monta como los soft costs: su importe sale de un
  porcentaje sobre los hard costs que vive en «00 Datos Activo»!C45. La primera
  fila de su bloque la escribe la plantilla; la aplicación empieza en la
  siguiente, para no borrar esa fórmula.

Ninguno de los dos tiene lista de objetos en «00 Datos Objeto», igual que los
capítulos de soft costs, así que llevan un único elemento `General`. Inventar
una lista habría producido códigos que la plantilla no sabe colocar.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: `(código, nombre, código del padre, nivel)`, en orden de creación.
NODOS: tuple[tuple[str, str, str | None, int], ...] = (
    ("OP", "Operativos", None, 1),
    ("IMP", "Imprevistos", None, 1),
    ("OP.C01", "Consumos Obra", "OP", 2),
    ("OP.C02", "Limpieza", "OP", 2),
    ("IMP.General", "General", "IMP", 2),
    ("OP.C01.01", "General", "OP.C01", 3),
    ("OP.C02.01", "General", "OP.C02", 3),
    ("IMP.General.01", "General", "IMP.General", 3),
)


def upgrade() -> None:
    for codigo, nombre, padre, nivel in NODOS:
        if padre is None:
            op.execute(
                f"""
                INSERT INTO capex_code (organization_id, code, name_es, level, parent_id, path)
                VALUES (NULL, '{codigo}', $lit${nombre}$lit$, {nivel}, NULL,
                        CAST('{codigo}' AS ltree))
                ON CONFLICT (organization_id, code) DO NOTHING
                """
            )
        else:
            op.execute(
                f"""
                INSERT INTO capex_code (organization_id, code, name_es, level, parent_id, path)
                SELECT NULL, '{codigo}', $lit${nombre}$lit$, {nivel}, p.id,
                       CAST('{codigo}' AS ltree)
                FROM capex_code p WHERE p.code = '{padre}' AND p.organization_id IS NULL
                ON CONFLICT (organization_id, code) DO NOTHING
                """
            )


def downgrade() -> None:
    """De hijos a padres, o la clave ajena lo impide.

    Un hallazgo ya codificado como `OP.C01.01` bloquea el borrado, y es lo
    correcto: perder la clasificación de una actuación para poder retroceder
    una migración sería un mal negocio.
    """
    for codigo, _, _, _ in reversed(NODOS):
        op.execute(f"DELETE FROM capex_code WHERE code = '{codigo}' AND organization_id IS NULL")
