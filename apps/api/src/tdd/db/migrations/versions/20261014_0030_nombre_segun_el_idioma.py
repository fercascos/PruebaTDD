"""El nombre de un catálogo, en el idioma de la petición.

Revisión: 0030
Anterior: 0029

La 0029 puso el inglés en la base. Esto lo sirve.

## La decisión: una función en SQL, no un `if` en Python

Hay tres sitios que leen los nombres de los catálogos y los tres tienen que
decir lo mismo:

1. La API, que los enseña en la pantalla.
2. El generador de informes PPTX, que los imprime.
3. La exportación a XLSX, que rellena la plantilla del cliente.

Resolver el idioma en Python obliga a pasar el idioma por los tres caminos y a
acordarse en cada consulta. El tercero es el que lo delata: la cola de tareas
corre en un **worker**, sin petición HTTP de la que sacar un `Accept-Language`,
así que acabaría con su propio mecanismo y dos mecanismos discrepan.

Así que el idioma viaja por donde ya viaja el contexto de la organización: una
**variable de sesión** que se fija con `set_config(..., TRUE)` al abrir la
transacción, igual que `app.current_org_id`. La misma pieza que hace que la RLS
no se pueda olvidar hace que el idioma no se pueda olvidar.

Y la regla vive en una función:

    nombre(name_es, name_en)

que devuelve el inglés si la sesión está en inglés **y lo hay**, y el castellano
en cualquier otro caso. Un solo sitio decide la regla, y las consultas que
agrupan por nombre —el reparto de CAPEX por capítulo, por concepto, por
riesgo— pueden poner `GROUP BY nombre(...)` sin más.

## Por qué el respaldo es `COALESCE` y no un error

`name_en` admite nulo (ver 0029). Una organización que añade su propio código de
CAPEX no lo traduce, y la pantalla en inglés tiene que seguir funcionando: sale
el castellano, que **se lee** como lo que es —esto no está traducido— en vez de
un hueco o un código interno.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Copia literal de `schema.sql`. Los dos caminos de creación se comparan en
#: `test_migraciones.py`, que entre otras cosas compara las funciones.
#:
#: `STABLE` y no `IMMUTABLE`: el resultado depende de `current_setting`, que
#: cambia entre transacciones. Marcarla `IMMUTABLE` dejaría a PostgreSQL
#: precalcularla o cachear un plan con el valor de otra sesión, y una pantalla
#: en inglés podría salir en castellano sin motivo aparente. `STABLE` dice la
#: verdad —constante dentro de una consulta, no entre consultas— y con eso
#: basta para usarla en un `GROUP BY`. Lo que `STABLE` no permite, y tampoco
#: hace falta, es indexar la expresión.
#:
#: `PARALLEL SAFE` porque solo lee una variable de sesión, que los procesos
#: paralelos heredan.
#:
#: El segundo argumento de `current_setting` es `TRUE`: *missing_ok*. Sin él,
#: una consulta fuera de una petición —`psql`, una migración, el arranque del
#: worker antes de fijar el contexto— reventaría con «unrecognized
#: configuration parameter» en vez de devolver el castellano.
NOMBRE = """\
CREATE FUNCTION nombre(es TEXT, en TEXT) RETURNS TEXT
    LANGUAGE sql
    STABLE
    PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN current_setting('app.idioma', TRUE) = 'en' THEN COALESCE(en, es)
        ELSE es
    END
$$
"""

COMENTARIO = """\
COMMENT ON FUNCTION nombre(TEXT, TEXT) IS
'[REQ] 0030 · El nombre de un catalogo en el idioma de la sesion. '
'Lee app.idioma, que fija aplicar_contexto() igual que el contexto RLS. '
'Si no hay traduccion devuelve el castellano, a proposito.'
"""


def upgrade() -> None:
    op.execute(NOMBRE)
    op.execute(COMENTARIO)


def downgrade() -> None:
    op.execute("DROP FUNCTION nombre(TEXT, TEXT)")
