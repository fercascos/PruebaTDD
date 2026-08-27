"""Comprueba la **barrera 4** (WORM) contra el bucket de verdad.

    python tools/comprobar_almacen.py            # lee la configuración del entorno
    python tools/comprobar_almacen.py --escribir # además, prueba a borrar y espera que S3 se niegue

`AlmacenEnS3.comprobar()` existía desde el principio y nunca se había ejecutado
contra nada: el adaptador estaba probado con `moto`, un simulador en proceso.
Eso ejercita el código —incluido que S3 rechace borrar una versión retenida—
pero **no demuestra que un bucket concreto esté bien creado**, que es justo lo
que falla en un despliegue: el versionado y el Object Lock solo se pueden
activar **al crear** el bucket, así que descubrirlo tarde no tiene arreglo, hay
que crear otro y copiar.

`[REQ]` Con `--escribir` sube un objeto de prueba y **no lo puede borrar**: si
el bucket está bien configurado, ese objeto se queda retenido los años que diga
la política. Úselo contra un bucket de pruebas, no contra el de producción.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "apps" / "api" / "src"))

from tdd.core.config import Settings  # noqa: E402
from tdd.evidence import storage  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--escribir",
        action="store_true",
        help="Sube un objeto de prueba y comprueba que S3 se niega a borrarlo.",
    )
    args = parser.parse_args(argv)

    settings = Settings()
    if settings.storage_backend != "s3":
        print(
            f"STORAGE_BACKEND es «{settings.storage_backend}», no «s3». "
            "Esta comprobación solo tiene sentido contra un bucket real.",
            file=sys.stderr,
        )
        return 2

    almacen = storage.construir(settings)
    print(
        f"Bucket «{settings.storage_bucket}» en "
        f"{settings.storage_endpoint_url or 'AWS'} · región {settings.storage_region}"
    )
    if not settings.storage_endpoint_url:
        # La distinción importa: MinIO es permisivo donde AWS no lo es, así que
        # un «todo correcto» contra MinIO no dice nada de un bucket de AWS.
        print("  · Contra AWS de verdad. Es lo que MinIO no puede demostrar (docs/21).")

    problemas = almacen.comprobar()  # type: ignore[union-attr]
    for p in problemas:
        print(f"  ✗ {p}")
    if not problemas:
        print("  ✓ Versionado, Object Lock y CORS en su sitio.")

    # `[REQ]` El permiso que rompe cada subida si falta.
    #
    # La aplicación sube cada original con `ObjectLockMode`, y **ese parámetro
    # exige `s3:PutObjectRetention` aparte de `s3:PutObject`**. Sin él fallan
    # las fotografías, los documentos y las plantillas, pero NO los derivados,
    # que se suben sin retención: parece un fallo intermitente y no lo es.
    #
    # Se comprueba con `--escribir`, porque comprobarlo es subir.

    if args.escribir:
        # La clave tiene que **parecer un original**, y eso significa llevar
        # `/originals/`: `es_original()` mira exactamente eso, y de ello depende
        # que se pida retención al subir y que borrar se rechace. Una clave con
        # otra forma se trata como derivado —correctamente— y la comprobación
        # acusaría al almacén de un fallo que no tiene. Pasó aquí.
        clave = f"comprobacion/{uuid.uuid4()}/originals/prueba.bin"
        try:
            almacen.guardar(clave, b"objeto de comprobacion, sin datos reales")
        except Exception as exc:  # noqa: BLE001 — es un ClientError de botocore
            # El caso que más caro sale y peor se diagnostica: los derivados
            # suben y los originales no.
            codigo = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if codigo in ("AccessDenied", "AccessDeniedException"):
                print(
                    "  ✗ AccessDenied al subir un ORIGINAL. Casi seguro falta "
                    "`s3:PutObjectRetention`: la retención se pide como parámetro "
                    "aparte y necesita su propio permiso. Los derivados seguirían "
                    "subiendo, así que parecería un fallo intermitente.",
                    file=sys.stderr,
                )
                return 1
            raise
        print(f"  · Subido {clave}")

        print("  ✓ Se puede escribir un original CON retención (s3:PutObjectRetention)")

        try:
            almacen.borrar(clave)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001 — el tipo lo pone el adaptador
            print(
                f"  ✓ El adaptador se niega a borrar el original: {type(exc).__name__}"
            )
        else:
            problemas.append(
                "El adaptador ha BORRADO un original. La barrera 4 no existe: "
                "revise `es_original()` y la política del bucket."
            )
            print("  ✗ El adaptador ha borrado un original")

        # Y ahora saltándose el adaptador, que es lo que de verdad prueba que la
        # garantía la sostiene el bucket y no nuestro código.
        cliente = almacen._s3  # noqa: SLF001 — comprobación deliberada de la capa de abajo
        versiones = cliente.list_object_versions(
            Bucket=settings.storage_bucket, Prefix=clave
        )
        for v in versiones.get("Versions", []):
            try:
                cliente.delete_object(
                    Bucket=settings.storage_bucket, Key=clave, VersionId=v["VersionId"]
                )
            except Exception as exc:  # noqa: BLE001 — es un ClientError de botocore
                print(
                    f"  ✓ S3 rechaza borrar la versión retenida: {type(exc).__name__}"
                )
            else:
                problemas.append(
                    "S3 ha permitido borrar la versión de un original retenido. "
                    "El bucket NO tiene Object Lock efectivo."
                )
                print("  ✗ S3 ha permitido borrar la versión")

        # CORS **medido**, no supuesto.
        #
        # `comprobar()` avisa cuando el bucket no declara reglas, pero no puede
        # saber si eso importa: MinIO y un bucket de AWS sin reglas devuelven el
        # mismo `NoSuchCORSConfiguration`, y MinIO acepta cualquier origen por
        # defecto. Lo único que zanja la duda es pedir el objeto **como lo pide
        # un navegador** y mirar si vuelve la cabecera.
        origen = settings.app_base_url.rstrip("/")
        url = almacen.url_firmada(clave, segundos=60)  # type: ignore[union-attr]
        peticion = urllib.request.Request(url, headers={"Origin": origen})  # noqa: S310
        try:
            with urllib.request.urlopen(peticion, timeout=15) as r:  # noqa: S310
                permitido = r.headers.get("Access-Control-Allow-Origin")
        except Exception as exc:  # noqa: BLE001 — cualquier fallo de red vale como «no»
            permitido = None
            print(
                f"  ! No se pudo pedir el objeto firmado: {type(exc).__name__}: {exc}"
            )
        if permitido in ("*", origen):
            print(
                f"  ✓ El almacén permite el origen «{origen}» (devolvió «{permitido}»)"
            )
            # Si el navegador puede leerlo, el aviso de configuración sobra.
            problemas = [p for p in problemas if "CORS" not in p]
        else:
            print(
                f"  ✗ El almacén NO permite el origen «{origen}» (devolvió «{permitido}»)"
            )
            if not any("CORS" in p for p in problemas):
                problemas.append(
                    f"El almacén no devuelve CORS para el origen «{origen}»"
                )

    if problemas:
        print(
            f"\n{len(problemas)} problemas. La barrera 4 NO está garantizada.",
            file=sys.stderr,
        )
        return 1
    print("\nLa barrera 4 se sostiene contra este bucket.")
    return 0


if __name__ == "__main__":  # pragma: no cover — punto de entrada
    raise SystemExit(main())
