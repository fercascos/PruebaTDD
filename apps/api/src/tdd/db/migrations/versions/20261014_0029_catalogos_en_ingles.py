"""Los catálogos, también en inglés.

Revisión: 0029
Anterior: 0028

`[REQ]` El cliente pidió una versión en inglés para sus compañeros de negocio.
La interfaz ya la tiene (`i18n/`, S-05), pero eso solo traduce **los rótulos
que están en el código**. El contenido de los desplegables, los nombres de los
capítulos de CAPEX, las zonas, los conceptos y los horizontes salen de la base,
y hasta ahora solo había `name_es`: una pantalla en inglés enseñaba «Affected
area: Cuartos técnicos».

Lo mismo pasaba con el informe, y ahí se ve peor: la plantilla inglesa ponía
las cabeceras en inglés y las filas en castellano.

## De dónde sale el inglés

**No se ha traducido: se ha leído del fichero inglés que el cliente ya usa.**
Sus dos plantillas CAPEX —`capex_ddt_es.xltm` y `capex_ddt_en.xltm`— son el
mismo libro con las etiquetas cambiadas, celda a celda, así que la misma celda
de las dos hojas es una pareja de traducción. De ahí salen 230 de las 336
filas, entre ellas las 20 zonas, las 6 tipologías, los 10 conceptos, los 4
niveles de riesgo con su definición entera y 174 de los 178 códigos CAPEX.

Importa porque la traducción obvia habría sido la equivocada en sitios que
duelen: «Comercial» es **Retail** y no *Commercial*; «Vida útil» es **End of
useful life** y no *Useful life*; «Normativa» es **Regulatory** y no
*Regulations*. Eso no se adivina: se lee.

Las otras 106 —el árbol documental y las secciones de memoria, que no aparecen
en ninguna plantilla inglesa porque esa parte no se le entrega traducida al
comprador— son **nuestras**, y están marcadas como tales en
`data/catalogos/traducciones_en.csv`, columna `fuente`. Quien firme el informe
sabe cuáles revisar.

El reparto lo reconstruye `tools/extraer_ingles_del_cliente.py`, con
`--check` en las pruebas para que el CSV no se desfase de las plantillas.

## Por qué `NULL` y no `NOT NULL`

`name_en` entra **sin valor por omisión y admitiendo nulo**. Es deliberado:

* Una organización puede añadir sus propios códigos de CAPEX y sus propias
  zonas (`organization_id IS NOT NULL`). Nadie va a traducirlos al darlos de
  alta, y exigirlo rompería el alta. Tampoco se puede rellenar con el
  castellano: eso convierte «no traducido» en «traducido», que es la mentira
  que esta aplicación no cuenta en ninguna otra parte.
* El respaldo es explícito y está en un solo sitio: `COALESCE(name_en,
  name_es)`. Falta una traducción y sale el castellano, que **se lee** como lo
  que es —esto no está traducido— en vez de un hueco o un código.

Es la misma decisión que en el frontend, y por el mismo motivo.

## Qué NO hace esta migración

No toca `definition_es` de `risk_level` más que para añadirle su pareja, ni
reescribe ninguna fila existente: solo rellena las columnas nuevas de las filas
del sistema (`organization_id IS NULL`), que son las que vienen de la semilla.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path

from alembic import op
from sqlalchemy import text

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Copia literal de `schema.sql`, tabla por tabla y con el mismo ancho que su
#: `name_es`. Los dos caminos de creación se comparan en `test_migraciones.py`,
#: así que esto no puede ser una versión parecida.
#:
#: El ancho se iguala al del castellano a propósito, aunque el inglés suele ser
#: más corto: el día que alguien alargue un nombre español, el inglés le cabe.
COLUMNAS: tuple[tuple[str, str, int], ...] = (
    ("asset_typology", "name_en", 120),
    ("zone", "name_en", 120),
    ("capex_code", "name_en", 200),
    ("risk_level", "name_en", 60),
    ("capex_concept", "name_en", 120),
    ("time_horizon", "name_en", 60),
    ("technical_system", "name_en", 120),
    ("phase_definition", "name_en", 120),
    ("doc_request_category", "name_en", 400),
    ("doc_check_type", "name_en", 120),
    ("memoria_seccion", "name_en", 160),
)

#: `risk_level` lleva además la definición entera, que el informe imprime como
#: leyenda. Es `TEXT` y no `VARCHAR`, igual que su pareja española.
TEXTOS: tuple[tuple[str, str], ...] = (("risk_level", "definition_en"),)

#: Dónde está el CSV, relativo a la raíz del repositorio.
RELATIVA = Path("data") / "catalogos" / "traducciones_en.csv"


def _csv_de_traducciones() -> Path:
    """Sube buscando `data/catalogos/traducciones_en.csv`.

    `[REQ]` Busca en vez de contar. La primera versión ponía
    `parents[5]`, y luego `parents[6]`, y las dos estaban mal: este fichero
    cuelga de `apps/api/src/tdd/db/migrations/versions/`, que son **siete**
    niveles, y contarlos de memoria falla —falló dos veces seguidas—.

    Lo que lo hizo caro no fue el número: fue que la primera versión se
    saltaba el relleno en silencio cuando no encontraba el fichero, así que
    la migración se aplicaba sin errores y dejaba los catálogos monolingües.
    El fallo ruidoso de `upgrade()` es la red, y esto quita la necesidad de
    usarla.
    """
    for carpeta in Path(__file__).resolve().parents:
        if (candidato := carpeta / RELATIVA).exists():
            return candidato
    # No se encontró: se devuelve una ruta nombrable para que el error de
    # `upgrade()` diga qué se buscaba y no un `None`.
    return Path(__file__).resolve().parents[-1] / RELATIVA


#: `phase_definition` es del sistema entera y **no tiene** `organization_id`:
#: son las 8 fases de un encargo, iguales para todos. El resto se filtra por la
#: fila de sistema para no tocar lo que una organización haya añadido.
SIN_ORGANIZACION = frozenset({"phase_definition"})

#: Y la clave de `memoria_seccion` no se llama `code`.
CLAVE = {"memoria_seccion": "seccion_code"}


def upgrade() -> None:
    for tabla, columna, ancho in COLUMNAS:
        op.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} VARCHAR({ancho})")
    for tabla, columna in TEXTOS:
        op.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} TEXT")

    # `[REQ]` Si el CSV no está, **falla**. La primera versión de esto se lo
    # saltaba en silencio «para que una instalación incompleta pudiera
    # arrancar», y eso es justo lo que escondió el error de la línea de
    # arriba: la migración se aplicó limpia, dijo que todo bien y dejó los
    # catálogos monolingües. Una migración que no puede hacer su trabajo tiene
    # que decirlo; el fichero viene con el código, así que si falta es que la
    # instalación está mal, no que haya que seguir adelante.
    csv_traducciones = _csv_de_traducciones()
    if not csv_traducciones.exists():
        raise FileNotFoundError(
            f"No se encuentra {RELATIVA} desde {Path(__file__).parent}, "
            "que trae el inglés de los catálogos. "
            "Ejecute `python3 tools/extraer_ingles_del_cliente.py`."
        )

    conn = op.get_bind()
    aplicadas = 0
    with csv_traducciones.open(encoding="utf-8", newline="") as fh:
        for fila in csv.DictReader(fh):
            tabla, campo = fila["tabla"], fila["campo"]
            if campo not in {c for _, c, _ in COLUMNAS} | {c for _, c in TEXTOS}:
                raise ValueError(f"columna desconocida en el CSV: {tabla}.{campo}")
            clave = CLAVE.get(tabla, "code")
            filtro = "" if tabla in SIN_ORGANIZACION else " AND organization_id IS NULL"
            resultado = conn.execute(
                text(f"UPDATE {tabla} SET {campo} = :texto WHERE {clave} = :code{filtro}"),
                {"texto": fila["texto_en"], "code": fila["code"]},
            )
            aplicadas += resultado.rowcount

    # Cero filas tocadas con un CSV de 333 líneas significa una de dos cosas, y
    # ninguna es «ya estaba»: o la base no tiene los catálogos sembrados —el
    # caso normal de una instalación nueva, donde la semilla los pondrá
    # después con su inglés— o el emparejamiento por `code` no casa con nada,
    # que es un fallo. Se distingue preguntando.
    if aplicadas == 0:
        hay_catalogos = conn.execute(
            text("SELECT EXISTS (SELECT 1 FROM zone WHERE organization_id IS NULL)")
        ).scalar()
        if hay_catalogos:
            raise RuntimeError(
                "Los catálogos están sembrados y ninguna de las traducciones ha "
                "encontrado su fila. Revise la columna `code` de traducciones_en.csv."
            )


def downgrade() -> None:
    for tabla, columna in TEXTOS:
        op.execute(f"ALTER TABLE {tabla} DROP COLUMN {columna}")
    for tabla, columna, _ in COLUMNAS:
        op.execute(f"ALTER TABLE {tabla} DROP COLUMN {columna}")
