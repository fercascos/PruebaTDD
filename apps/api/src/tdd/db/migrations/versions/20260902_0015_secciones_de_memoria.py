"""La correspondencia sección de memoria → capítulo CAPEX, como catálogo.

Revisión: 0015
Anterior: 0014

`[REQ]` §5.9 · Una memoria técnica **no trae la lista de las 15 categorías del
CAPEX**. Se comprobó leyendo una de verdad: trae una memoria constructiva
redactada según el Código Técnico, con sus propias secciones —`MC.0` a `MC.7`—
y los elementos enumerados en prosa dentro de cada una. Las categorías se
**deducen** de esas secciones.

Y la correspondencia no es uno a uno en ninguna de las dos direcciones:

* `MC.2 Cimentación` y `MC.3 Sistema estructural` caen las dos en `H01`.
* `MC.6 Instalaciones` reparte sus elementos entre **seis** capítulos.

Por eso es una tabla de catálogo y no un diccionario en el código: la segunda
memoria que llegue traerá otra numeración o secciones que ésta no tiene, y
corregirlo tiene que ser editar una fila, no desplegar. Las filas salen de
`data/catalogos/secciones_memoria.csv`, que a su vez se genera de §5.9: el
documento sigue siendo la fuente de verdad.

`capex_code_id` nulo significa «esta sección no mapea a ningún capítulo, **y
está decidido**». `MC.0 Trabajos previos` —vallado, implantación, replanteo— es
coste de obra, no del activo que se compra. Sin la fila no se distinguiría de
una sección olvidada.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Copia literal de `schema.sql`: los dos caminos de creación se comparan.
CATALOGO = """\
CREATE TABLE memoria_seccion (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organization(id),
    seccion_code    VARCHAR(10) NOT NULL,
    name_es         VARCHAR(160) NOT NULL,
    capex_code_id   UUID REFERENCES capex_code(id),
    is_system       BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE NULLS NOT DISTINCT (organization_id, seccion_code, capex_code_id)
);

CREATE INDEX memoria_seccion_codigo_idx ON memoria_seccion (seccion_code);
"""


def upgrade() -> None:
    op.execute(CATALOGO)
    op.execute("ALTER TABLE memoria_seccion ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE memoria_seccion FORCE ROW LEVEL SECURITY")
    # La política de CATÁLOGO, no la de aislamiento: las filas del sistema
    # (`organization_id IS NULL`) las ve todo el mundo; las propias, solo su
    # organización. Es lo mismo que hacen `zone` y `capex_code`.
    op.execute(
        "CREATE POLICY memoria_seccion_catalogo ON memoria_seccion "
        "USING (organization_id IS NULL OR organization_id = org_actual()) "
        "WITH CHECK (organization_id = org_actual())"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS memoria_seccion")
