"""`Certificación WIRESCORED` → `Certificación WIREDSCORE`.

Revisión: 0022
Anterior: 0021

La tercera y última errata de las listas del cliente, corregida por el mismo
criterio que las dos de `0021`: **en la plantilla y en el catálogo a la vez**,
porque estos textos son valores de listas cerradas por las que agrupan las tablas
dinámicas, y cambiar un solo lado deja una celda fuera de su propia lista —la
hoja se abre bien y el gráfico la deja fuera—.

Es una **transposición de letras**: el producto se llama *WiredScore*, y la
española escribía `WIRESCORED`. La plantilla inglesa ya lo tenía bien
—`WIREDSCORE Certification`—, así que aquí solo se toca el español.

`[SUP]` Se escribe en **mayúsculas** y no `WiredScore`, que sería la grafía de
marca. Dos razones: es como lo escribe la plantilla inglesa, y es como están sus
cuatro vecinas de la misma lista —BREEAM, LEED, WELL—. Corregir una errata es una
cosa y cambiar el estilo de la lista entera es otra, y solo se ha pedido la
primera. `[PDV]` Si el cliente prefiere `WiredScore`, es cambiar los dos lados
otra vez y no tiene más misterio.

**Se renombra, no se sustituye**, con el nombre anterior en el `WHERE`: la fila
conserva su `id` —ningún hallazgo cambia de código— y no se pisa el nombre de una
organización que lo hubiera editado.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ERRATA = """\
UPDATE capex_code
   SET name_es = 'Certificación WIREDSCORE'
 WHERE code = 'ESG.ES1.06' AND name_es = 'Certificación WIRESCORED'
"""


def upgrade() -> None:
    op.execute(ERRATA)


def downgrade() -> None:
    # Igual que en `0021`: la plantilla ya está corregida, y dejar el catálogo
    # con la errata rompería el puente entre los dos.
    raise RuntimeError(
        "0022 no se deshace: la plantilla española ya dice «WIREDSCORE» y el "
        "catálogo tiene que decir lo mismo que sus desplegables."
    )
