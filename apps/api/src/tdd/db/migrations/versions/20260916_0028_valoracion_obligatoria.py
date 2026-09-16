"""Validar un descriptivo exige haberlo valorado.

Revisión: 0028
Anterior: 0027

`[REQ]` El cliente lo pidió con estas palabras: *«si hay descriptivo debería ser
obligatorio que hubiera una valoración por parte del técnico»*. Y es la regla
correcta, porque las dos columnas no son lo mismo y por eso están separadas: el
**descriptivo** dice qué hay y lo trae la memoria técnica; la **valoración** dice
en qué estado está y **no la trae ningún documento**, la escribe quien ha ido a
verlo.

De ahí que un objeto pudiera quedarse a medias sin que nadie lo notara: el
descriptivo se rellenaba solo, se marcaba la casilla de validado y la valoración
se quedaba vacía. En el informe eso salía como una sección con su texto y, al
pie, el rótulo «Valoración» encabezando media página en blanco.

## Por qué `NOT VALID`, y no es una forma de escurrir el bulto

La restricción entra **sin comprobar las filas que ya existen**. PostgreSQL la
aplica a todo lo que se inserte o se actualice a partir de ahora, y deja en paz
lo anterior. Es deliberado, y la alternativa era peor:

* Validarla exigiría **arreglar antes** las filas que no cumplen, y las dos
  formas de arreglarlas son malas. Inventar una valoración está prohibido y
  sería mentir en un entregable. Quitarles la casilla de validado le deshace el
  trabajo a alguien sin avisarle, y en una base de producción eso son horas de
  un técnico que un día se encuentra su inventario a medio validar.
* Dejarlas en paz **no las esconde**: el aviso `MISSING_ASSESSMENT` las saca una
  por una, con su sección y su código, cada vez que se previsualiza el informe.

Así que la restricción para las nuevas y el aviso para las viejas. Cuando el
equipo termine de valorarlas, `VALIDATE CONSTRAINT` la convierte en firme sin
tocar nada más, y esa orden ya no arriesga nada porque para entonces se sabe que
no hay ninguna fila que la incumpla.

## Lo que NO cambia

Un objeto **valorado y sin describir** sigue siendo válido: hay elementos que se
ven en la visita y no aparecen en ninguna memoria. La restricción de antes
—`descriptivo_validado_no_vacio`, que solo pedía una de las dos— se queda donde
está: ésta añade la exigencia en un sentido, no la sustituye.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Copia literal de `schema.sql`: los dos caminos de creación se comparan en
#: `test_migraciones.py`, así que esto no puede ser una versión parecida.
VALORACION_OBLIGATORIA = """\
ALTER TABLE descriptivo_objeto
    ADD CONSTRAINT descriptivo_validado_con_valoracion
    CHECK (
        validado_at IS NULL
        OR length(trim(texto)) = 0
        OR length(trim(valoracion)) > 0
    ) NOT VALID
"""


def upgrade() -> None:
    op.execute(VALORACION_OBLIGATORIA)


def downgrade() -> None:
    op.execute("ALTER TABLE descriptivo_objeto DROP CONSTRAINT descriptivo_validado_con_valoracion")
