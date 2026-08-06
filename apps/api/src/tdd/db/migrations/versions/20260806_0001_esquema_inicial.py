"""Esquema inicial: aplica la foto congelada del esquema en la revisión 0001.

Revisión: 0001
Anterior: ninguna

Esta migración **no reescribe el esquema en llamadas de Alembic**: ejecuta un
fichero SQL tal cual. Es deliberado.

**El fichero es `versions/sql/0001_esquema_inicial.sql`, no `db/schema.sql`.**
La distinción es el corazón de cómo funcionan las migraciones aquí y costó la
primera migración incremental descubrirla:

* `db/schema.sql` describe el esquema **de ahora**, el de `head`. Se actualiza
  con cada cambio y es lo que se lee para saber cómo es la base hoy.
* Este fichero describe el esquema **tal como era en la revisión 0001**, y no
  se toca nunca más.

Si 0001 leyera `db/schema.sql`, cada tabla nueva se crearía dos veces al migrar
desde cero —una en 0001, con el esquema ya actualizado, y otra en la migración
que la introduce— y `alembic upgrade head` reventaría con «relation already
exists» sobre una base vacía. Que es justo lo que pasó.

`schema.sql` es la única verdad del esquema, y contiene 6 políticas RLS
explícitas más las que crean dos bucles `DO $$`, 9 triggers, 14 funciones,
4 columnas generadas y 57 restricciones `CHECK`. Traducir todo eso a
`op.create_table(...)` tendría dos problemas, y el segundo es el grave:

1. Serían mil líneas de Python que dicen lo mismo que mil líneas de SQL, y las
   dos habría que mantenerlas sincronizadas a mano.
2. **Alembic no sabe expresar la mayor parte.** Las políticas, los triggers y
   las columnas generadas acabarían en `op.execute()` con el mismo SQL, y lo
   que quedaría en llamadas nativas sería justo lo que menos importa. Un
   esquema «migrado» al que le faltaran las políticas arrancaría sin errores y
   dejaría los datos de cada organización visibles para las demás.

Así que la migración inicial es el fichero, y las siguientes se escriben a mano.
`test_migraciones.py` comprueba que migrar desde cero produce exactamente la
misma estructura que aplicar `schema.sql` directamente: si alguien toca uno de
los dos caminos y no el otro, la suite lo dice.

`downgrade` **no existe a propósito**: deshacer el esquema inicial es borrar la
base entera. Ver el comentario de abajo.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: La foto congelada vive al lado, en `versions/sql/`. **No es `db/schema.sql`**:
#: ver el encabezado del módulo.
ESQUEMA = Path(__file__).resolve().parent / "sql" / "0001_esquema_inicial.sql"


def upgrade() -> None:
    sql = ESQUEMA.read_text(encoding="utf-8")
    if not sql.strip():
        # Un fichero vacío produciría una migración que «funciona» y deja la
        # base sin nada dentro. Mejor reventar aquí.
        raise RuntimeError(f"{ESQUEMA} está vacío: no hay esquema que aplicar")
    op.execute(sql)


def downgrade() -> None:
    raise NotImplementedError(
        "Deshacer el esquema inicial es borrar la base entera, incluidos los "
        "datos. No se automatiza: quien de verdad quiera hacerlo tiene "
        "`DROP SCHEMA public CASCADE` y la responsabilidad que conlleva. Un "
        "`downgrade` que lo hiciera solo convertiría un error de tecleo en una "
        "pérdida total."
    )
