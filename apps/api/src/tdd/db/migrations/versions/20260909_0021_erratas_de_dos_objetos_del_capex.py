"""Las dos erratas del árbol del cliente, corregidas.

Revisión: 0021
Anterior: 0020

`0020` copió **literales** dos nombres mal escritos de la hoja del cliente, y lo
hizo a propósito: el catálogo tiene que decir lo que dicen los desplegables de su
plantilla, y corregir uno de los dos lados por nuestra cuenta habría dejado la
base de datos y el Excel diciendo cosas distintas.

**El cliente ha pedido corregirlas**, así que se corrigen **los dos lados a la
vez**: aquí y en la plantilla española, con
`tools/corregir_erratas_plantillas.py`. Esa es la condición que faltaba.

- `Placas fotovoltáicas` → `Placas fotovoltaicas`. El diptongo `ai` es átono y no
  lleva tilde.
- `Bies` → `BIEs`. `BIE` es el acrónimo de Boca de Incendio Equipada, y su plural
  se escribe con la marca en minúscula detrás de las siglas.

La plantilla **inglesa** no hace falta tocarla: dice `Photovoltaic panels` y
`Fire hose reels`, que están bien.

**Se renombra, no se sustituye.** Igual que en `0020`: la fila conserva su `id`,
así que ningún hallazgo cambia de código. Y lleva el nombre anterior en el
`WHERE`, para no pisar el de una organización que lo hubiera editado.

`[REC]` Queda fuera `Certificación WIRESCORED`, que también está mal escrito
—el producto es *WiredScore*—, porque cuando se escribió esto el cliente no lo
había pedido. Lo pidió justo después: lo corrige `0022`, por este mismo camino.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ERRATAS = """\
UPDATE capex_code SET name_es = v.nuevo
FROM (VALUES
    ('HC.H09.14', 'Placas fotovoltáicas', 'Placas fotovoltaicas'),
    ('HC.H10.05', 'Bies',                 'BIEs')
) AS v(code, viejo, nuevo)
WHERE capex_code.code = v.code AND capex_code.name_es = v.viejo
"""


def upgrade() -> None:
    op.execute(ERRATAS)


def downgrade() -> None:
    # Volver a escribirlas mal es reversible y no cuesta nada, pero tampoco
    # sirve de nada: la plantilla ya está corregida, y dejar el catálogo con la
    # errata rompería el puente entre los dos. Si hay que volver atrás de
    # verdad, se revierten los dos a la vez.
    raise RuntimeError(
        "0021 no se deshace: la plantilla española ya está corregida y el "
        "catálogo tiene que decir lo mismo que sus desplegables."
    )
