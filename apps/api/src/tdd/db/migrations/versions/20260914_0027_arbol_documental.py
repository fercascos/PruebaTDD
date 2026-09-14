"""El árbol documental del cliente ocupa el sitio de las categorías inventadas.

Revisión: 0027
Anterior: 0026

`[REQ]` §3.2 b · La documentación del activo es **el árbol de la hoja v2 del
cliente**: 73 nodos en tres niveles, de los que 60 no tienen hijos y son los que
llevan estado y documentos colgando. Está transcrito en `docs/05` §5.10 desde
hace semanas y se genera a `data/catalogos/arbol_documental.csv`, pero nadie lo
sembraba: la base seguía con las **seis categorías de relleno** que se pusieron
antes de que el árbol llegara —`MEMORIA_TECNICA`, `LICENCIAS_URBANISTICAS`…—.

Esta revisión hace sitio. La semilla es la que mete las 73 filas
(`tdd.catalogs.seeding`); aquí van los tres cambios de forma que hacen falta
para que quepan y para que el árbol no se pueda contradecir a sí mismo.

## 1 · `name_es` pasa de 120 a 400

Los nombres son del cliente y se transcriben literales, con sus paréntesis y sus
enumeraciones. El más largo del árbol tiene **342 caracteres** —el nodo de
REACH—, así que con 120 la semilla ni siquiera entra. Se podría haber acortado
el nombre; no se hace, porque esa frase es justo con la que el gestor reconoce
qué tiene que pedirle a la propiedad.

## 2 · Una casilla por nodo y activo

`doc_request_item` nació como una lista libre: se escribía un título y se metía
en una categoría, y nada impedía dos líneas iguales. Para el árbol eso no vale
—una casilla del árbol **es** un nodo—, así que se impone un único registro por
fase, activo y nodo.

El índice es **parcial**, `WHERE asset_id IS NOT NULL`, y esa condición es la
línea que separa las dos cosas que conviven en la tabla: lo que cuelga de un
activo es el árbol y no se repite; lo que no cuelga de ninguno sigue siendo la
checklist libre del proyecto, donde dos informes técnicos previos distintos son
dos líneas legítimas de la misma categoría.

## 3 · Las seis categorías de relleno se retiran

Y solo si **no las usa nadie**. Eran `[SUP]`: un armario provisional hasta que
llegara el árbol de verdad. Si alguna tiene líneas colgando se queda donde está
—borrarla se llevaría por delante trabajo de una persona— y convive con el
árbol hasta que se decida a dónde mover esas líneas.

`[LIM]` La retirada **no migra nada**. Una línea que estuviera en
`LICENCIAS_URBANISTICAS` no se reubica sola en `S1.1`: la categoría vieja abarca
cuatro nodos del árbol (`S1.1.1`…`S1.1.4`) y elegir uno sería inventarse cuál.
Se quedan donde están, visibles en la checklist del proyecto.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Copia literal de `schema.sql`: los dos caminos de creación se comparan en
#: `test_migraciones.py`, así que esto no puede ser una versión parecida.
NOMBRE_LARGO = """\
ALTER TABLE doc_request_category ALTER COLUMN name_es TYPE VARCHAR(400)
"""

CASILLA_UNICA = """\
CREATE UNIQUE INDEX doc_request_casilla_uniq
    ON doc_request_item (project_phase_id, asset_id, category_id)
    WHERE asset_id IS NOT NULL
"""

#: Las seis de relleno, por código. Se comparan con `is_system` y sin
#: organización porque una categoría que se haya creado un cliente con el mismo
#: código es suya y no se toca.
RETIRAR_RELLENO = """\
DELETE FROM doc_request_category c
 WHERE c.organization_id IS NULL
   AND c.is_system
   AND c.code IN ('MEMORIA_TECNICA', 'LICENCIAS_URBANISTICAS', 'PROYECTOS',
                  'CONTRATOS_MANTENIMIENTO', 'LEGALIZACIONES_CERTIFICADOS', 'GARANTIAS')
   AND NOT EXISTS (SELECT 1 FROM doc_request_item d WHERE d.category_id = c.id)
"""

#: La que sobreviva por tener líneas colgando se va **al final** de la lista.
#: Sin esto se quedaría con su `display_order` de 1 a 6, que es el rango donde
#: ahora empieza el árbol, y aparecería intercalada entre `S1.1.1` y `S1.2` en
#: todos los desplegables. Estar es inevitable; estorbar, no.
RELLENO_AL_FINAL = """\
UPDATE doc_request_category SET display_order = 900
 WHERE organization_id IS NULL
   AND is_system
   AND code IN ('MEMORIA_TECNICA', 'LICENCIAS_URBANISTICAS', 'PROYECTOS',
                'CONTRATOS_MANTENIMIENTO', 'LEGALIZACIONES_CERTIFICADOS', 'GARANTIAS')
"""


def upgrade() -> None:
    op.execute(NOMBRE_LARGO)
    op.execute(CASILLA_UNICA)
    op.execute(RETIRAR_RELLENO)
    op.execute(RELLENO_AL_FINAL)


def downgrade() -> None:
    """`[LIM]` No devuelve las seis categorías ni acorta los nombres largos.

    Volver a `VARCHAR(120)` **fallaría** en cuanto el árbol esté sembrado: hay
    nombres de 342 caracteres y PostgreSQL no los trunca solo. Y reponer las seis
    es trabajo de la semilla, no de aquí. Se deshace lo único que se puede
    deshacer sin perder ni inventar datos: el índice.
    """
    op.execute("DROP INDEX doc_request_casilla_uniq")
