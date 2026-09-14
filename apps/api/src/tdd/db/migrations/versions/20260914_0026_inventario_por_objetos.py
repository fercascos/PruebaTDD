"""El inventario por categorías y objetos.

Revisión: 0026
Anterior: 0025

`[REQ]` §3.2 d · Revisando el prototipo, el cliente pidió que el inventario del
activo se enseñe **«dividido por las distintas categorías y dentro de cada
categoría todos sus objetos»**, y que cada objeto lleve dos cuadros de texto:
**Descriptivo** —lo que dice la memoria técnica— y **Valoración** —lo que opina
el técnico que lo ha visto—, con su inventario de equipos debajo y sus
fotografías.

Tres cambios, y ninguno toca una fila existente.

## 1 · `descriptivo_objeto.valoracion`

Es una columna y no un párrafo más dentro de `texto` porque **son dos cosas con
dos procedencias**. El descriptivo se puede volver a traer del documento; la
valoración no se trae de ningún sitio, y traer el descriptivo encima de ella
borraría el trabajo de una persona. En la misma columna, además, nadie sabría
seis meses después qué se observó y qué se copió.

## 2 · La validación deja de exigir descriptivo

El CHECK decía «validado exige `texto` no vacío». Con dos textos la regla es que
haya **al menos uno**: hay objetos que se valoran sin describir —una fachada que
se ve y no aparece en ninguna memoria— y objetos que se describen antes de ir a
visitarlos. Se relaja, que es hacia donde se puede mover un CHECK sin romper
nada: lo que era válido lo sigue siendo.

## 3 · `equipment.capex_code_id`

El objeto del árbol al que pertenece cada equipo. Hoy un equipo solo sabe de qué
**sistema técnico** es, y de ahí no se deduce la categoría: el sistema
«Protección contra incendios» vale `H06 + H10` en la hoja del cliente —pasiva y
activa, dos capítulos—, así que generar su actuación tenía que adivinar o
rendirse. Preguntando el objeto **mientras se inventaría**, con el equipo
delante, la ambigüedad se resuelve donde hay alguien que sabe la respuesta.

`[LIM]` **No se rellena hacia atrás.** Se podría mapear el sistema al capítulo,
pero un capítulo tiene once objetos y elegir uno sería inventarse dónde está la
máquina. Las filas que ya existen se quedan sin objeto y la pantalla las reúne
aparte, en «sin clasificar», que es un sitio del que se sale mirando el equipo y
no adivinando desde una consulta.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Copia literal de `schema.sql`: los dos caminos de creación se comparan en
#: `test_migraciones.py`, así que esto no puede ser una versión parecida.
VALORACION = """\
ALTER TABLE descriptivo_objeto ADD COLUMN valoracion TEXT NOT NULL DEFAULT ''
"""

VALIDADO_NO_VACIO = """\
ALTER TABLE descriptivo_objeto DROP CONSTRAINT descriptivo_validado_no_vacio
"""

VALIDADO_NO_VACIO_NUEVO = """\
ALTER TABLE descriptivo_objeto ADD CONSTRAINT descriptivo_validado_no_vacio
    CHECK (
        validado_at IS NULL
        OR length(trim(texto)) > 0
        OR length(trim(valoracion)) > 0
    )
"""

OBJETO_DEL_EQUIPO = """\
ALTER TABLE equipment ADD COLUMN capex_code_id UUID REFERENCES capex_code(id)
"""

INDICE_OBJETO = """\
CREATE INDEX equipment_objeto_idx ON equipment (asset_id, capex_code_id)
"""


def upgrade() -> None:
    op.execute(VALORACION)
    op.execute(VALIDADO_NO_VACIO)
    op.execute(VALIDADO_NO_VACIO_NUEVO)
    op.execute(OBJETO_DEL_EQUIPO)
    op.execute(INDICE_OBJETO)


def downgrade() -> None:
    """`[LIM]` Se pierden las valoraciones escritas y el objeto de cada equipo.

    No hay dónde guardarlos: son las únicas columnas donde viven. Y volver al
    CHECK anterior **puede fallar** si alguien validó un objeto que solo tenía
    valoración: esa fila dejaría de cumplir la regla vieja. Se avisa en vez de
    fingir que la vuelta atrás es gratis.
    """
    op.execute("DROP INDEX equipment_objeto_idx")
    op.execute("ALTER TABLE equipment DROP COLUMN capex_code_id")
    op.execute(VALIDADO_NO_VACIO)
    op.execute(
        "ALTER TABLE descriptivo_objeto ADD CONSTRAINT descriptivo_validado_no_vacio "
        "CHECK (validado_at IS NULL OR length(trim(texto)) > 0)"
    )
    op.execute("ALTER TABLE descriptivo_objeto DROP COLUMN valoracion")
