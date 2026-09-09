"""El árbol de CAPEX que mantiene el cliente, con sus códigos.

Revisión: 0020
Anterior: 0019

El cliente mandó su estructura —6 tipos de coste, 28 categorías, 141 objetos— y
pidió que **los códigos del catálogo sean los suyos**. La mayoría ya coincidían
(`H01`…`H15`); los que no, hay que renombrarlos aquí, porque sembrar solo añade
y dejarlo así habría dejado el desplegable con las dos versiones de cada
concepto: `MA.General › Ruido` y `MA.MA1 › Ruido`.

**Renombrar la fila, y no crear una nueva y mover los hallazgos.** La fila
conserva su `id`, así que todo lo que apunta a ella —`finding`, `photo`,
`memoria_categoria`, `memoria_objeto`— sigue apuntando a lo mismo sin tocar una
sola de esas tablas. Es la diferencia entre una migración de una página y un
remapeo que hay que validar hallazgo a hallazgo.

**Solo se renombra lo que nadie ha editado.** El catálogo es editable por
organización: si un administrador cambió el nombre de un capítulo, ese nombre es
suyo y esta migración no lo pisa. Por eso los `UPDATE` de nombre llevan el
nombre anterior en el `WHERE`.

**Y aguanta que la siembra haya ido antes.** Si el código de destino ya existe
—porque alguien sembró el catálogo nuevo antes de migrar—, no se renombra: se
mueve lo que apunta a la fila vieja y la vieja se deprecia. Sin eso, la
migración fallaría por el `UNIQUE (organization_id, code)` en exactamente el
orden de despliegue que más prisas tiene.

`[LIM]` Dos nombres del cliente traen erratas —`Placas fotovoltáicas` lleva una
tilde que no le corresponde y `Bies` es el acrónimo BIE mal escrito—. Se copian
**literales**, por la misma razón que `WIRESCORED` en §5.3: el catálogo tiene
que decir lo que dicen sus desplegables. Corregirlo exige corregir su hoja.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: `(código, nombre anterior, nombre nuevo)`. Copia literal de lo que produce
#: `tools/importar_arbol_capex.py` sobre la hoja del cliente.
NOMBRES = """\
UPDATE capex_code SET name_es = v.nuevo
FROM (VALUES
    ('HC',        'Hard Costs',                        'Hard Cost'),
    ('MA',        'Medioambiental',                    'Medioambiente'),
    ('ESG',       'ESG & Energía',                     'ESG y Energía'),
    ('SC',        'Soft Costs',                        'Soft Cost'),
    ('OP',        'Operativos',                        'Operativo'),
    ('HC.H06',    'Protección pasiva contra incendios','Protección Pasiva Incendios'),
    ('HC.H10',    'Protección activa contra incendios','Protección Activa Incendios'),
    ('HC.H13',    'Seguridad, CCTV y BMS',             'Seguridad CCTV y BMS'),
    ('HC.H09.14', 'Placas fotovoltaicas',              'Placas fotovoltáicas'),
    ('HC.H10.05', 'BIEs',                              'Bies'),
    ('MA.General',  'General',      'Medioambiente'),
    ('ESG.General', 'General',      'ESG'),
    ('SC.General',  'General',      'Otros'),
    ('OP.C01',      'Consumos Obra','Consumos obra')
) AS v(code, viejo, nuevo)
WHERE capex_code.code = v.code AND capex_code.name_es = v.viejo
"""

#: `(código viejo, código nuevo)`. Las categorías y los objetos que cambian de
#: código porque el cliente los numera de otra manera.
CODIGOS = """\
DO $$
DECLARE
    par RECORD;
    destino UUID;
    origen UUID;
BEGIN
    FOR par IN SELECT * FROM (VALUES
        -- Categorías
        ('MA.General',  'MA.MA1'),
        ('ESG.General', 'ESG.ES1'),
        ('OP.C01',      'OP.OP1'),
        ('OP.C02',      'OP.OP2'),
        ('IMP.General', 'IMP.IM1'),
        -- [SUP] El «General» de soft costs pasa a ser su «Otros»: el cliente no
        -- lo trae, y un soft cost codificado como «General» es exactamente lo
        -- que ese cajón recoge.
        ('SC.General',  'SC.S04'),
        -- Objetos. El orden dentro de cada categoría cambia —el cliente pone
        -- «General» al final y añade «Otros»—, así que el emparejamiento es por
        -- nombre y no por posición.
        ('MA.General.01', 'MA.MA1.13'),
        ('MA.General.02', 'MA.MA1.01'),
        ('MA.General.03', 'MA.MA1.02'),
        ('MA.General.04', 'MA.MA1.03'),
        ('MA.General.05', 'MA.MA1.04'),
        ('MA.General.06', 'MA.MA1.05'),
        ('MA.General.07', 'MA.MA1.06'),
        ('MA.General.08', 'MA.MA1.07'),
        ('MA.General.09', 'MA.MA1.08'),
        ('MA.General.10', 'MA.MA1.09'),
        ('MA.General.11', 'MA.MA1.10'),
        ('MA.General.12', 'MA.MA1.11'),
        ('MA.General.13', 'MA.MA1.12'),
        ('ESG.General.01', 'ESG.ES1.11'),
        ('ESG.General.02', 'ESG.ES1.01'),
        ('ESG.General.03', 'ESG.ES1.02'),
        ('ESG.General.04', 'ESG.ES1.03'),
        ('ESG.General.05', 'ESG.ES1.04'),
        ('ESG.General.06', 'ESG.ES1.05'),
        ('ESG.General.07', 'ESG.ES1.06'),
        ('ESG.General.08', 'ESG.ES1.07'),
        ('ESG.General.09', 'ESG.ES1.08'),
        ('ESG.General.10', 'ESG.ES1.09'),
        ('ESG.General.11', 'ESG.ES1.10')
    ) AS t(viejo, nuevo)
    LOOP
        SELECT id INTO origen FROM capex_code WHERE code = par.viejo;
        CONTINUE WHEN origen IS NULL;

        SELECT id INTO destino FROM capex_code WHERE code = par.nuevo;
        IF destino IS NULL THEN
            UPDATE capex_code SET code = par.nuevo WHERE id = origen;
        ELSE
            -- La siembra fue antes: se mueve lo que apunta a la vieja y la
            -- vieja se deprecia. Deprecar y no borrar, porque un informe
            -- emitido tiene que seguir resolviendo su código.
            UPDATE finding            SET capex_code_id = destino WHERE capex_code_id = origen;
            UPDATE photo              SET capex_code_id = destino WHERE capex_code_id = origen;
            UPDATE memoria_categoria  SET capex_code_id = destino WHERE capex_code_id = origen;
            UPDATE memoria_objeto     SET capex_code_id = destino WHERE capex_code_id = origen;
            UPDATE capex_code SET deprecated_at = now() WHERE id = origen;
        END IF;
    END LOOP;
END $$
"""

#: Los objetos «General» de las categorías que en la estructura del cliente **no
#: tienen objetos**. No se borran —lo que ya está codificado ahí tiene que
#: seguir resolviéndose— pero dejan de ofrecerse, y lo que apunta a ellos sube a
#: su categoría, que es un nivel válido para codificar un hallazgo.
HUERFANOS = """\
DO $$
DECLARE
    par RECORD;
    destino UUID;
    origen UUID;
BEGIN
    FOR par IN SELECT * FROM (VALUES
        ('SC.General.01',  'SC.S04'),
        ('SC.S01.01',      'SC.S01'),
        ('SC.S02.01',      'SC.S02'),
        ('SC.S03.01',      'SC.S03'),
        ('OP.C01.01',      'OP.OP1'),
        ('OP.C02.01',      'OP.OP2'),
        ('IMP.General.01', 'IMP.IM1')
    ) AS t(viejo, categoria)
    LOOP
        SELECT id INTO origen  FROM capex_code WHERE code = par.viejo;
        SELECT id INTO destino FROM capex_code WHERE code = par.categoria;
        CONTINUE WHEN origen IS NULL OR destino IS NULL;

        UPDATE finding           SET capex_code_id = destino WHERE capex_code_id = origen;
        UPDATE photo             SET capex_code_id = destino WHERE capex_code_id = origen;
        UPDATE memoria_categoria SET capex_code_id = destino WHERE capex_code_id = origen;
        UPDATE memoria_objeto    SET capex_code_id = destino WHERE capex_code_id = origen;
        UPDATE capex_code SET deprecated_at = now() WHERE id = origen AND deprecated_at IS NULL;
    END LOOP;
END $$
"""

#: `path` se deriva del código, así que renombrar sin recalcularlo dejaría las
#: consultas por subárbol —«todo el CAPEX de electricidad»— mirando al sitio
#: equivocado. Misma expresión que usa la siembra.
CAMINOS = """\
UPDATE capex_code
   SET path = text2ltree(regexp_replace(code, '[^A-Za-z0-9.]', '_', 'g'))
 WHERE path IS DISTINCT FROM text2ltree(regexp_replace(code, '[^A-Za-z0-9.]', '_', 'g'))
"""


def upgrade() -> None:
    op.execute(NOMBRES)
    op.execute(CODIGOS)
    op.execute(HUERFANOS)
    op.execute(CAMINOS)


def downgrade() -> None:
    # No se deshace: los códigos viejos ya no existen en ningún sitio del que
    # reconstruirlos, y lo que se movió de fila no sabe de dónde venía. Volver
    # atrás significa restaurar una copia, que es lo honesto que se puede decir.
    raise RuntimeError(
        "0020 no se deshace: renombra códigos del catálogo. Restaure una copia de seguridad."
    )
