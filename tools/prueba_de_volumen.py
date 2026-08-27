"""El criterio de aceptación de volumen del bloque 4, medido.

`[REQ]` §20.5 · «Se genera un informe de **≥ 40 diapositivas** con **3 activos,
40 hallazgos, 60 líneas y 35 fotografías**».

Ese criterio llevaba desde el principio sin marcar, y no por olvido: hasta ahora
no había ni las tipografías corporativas ni una forma de montar un encargo de
ese tamaño. Esto lo hace y **da los números**: cuántas diapositivas salen, cuánto
tarda, cuánto ocupa y qué avisos de desbordamiento se emiten **midiendo con la
Gotham real**, que es lo único que hace que ese aviso valga algo.

    python3 tools/prueba_de_volumen.py --plantilla /ruta/plantilla.pptx

`[REQ]` §15 · Todo lo que siembra es **ficticio**: nombres, importes, textos y
fotografías generadas. Apúntelo solo a una base de demostración; escribe
directamente sobre ella y no limpia lo que crea.

`[LIM]` Lo que esto **no** contesta es la otra mitad del criterio: «y un
consultor lo considera entregable con retoques menores». Eso lo decide una
persona abriendo el fichero en PowerPoint, y no hay forma de automatizarlo.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "apps" / "api" / "src"))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from tdd.reporting import generator, snapshot  # noqa: E402

#: El tamaño que pide §20.5. No se redondea a un número bonito: es el criterio.
ACTIVOS, HALLAZGOS, LINEAS, FOTOS = 3, 40, 60, 35

#: `[REQ]` §15 · Texto de relleno con la longitud de uno real, no «lorem ipsum».
#: Importa: lo que se mide es si **cabe**, y un párrafo corto no probaría nada.
#: Multiplica la longitud de los textos, para provocar el desbordamiento a
#: propósito y comprobar que el aviso salta. Con `1` son textos de longitud
#: realista y no debería saltar ninguno.
FACTOR = int(os.environ.get("TDD_FACTOR_TEXTO", "1"))

PARRAFO = (
    "Se observa degradación generalizada del elemento, con pérdida de sección en "
    "los puntos de anclaje y presencia de óxido activo en la cara inferior. La "
    "actuación propuesta contempla el saneado mecánico de las superficies "
    "afectadas, la aplicación de imprimación de dos componentes y el repintado "
    "con esmalte de poliuretano. Se recomienda ejecutar la intervención fuera de "
    "la temporada de lluvias y coordinarla con la parada técnica de la "
    "instalación para no interrumpir la operativa del centro. "
)


def _sembrar(
    s: Session, org: uuid.UUID, usuario: uuid.UUID, cliente: uuid.UUID
) -> uuid.UUID:
    """Un encargo del tamaño del criterio. Devuelve su identificador."""
    proyecto = s.execute(
        text(
            "INSERT INTO project (organization_id, client_id, internal_code, name, status) "
            "VALUES (:o, :c, :cod, 'Cartera logística · prueba de volumen', 'EN_ANALISIS') "
            "RETURNING id"
        ),
        {
            "o": str(org),
            "c": str(cliente),
            "cod": f"VOL-{uuid.uuid4().hex[:6].upper()}",
        },
    ).scalar_one()

    tipologia = s.execute(
        text("SELECT id FROM asset_typology ORDER BY sort_order LIMIT 1")
    ).scalar_one()
    zonas = [
        r[0]
        for r in s.execute(
            text(
                "SELECT z.id FROM zone z JOIN zone_typology zt ON zt.zone_id = z.id "
                "WHERE zt.typology_id = :t ORDER BY z.sort_order"
            ),
            {"t": tipologia},
        ).all()
    ]
    codigos = [
        r[0]
        for r in s.execute(
            text("SELECT id FROM capex_code WHERE level = 3 ORDER BY code LIMIT 20")
        ).all()
    ]
    horizontes = [
        r[0]
        for r in s.execute(
            text("SELECT id FROM time_horizon ORDER BY sort_order")
        ).all()
    ]
    riesgos = [
        r[0] for r in s.execute(text("SELECT id FROM risk_level ORDER BY id")).all()
    ]

    activos = []
    for i in range(ACTIVOS):
        activos.append(
            s.execute(
                text(
                    "INSERT INTO asset (organization_id, project_id, typology_id, name, "
                    "asset_code, city, country_code, total_built_sqm, year_built) "
                    "VALUES (:o, :p, :t, :n, :c, 'Getafe', 'ES', 18500, 2004) RETURNING id"
                ),
                {
                    "o": str(org),
                    "p": str(proyecto),
                    "t": tipologia,
                    "n": f"Nave {chr(65 + i)} · Ficticia",
                    "c": f"GTF-{chr(65 + i)}",
                },
            ).scalar_one()
        )

    # Un perfil de coste, que las líneas necesitan.
    perfil = s.execute(
        text(
            "INSERT INTO cost_profile (organization_id, name, cascade_config, is_default) "
            'VALUES (:o, :n, CAST(\'{"convencion": "espanola"}\' AS jsonb), FALSE) '
            "RETURNING id"
        ),
        # Nombre único por ejecución: el perfil lleva un índice único por
        # organización y nombre, así que repetir la prueba chocaba con el perfil
        # de la vez anterior.
        {"o": str(org), "n": f"Volumen {uuid.uuid4().hex[:6]}"},
    ).scalar_one()

    hallazgos = []
    for i in range(HALLAZGOS):
        hallazgos.append(
            s.execute(
                text(
                    "INSERT INTO finding (organization_id, project_id, asset_id, zone_id, "
                    "capex_code_id, risk_level_id, title, description, recommendation, status, "
                    "created_by) VALUES (:o, :p, :a, :z, :c, :r, :t, :d, :rec, 'VALIDADO', :u) "
                    "RETURNING id"
                ),
                {
                    "o": str(org),
                    "p": str(proyecto),
                    "a": activos[i % ACTIVOS],
                    "z": zonas[i % len(zonas)],
                    "c": codigos[i % len(codigos)],
                    "r": riesgos[i % len(riesgos)],
                    "t": f"Hallazgo {i + 1:02d} · deterioro en elemento constructivo",
                    # Longitud realista: es lo que decide si el aviso de
                    # desbordamiento salta o no.
                    "d": PARRAFO * 2 * FACTOR,
                    "rec": PARRAFO,
                    "u": str(usuario),
                },
            ).scalar_one()
        )

    # 60 líneas sobre 40 hallazgos: 20 llevan dos plazos (P-44), el resto uno.
    puestas = 0
    for i, hallazgo in enumerate(hallazgos):
        cuantas = 2 if i < LINEAS - HALLAZGOS else 1
        for j in range(cuantas):
            s.execute(
                text(
                    "INSERT INTO capex_item (organization_id, project_id, finding_id, "
                    "cost_profile_id, time_horizon_id, amount, tax_pct, price_status) "
                    "VALUES (:o, :p, :f, :cp, :h, :a, 0.21, 'SIN_PRECIO')"
                ),
                {
                    "o": str(org),
                    "p": str(proyecto),
                    "f": hallazgo,
                    "cp": perfil,
                    "h": horizontes[(i + j) % len(horizontes)],
                    "a": 1250 * (i + 1) + 700 * j,
                },
            )
            puestas += 1
    return proyecto, activos, puestas


def _fotos(
    s: Session, org: uuid.UUID, proyecto: uuid.UUID, activos: list, usuario: uuid.UUID
):
    """35 fotografías sintéticas, con su objeto y su derivado."""
    from PIL import Image

    from tdd.evidence import storage

    almacen = storage.AlmacenEnMemoria()
    for i in range(FOTOS):
        foto_id = uuid.uuid4()
        im = Image.new("RGB", (1600, 1200), (40 + i * 5 % 200, 90, 140))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=80)
        datos = buf.getvalue()

        clave_o = storage.clave_de_original(org, proyecto, foto_id, "jpg")
        clave_d = storage.clave_de_derivado(org, proyecto, foto_id, "VISTA_1600")
        almacen.guardar(clave_o, datos)
        almacen.guardar(clave_d, datos)

        objeto = s.execute(
            text(
                "INSERT INTO stored_object (organization_id, project_id, kind, storage_key, "
                "sha256, byte_size, mime_type, is_original) "
                "VALUES (:o, :p, 'PHOTO', :k, :h, :b, 'image/jpeg', TRUE) RETURNING id"
            ),
            {
                "o": str(org),
                "p": str(proyecto),
                "k": clave_o,
                "h": uuid.uuid4().hex * 2,
                "b": len(datos),
            },
        ).scalar_one()

        s.execute(
            text(
                "INSERT INTO photo (organization_id, project_id, asset_id, stored_object_id, "
                "original_filename, display_name, file_extension, mime_type, sha256, "
                "byte_size, status, origin, include_in_report, report_order, caption, "
                "uploaded_by) "
                "VALUES (:o, :p, :a, :so, :fn, :dn, 'jpg', 'image/jpeg', :h, :b, 'LISTA', "
                "'CAMARA', TRUE, :ord, :cap, :u) RETURNING id"
            ),
            {
                "o": str(org),
                "p": str(proyecto),
                "a": activos[i % len(activos)],
                "so": objeto,
                "fn": f"IMG_{i:04d}.jpg",
                "dn": f"Ficticia_{i:04d}",
                "h": uuid.uuid4().hex * 2,
                "b": len(datos),
                "ord": i,
                "cap": f"Detalle {i + 1} · elemento con deterioro visible",
                "u": str(usuario),
            },
        )
    return almacen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plantilla", required=True, type=Path, help="PPTX real del cliente"
    )
    parser.add_argument(
        "--dsn",
        default=os.environ.get("DATABASE_MIGRATION_URL")
        or os.environ.get("DATABASE_URL", ""),
        help="Conexión de ADMINISTRACIÓN a una base de DEMOSTRACIÓN.",
    )
    parser.add_argument(
        "--salida", type=Path, default=Path("/tmp/informe-volumen.pptx")
    )
    args = parser.parse_args(argv)
    if not args.dsn:
        print("Falta la conexión: defina DATABASE_URL o pase --dsn.", file=sys.stderr)
        return 2

    # ── Las tipografías, antes de nada ──────────────────────────────────────
    from tdd.reporting import fonts

    faltan = [f for f in fonts.FAMILIAS_REQUERIDAS if fonts.localizar(f) is None]
    print("── Tipografías corporativas")
    if faltan:
        print(f"   ✗ Faltan {len(faltan)}: {', '.join(faltan)}")
        print("     Sin ellas el aviso de desbordamiento NO se emite: el módulo")
        print("     prefiere callarse antes que medir con una sustituta.")
    else:
        print(
            f"   ✓ Las {len(fonts.FAMILIAS_REQUERIDAS)} instaladas. Se mide de verdad."
        )

    motor = create_engine(args.dsn, future=True)
    with Session(motor) as s, s.begin():
        org = s.execute(
            text("SELECT id FROM organization ORDER BY created_at LIMIT 1")
        ).scalar()
        usuario = s.execute(
            text("SELECT id FROM app_user ORDER BY created_at LIMIT 1")
        ).scalar()
        cliente = s.execute(
            text("SELECT id FROM client ORDER BY created_at LIMIT 1")
        ).scalar()
        if not (org and usuario and cliente):
            print("La base no tiene organización, usuario o cliente.", file=sys.stderr)
            return 2

        print(
            f"\n── Sembrando {ACTIVOS} activos, {HALLAZGOS} hallazgos, {LINEAS} líneas"
        )
        t0 = time.perf_counter()
        proyecto, activos, lineas = _sembrar(s, org, usuario, cliente)
        almacen = _fotos(s, org, proyecto, activos, usuario)
        print(
            f"   {lineas} líneas y {FOTOS} fotografías en {time.perf_counter() - t0:.1f} s"
        )

    with Session(motor) as s:
        print("\n── Congelando la instantánea")
        t0 = time.perf_counter()
        instantanea = snapshot.construir(s, proyecto)
        t_snap = time.perf_counter() - t0
        print(f"   {len(instantanea.get('findings', []))} hallazgos · {t_snap:.2f} s")

        from tdd.reporting.produccion import fotos_del_snapshot

        fotos = fotos_del_snapshot(s, almacen, instantanea)
        print(f"   {len(fotos)} fotografías recuperadas del almacén")

    print("\n── Generando el informe con la plantilla real")
    plantilla = args.plantilla.read_bytes()
    t0 = time.perf_counter()
    resultado = generator.generar(plantilla, instantanea, fotos=fotos)
    t_gen = time.perf_counter() - t0

    args.salida.write_bytes(resultado.pptx)
    from pptx import Presentation

    diapositivas_plantilla = len(Presentation(io.BytesIO(plantilla)).slides._sldIdLst)

    print("\n── Resultado, contra el criterio de §20.5")
    cumple = resultado.diapositivas >= 40
    print(
        f"   Diapositivas            {resultado.diapositivas}"
        f"   (plantilla: {diapositivas_plantilla})   "
        f"{'✓ ≥ 40' if cumple else '✗ menos de 40'}"
    )
    print(f"   De ellas, de tabla      {resultado.diapositivas_de_tabla}")
    print(f"   Fotografías insertadas  {resultado.fotos_insertadas} de {FOTOS}")
    print(f"   Tiempo de generación    {t_gen:.1f} s")
    print(f"   Tamaño PPTX             {len(resultado.pptx) / 1024 / 1024:.1f} MB")
    print(f"   Tamaño XLSX             {len(resultado.xlsx) / 1024:.0f} KB")
    print(f"   Marcadores sin resolver {len(resultado.marcadores_sin_resolver)}")
    for m in resultado.marcadores_sin_resolver[:8]:
        print(f"     · {m}")
    print(f"   Marcas de agua retiradas {len(resultado.marcas_de_agua_retiradas)}")
    print(f"   Desbordamientos de texto {len(resultado.desbordamientos)}")
    for d in resultado.desbordamientos[:5]:
        print(f"     · {d}")
    if len(resultado.desbordamientos) > 5:
        print(f"     … y {len(resultado.desbordamientos) - 5} más")
    print(f"   Avisos del Excel         {len(resultado.avisos_del_excel)}")
    for aviso in resultado.avisos_del_excel[:4]:
        print(f"     · {aviso}")
    print(f"\n   Escrito en {args.salida}")
    return 0 if cumple else 1


if __name__ == "__main__":  # pragma: no cover — punto de entrada
    raise SystemExit(main())
