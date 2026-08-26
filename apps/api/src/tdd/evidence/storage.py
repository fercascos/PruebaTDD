"""Almacenamiento de binarios · **puerto y adaptador de desarrollo**.

`[LIM]` **El adaptador de producción (S3 con Object Lock) NO está implementado
ni probado.** Lo que hay aquí es un adaptador sobre disco que sirve para la
suite y para levantar la aplicación en local. La barrera 4 del bloque de
fotografías —versionado y WORM sobre el prefijo `originals/`— es una propiedad
del bucket, no de este código, y no se puede afirmar que funcione hasta
probarla contra un bucket real.

Lo que sí es definitivo es la **forma de las claves** y el contrato del puerto:
el resto de la aplicación depende solo de `AlmacenDeObjetos`, así que sustituir
el adaptador no toca ni el servicio ni la API.

    {org}/{proyecto}/originals/{photo_id}.{ext}      ← inmutable
    {org}/{proyecto}/derivatives/{photo_id}/thumb-320.jpg
    {org}/{proyecto}/derivatives/{photo_id}/preview-1600.jpg

El identificador del objeto es un **UUID**, nunca el nombre que puso el
usuario: así renombrar no mueve bytes y un nombre con caracteres raros no puede
convertirse en una ruta con caracteres raros.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Protocol

#: Nombre de fichero de cada derivado dentro de su carpeta.
NOMBRE_DE_DERIVADO = {
    "MINIATURA_320": "thumb-320.jpg",
    "VISTA_1600": "preview-1600.jpg",
    "WEB": "web.jpg",
    "ANOTADA_RASTER": "annotated.jpg",
}

#: Lado máximo en píxeles de cada derivado.
LADO_DE_DERIVADO = {"MINIATURA_320": 320, "VISTA_1600": 1600, "WEB": 1200}


class ObjetoNoEncontrado(KeyError):
    """La clave no existe en el almacén."""


class OriginalInmutable(PermissionError):
    """`[REQ]` Se intentó sobrescribir un objeto bajo `originals/`.

    Es la barrera 4 llevada al puerto: aunque el bucket todavía no tenga Object
    Lock, el código no ofrece ninguna forma de sobrescribir un original.
    """


def clave_de_original(
    organization_id: uuid.UUID, project_id: uuid.UUID, photo_id: uuid.UUID, extension: str
) -> str:
    ext = extension.lstrip(".").lower()
    return f"{organization_id}/{project_id}/originals/{photo_id}.{ext}"


def clave_de_derivado(
    organization_id: uuid.UUID, project_id: uuid.UUID, photo_id: uuid.UUID, clase: str
) -> str:
    nombre = NOMBRE_DE_DERIVADO[clase]
    return f"{organization_id}/{project_id}/derivatives/{photo_id}/{nombre}"


def clave_de_documento(
    organization_id: uuid.UUID, project_id: uuid.UUID, document_id: uuid.UUID, extension: str
) -> str:
    ext = extension.lstrip(".").lower() or "bin"
    return f"{organization_id}/{project_id}/documents/{document_id}.{ext}"


def es_original(clave: str) -> bool:
    """Un documento y una plantilla son tan originales como una fotografía: no
    hay versión «derivada» de un PDF o de un PPTX del cliente que se pueda
    regenerar, así que también son inmutables. Los informes generados, en
    cambio, sí son derivados: se pueden volver a producir desde el snapshot."""
    return any(marca in clave for marca in ("/originals/", "/documents/", "/templates/"))


class AlmacenDeObjetos(Protocol):
    """El contrato. Nótese que **no existe una operación de sobrescritura**."""

    def guardar(self, clave: str, datos: bytes) -> None: ...
    def leer(self, clave: str) -> bytes: ...
    def existe(self, clave: str) -> bool: ...
    def borrar(self, clave: str) -> None: ...


class AlmacenEnDisco:
    """Adaptador de desarrollo y pruebas. `[LIM]` No apto para producción.

    Le faltan, como mínimo: URLs firmadas, versionado, Object Lock, cifrado en
    reposo y ciclo de vida. No se afirma que ninguna de esas cosas funcione.
    """

    def __init__(self, raiz: Path) -> None:
        self.raiz = Path(raiz)
        self.raiz.mkdir(parents=True, exist_ok=True)

    def _ruta(self, clave: str) -> Path:
        # Sin esto, una clave con `..` escribiría fuera de la raíz. Las claves
        # las genera el servidor, pero la comprobación no cuesta nada y el día
        # que alguien acepte una clave de fuera sigue en pie.
        destino = (self.raiz / clave).resolve()
        if not destino.is_relative_to(self.raiz.resolve()):
            raise ValueError("Clave de almacenamiento fuera de la raíz")
        return destino

    def guardar(self, clave: str, datos: bytes) -> None:
        ruta = self._ruta(clave)
        if es_original(clave) and ruta.exists():
            raise OriginalInmutable(f"El original {clave} ya existe y no se sobrescribe")
        ruta.parent.mkdir(parents=True, exist_ok=True)
        # Escritura atómica: un fallo a mitad no deja un original truncado que
        # parecería válido y no coincidiría con su hash.
        temporal = ruta.with_suffix(ruta.suffix + ".parcial")
        temporal.write_bytes(datos)
        temporal.replace(ruta)

    def leer(self, clave: str) -> bytes:
        ruta = self._ruta(clave)
        if not ruta.exists():
            raise ObjetoNoEncontrado(clave)
        return ruta.read_bytes()

    def existe(self, clave: str) -> bool:
        return self._ruta(clave).exists()

    def borrar(self, clave: str) -> None:
        if es_original(clave):
            raise OriginalInmutable(f"Un original no se borra desde el almacén ({clave})")
        ruta = self._ruta(clave)
        if ruta.exists():
            ruta.unlink()


class AlmacenEnMemoria:
    """Para pruebas que no deben tocar el disco."""

    def __init__(self) -> None:
        self._objetos: dict[str, bytes] = {}

    def guardar(self, clave: str, datos: bytes) -> None:
        if es_original(clave) and clave in self._objetos:
            raise OriginalInmutable(f"El original {clave} ya existe y no se sobrescribe")
        self._objetos[clave] = datos

    def leer(self, clave: str) -> bytes:
        if clave not in self._objetos:
            raise ObjetoNoEncontrado(clave)
        return self._objetos[clave]

    def existe(self, clave: str) -> bool:
        return clave in self._objetos

    def borrar(self, clave: str) -> None:
        if es_original(clave):
            raise OriginalInmutable(f"Un original no se borra desde el almacén ({clave})")
        self._objetos.pop(clave, None)


# ─────────────────────────────────────────────────────────────────────────────
#  Adaptador S3 · barrera 4
# ─────────────────────────────────────────────────────────────────────────────


class AlmacenConUrlFirmada(Protocol):
    """Puerto opcional: no todos los adaptadores saben firmar URLs.

    El de disco no puede, y no se finge que sí. Quien quiera una URL firmada
    comprueba con `isinstance`/`hasattr` en vez de recibir una cadena inútil.
    """

    def url_firmada(self, clave: str, *, segundos: int) -> str: ...


#: `[REQ]` Modos de Object Lock, y por qué el valor por defecto es `GOVERNANCE`.
#:
#: `COMPLIANCE` es más fuerte: **nadie**, ni la cuenta raíz, puede acortar la
#: retención ni borrar la versión hasta que venza. Es la lectura literal de
#: «los archivos originales nunca deben sobrescribirse».
#:
#: Y por eso mismo no puede ser el valor por defecto: choca de frente con el
#: derecho de supresión. Si un cliente ejerce su derecho al borrado, o si por
#: error entra en el bucket una fotografía con una persona identificable,
#: `COMPLIANCE` **impide atenderlo** durante los años que dure la retención. Se
#: cambiaría un riesgo técnico por uno legal.
#:
#: `GOVERNANCE` protege igual del accidente —hace falta un permiso explícito,
#: `s3:BypassGovernanceRetention`, que la aplicación no tiene— y deja una vía
#: auditable para el borrado legítimo. Quien despliegue puede subir a
#: `COMPLIANCE` sabiendo lo que acepta.
MODOS_DE_BLOQUEO = ("GOVERNANCE", "COMPLIANCE")


def construir_cliente(
    *,
    endpoint_url: str | None = None,
    region: str | None = None,
    access_key_id: str | None = None,
    secret_access_key: str | None = None,
) -> object:
    """El cliente de S3, con dos ajustes que no son opcionales.

    **Firma v4.** Sin fijarla, botocore firma algunas peticiones con la v2, que
    AWS **ya no admite** en las regiones creadas después de 2014: las URL
    firmadas saldrían con `AWSAccessKeyId=` y el almacén las rechazaría. Se vio
    en una prueba que miraba la URL generada.

    **Direccionamiento por ruta cuando hay `endpoint_url`.** Es la señal de que
    detrás hay un MinIO o similar, que no resuelve `bucket.host`.

    Las credenciales llegan por parámetro desde la configuración, que las lee
    del entorno. Si vienen vacías, botocore usa su cadena habitual —rol de la
    instancia, perfil—, que es lo preferible en producción: la credencial más
    segura es la que no hay que guardar en ningún sitio.
    """
    import boto3  # noqa: PLC0415 — solo se importa si se usa este adaptador
    from botocore.config import Config  # noqa: PLC0415

    ajustes = Config(signature_version="s3v4")
    if endpoint_url:
        ajustes = Config(signature_version="s3v4", s3={"addressing_style": "path"})
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url or None,
        region_name=region or None,
        aws_access_key_id=access_key_id or None,
        aws_secret_access_key=secret_access_key or None,
        config=ajustes,
    )


class AlmacenS3:
    """Adaptador sobre almacenamiento compatible con S3 (AWS, MinIO, …).

    **La barrera 4 no la pone este código: la pone el bucket.** Aquí solo se
    hacen tres cosas y conviene no confundirlas con la garantía:

    1. No se ofrece ninguna operación de sobrescritura de un original, y se
       comprueba antes de escribir.
    2. Al subir un original se le pide a S3 que lo retenga (`ObjectLockMode`).
    3. Borrar un original se rechaza aquí mismo.

    Lo que de verdad impide perder los bytes es que el bucket tenga
    **versionado y Object Lock activados al crearlo** —no se pueden activar
    después—, y eso es una propiedad de la infraestructura. `comprobar()` lo
    verifica contra el bucket real y dice qué falta.

    `[LIM]` Probado contra `moto`, que es un simulador en proceso: eso ejercita
    este código —incluido que S3 rechace borrar una versión retenida—, pero
    **no demuestra que un bucket concreto esté bien configurado**. Para eso
    está `comprobar()`, que hay que ejecutar contra el bucket de verdad.
    """

    def __init__(
        self,
        *,
        bucket: str,
        cliente: object | None = None,
        endpoint_url: str | None = None,
        region: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        object_lock: bool = True,
        modo_de_bloqueo: str = "GOVERNANCE",
        dias_de_retencion: int = 3650,
    ) -> None:
        if modo_de_bloqueo not in MODOS_DE_BLOQUEO:
            raise ValueError(f"Modo de bloqueo no válido: {modo_de_bloqueo}")
        self.bucket = bucket
        self.object_lock = object_lock
        self.modo_de_bloqueo = modo_de_bloqueo
        self.dias_de_retencion = dias_de_retencion

        if cliente is not None:
            self._s3 = cliente
            return
        self._s3 = construir_cliente(
            endpoint_url=endpoint_url,
            region=region,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
        )

    # ── Puerto ───────────────────────────────────────────────────────────────

    def guardar(self, clave: str, datos: bytes) -> None:
        if es_original(clave) and self.existe(clave):
            # Comprobar y escribir no es atómico, y da igual: la clave lleva un
            # UUID recién generado, así que no hay dos escrituras compitiendo
            # por la misma. Y si las hubiera, el versionado del bucket conserva
            # las dos: no se pierde nada, que es lo que importa.
            raise OriginalInmutable(f"El original {clave} ya existe y no se sobrescribe")

        extra: dict[str, object] = {}
        if self.object_lock and es_original(clave):
            from datetime import UTC, datetime, timedelta  # noqa: PLC0415

            extra = {
                "ObjectLockMode": self.modo_de_bloqueo,
                "ObjectLockRetainUntilDate": datetime.now(UTC)
                + timedelta(days=self.dias_de_retencion),
            }
        self._s3.put_object(Bucket=self.bucket, Key=clave, Body=datos, **extra)  # type: ignore[attr-defined]

    def leer(self, clave: str) -> bytes:
        from botocore.exceptions import ClientError  # noqa: PLC0415

        try:
            respuesta = self._s3.get_object(Bucket=self.bucket, Key=clave)  # type: ignore[attr-defined]
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
                raise ObjetoNoEncontrado(clave) from exc
            raise
        return respuesta["Body"].read()  # type: ignore[no-any-return]

    def existe(self, clave: str) -> bool:
        from botocore.exceptions import ClientError  # noqa: PLC0415

        try:
            self._s3.head_object(Bucket=self.bucket, Key=clave)  # type: ignore[attr-defined]
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return False
            raise
        return True

    def borrar(self, clave: str) -> None:
        if es_original(clave):
            raise OriginalInmutable(f"Un original no se borra desde el almacén ({clave})")
        self._s3.delete_object(Bucket=self.bucket, Key=clave)  # type: ignore[attr-defined]

    # ── Extras del adaptador ─────────────────────────────────────────────────

    def url_firmada(self, clave: str, *, segundos: int = 300) -> str:
        """URL temporal de lectura directa contra el almacén.

        `[REQ]` §18.5 · Un recurso, cinco minutos, y **después** de autorizar:
        firmar es un permiso, así que quien llame tiene que haber comprobado
        antes que ese usuario puede ver ese objeto. Una URL firmada emitida sin
        esa comprobación es una fuga con fecha de caducidad.
        """
        return self._s3.generate_presigned_url(  # type: ignore[attr-defined,no-any-return]
            "get_object", Params={"Bucket": self.bucket, "Key": clave}, ExpiresIn=segundos
        )

    def comprobar(self) -> list[str]:
        """Qué le falta al bucket para sostener la barrera 4. Vacío = correcto.

        Existe porque **el versionado y el Object Lock no se pueden activar
        después de crear el bucket**: si el bucket se creó mal, no hay arreglo,
        hay que crear otro y copiar. Descubrirlo el día que alguien sobrescribe
        un original es descubrirlo tarde.
        """
        from botocore.exceptions import ClientError  # noqa: PLC0415

        problemas: list[str] = []
        try:
            versionado = self._s3.get_bucket_versioning(Bucket=self.bucket)  # type: ignore[attr-defined]
        except ClientError as exc:
            codigo = exc.response["Error"]["Code"]
            return [f"No se puede consultar el bucket «{self.bucket}»: {codigo}"]
        if versionado.get("Status") != "Enabled":
            problemas.append(
                "El versionado del bucket NO está activado. Sin él, sobrescribir "
                "una clave destruye los bytes anteriores. No se puede activar de "
                "forma retroactiva sobre lo ya escrito."
            )
        try:
            self._s3.get_object_lock_configuration(Bucket=self.bucket)  # type: ignore[attr-defined]
        except ClientError:
            problemas.append(
                "El bucket NO tiene Object Lock. Solo se puede habilitar AL CREAR "
                "el bucket: hay que crear uno nuevo y copiar el contenido."
            )
        try:
            self._s3.get_bucket_cors(Bucket=self.bucket)  # type: ignore[attr-defined]
        except ClientError:
            # No es un problema de integridad, pero rompe la aplicación entera
            # en el navegador y de una forma que no se ve desde el servidor: la
            # API redirige bien, S3 devuelve el objeto, y el navegador se niega
            # a entregárselo al JavaScript por falta de `Access-Control-Allow-
            # Origin`. La rejilla sale vacía sin un solo error en el log.
            problemas.append(
                "El bucket no tiene reglas CORS. La aplicación sigue el 302 con "
                "`fetch`, así que el navegador exige que el bucket permita el "
                "origen de la aplicación en GET; si no, las imágenes no cargan "
                "y no aparece ningún error en el servidor."
            )
        return problemas


def construir(settings: Any) -> Any:
    """El adaptador de almacenamiento, y su diagnóstico al arrancar.

    Vive aquí y no en `main` porque **el worker también lo necesita**, y
    arrancar el worker no debe levantar la aplicación web entera para conseguir
    un almacén.

    Con S3 se comprueba el bucket **aquí**, no en la primera subida: el
    versionado y el Object Lock solo se pueden activar al crear el bucket, así
    que descubrir que falta el día que alguien sobrescribe un original es
    descubrirlo cuando ya no tiene arreglo.

    Se avisa y se sigue en vez de negarse a arrancar: un bucket sin WORM
    protege peor, pero negarse dejaría la aplicación caída por algo que quizá
    esté a medio migrar. Lo que no se hace es callarlo.
    """
    if settings.storage_backend != "s3":
        # [LIM] Sobre disco: sin URLs firmadas, sin versionado y sin Object
        # Lock. Vale para desarrollo y para la suite, no para producción.
        return AlmacenEnDisco(settings.storage_local_dir)

    almacen = AlmacenS3(
        bucket=settings.storage_bucket,
        endpoint_url=settings.storage_endpoint_url,
        region=settings.storage_region,
        access_key_id=settings.storage_access_key_id,
        secret_access_key=settings.storage_secret_access_key,
        object_lock=settings.storage_enable_object_lock,
        modo_de_bloqueo=settings.storage_object_lock_mode,
        dias_de_retencion=settings.storage_object_lock_days,
    )
    for problema in almacen.comprobar():
        logging.getLogger("tdd.almacen").error("Barrera 4 incompleta: %s", problema)
    return almacen
