"""Adaptador S3 y la barrera 4 `[REQ]` §15 · docs/10.

**Qué prueba esto y qué no.** Se ejecuta contra `moto`, un simulador de S3 en
proceso. Eso ejercita de verdad el código del adaptador —qué parámetros manda,
qué hace ante un original que ya existe, cómo traduce los errores— y también
una parte de la garantía: `moto` **sí rechaza** borrar una versión retenida.

Lo que **no** demuestra es que un bucket concreto de producción esté bien
configurado. El versionado y el Object Lock solo se pueden activar al crear el
bucket, y eso es infraestructura. Para eso está `comprobar()`, que se ejecuta
contra el bucket real y dice qué falta; aquí se comprueba que `comprobar()`
detecta un bucket mal creado, que es lo único comprobable desde una prueba.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from moto import mock_aws

from tdd.evidence.storage import (
    AlmacenS3,
    ObjetoNoEncontrado,
    OriginalInmutable,
    clave_de_derivado,
    clave_de_original,
    construir_cliente,
)

REGION = "eu-west-1"
ORG, PROY, FOTO = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
ORIGINAL = clave_de_original(ORG, PROY, FOTO, "jpg")
DERIVADO = clave_de_derivado(ORG, PROY, FOTO, "MINIATURA_320")


def _cliente():
    """El mismo constructor que usa la aplicación.

    Si la prueba armara su propio cliente, no comprobaría los ajustes que la
    aplicación aplica —firma v4, entre otros— y la URL firmada de producción
    podría salir distinta de la que aquí se da por buena.
    """
    return construir_cliente(
        region=REGION,
        access_key_id="prueba-sin-valor-real",
        secret_access_key="prueba-sin-valor-real",
    )


def _bucket(s3, nombre: str, *, con_bloqueo: bool, con_cors: bool = False) -> None:
    s3.create_bucket(
        Bucket=nombre,
        CreateBucketConfiguration={"LocationConstraint": REGION},
        **({"ObjectLockEnabledForBucket": True} if con_bloqueo else {}),
    )
    if con_cors:
        # Un bucket bien preparado permite que el navegador lea el objeto al
        # seguir el 302 de la API. Sin esto la rejilla sale vacía.
        s3.put_bucket_cors(
            Bucket=nombre,
            CORSConfiguration={
                "CORSRules": [
                    {
                        "AllowedMethods": ["GET"],
                        "AllowedOrigins": ["https://tdd.ejemplo.example"],
                        "AllowedHeaders": ["*"],
                    }
                ]
            },
        )


@pytest.fixture
def almacen():
    with mock_aws():
        s3 = _cliente()
        _bucket(s3, "tdd-objetos", con_bloqueo=True, con_cors=True)
        yield AlmacenS3(bucket="tdd-objetos", cliente=s3, dias_de_retencion=3650), s3


# ─────────────────────────────────────────────────────────────────────────────
#  El contrato del puerto
# ─────────────────────────────────────────────────────────────────────────────


def test_guarda_y_lee(almacen) -> None:
    a, _ = almacen
    a.guardar(ORIGINAL, b"los bytes de la foto")
    assert a.leer(ORIGINAL) == b"los bytes de la foto"
    assert a.existe(ORIGINAL) is True


def test_una_clave_que_no_existe_da_el_error_del_puerto(almacen) -> None:
    """Y no un `ClientError` de botocore: el resto de la aplicación no debe
    saber qué biblioteca hay debajo."""
    a, _ = almacen
    assert a.existe("no/existe.jpg") is False
    with pytest.raises(ObjetoNoEncontrado):
        a.leer("no/existe.jpg")


def test_un_derivado_se_sobrescribe_y_se_borra_sin_problema(almacen) -> None:
    """Un derivado se puede regenerar desde el original: no hay nada que
    proteger, y bloquearlo impediría rehacer una miniatura."""
    a, _ = almacen
    a.guardar(DERIVADO, b"miniatura")
    a.guardar(DERIVADO, b"miniatura rehecha")
    assert a.leer(DERIVADO) == b"miniatura rehecha"
    a.borrar(DERIVADO)
    assert a.existe(DERIVADO) is False


# ─────────────────────────────────────────────────────────────────────────────
#  Barrera 4 · el original no se sobrescribe ni se borra
# ─────────────────────────────────────────────────────────────────────────────


def test_el_adaptador_se_niega_a_sobrescribir_un_original(almacen) -> None:
    a, _ = almacen
    a.guardar(ORIGINAL, b"el original")
    with pytest.raises(OriginalInmutable):
        a.guardar(ORIGINAL, b"otro contenido")
    assert a.leer(ORIGINAL) == b"el original"


def test_el_adaptador_se_niega_a_borrar_un_original(almacen) -> None:
    a, _ = almacen
    a.guardar(ORIGINAL, b"el original")
    with pytest.raises(OriginalInmutable):
        a.borrar(ORIGINAL)
    assert a.existe(ORIGINAL) is True


def test_un_documento_y_una_plantilla_son_tan_originales_como_una_foto(almacen) -> None:
    """No hay versión «derivada» de un PDF del cliente que se pueda regenerar."""
    a, _ = almacen
    for clave in (
        f"{ORG}/{PROY}/documents/{uuid.uuid4()}.pdf",
        f"{ORG}/templates/{uuid.uuid4()}.pptx",
    ):
        a.guardar(clave, b"contenido")
        with pytest.raises(OriginalInmutable):
            a.guardar(clave, b"otro")
        with pytest.raises(OriginalInmutable):
            a.borrar(clave)


def test_el_original_sube_con_retencion_puesta(almacen) -> None:
    """`[REQ]` Es lo que hace que la garantía no dependa de este código.

    Si mañana alguien añade un `sobrescribir()` al adaptador, o entra por la
    consola de AWS, la retención del objeto sigue en pie.
    """
    a, s3 = almacen
    a.guardar(ORIGINAL, b"el original")
    cabecera = s3.head_object(Bucket="tdd-objetos", Key=ORIGINAL)
    assert cabecera["ObjectLockMode"] == "GOVERNANCE"
    assert cabecera["ObjectLockRetainUntilDate"] > datetime.now(UTC)


def test_un_derivado_no_se_retiene(almacen) -> None:
    """Retener las miniaturas llenaría el bucket de versiones de algo que se
    regenera en un segundo, y con Object Lock esas versiones no se pueden
    borrar hasta que venzan."""
    a, s3 = almacen
    a.guardar(DERIVADO, b"miniatura")
    assert "ObjectLockMode" not in s3.head_object(Bucket="tdd-objetos", Key=DERIVADO)


def test_saltarse_el_adaptador_no_destruye_los_bytes_del_original(almacen) -> None:
    """**La garantía de verdad.**

    Se escribe encima del original hablando con S3 directamente, como haría
    alguien desde la consola de AWS o un script suelto. S3 no lo impide —crear
    una versión nueva es una operación legítima—, pero el versionado conserva
    la anterior y la retención impide destruirla. Los bytes originales siguen
    ahí, que es lo que el cliente pidió.
    """
    a, s3 = almacen
    a.guardar(ORIGINAL, b"el original de la visita")

    s3.put_object(Bucket="tdd-objetos", Key=ORIGINAL, Body=b"encima")
    assert a.leer(ORIGINAL) == b"encima"  # la versión actual sí cambia

    versiones = s3.list_object_versions(Bucket="tdd-objetos", Prefix=ORIGINAL)["Versions"]
    assert len(versiones) == 2
    anterior = next(v for v in versiones if not v["IsLatest"])
    recuperado = s3.get_object(Bucket="tdd-objetos", Key=ORIGINAL, VersionId=anterior["VersionId"])[
        "Body"
    ].read()
    assert recuperado == b"el original de la visita"


def test_la_version_retenida_no_se_puede_borrar_ni_hablando_con_s3(almacen) -> None:
    """Es la propiedad del bucket, no del adaptador: por eso se comprueba
    saltándose el adaptador por completo."""
    from botocore.exceptions import ClientError

    a, s3 = almacen
    a.guardar(ORIGINAL, b"el original")
    version = s3.list_object_versions(Bucket="tdd-objetos", Prefix=ORIGINAL)["Versions"][0]

    with pytest.raises(ClientError) as exc:
        s3.delete_object(Bucket="tdd-objetos", Key=ORIGINAL, VersionId=version["VersionId"])
    assert exc.value.response["Error"]["Code"] == "AccessDenied"


# ─────────────────────────────────────────────────────────────────────────────
#  Modo de bloqueo
# ─────────────────────────────────────────────────────────────────────────────


def test_el_modo_por_defecto_es_governance_y_no_compliance() -> None:
    """`COMPLIANCE` impediría atender un derecho de supresión durante los años
    que dure la retención: cambiaría un riesgo técnico por uno legal. Quien
    despliega puede subirlo, sabiendo lo que acepta."""
    with mock_aws():
        s3 = _cliente()
        _bucket(s3, "tdd-modo", con_bloqueo=True)
        assert AlmacenS3(bucket="tdd-modo", cliente=s3).modo_de_bloqueo == "GOVERNANCE"


def test_se_puede_subir_a_compliance_a_proposito() -> None:
    with mock_aws():
        s3 = _cliente()
        _bucket(s3, "tdd-estricto", con_bloqueo=True)
        a = AlmacenS3(bucket="tdd-estricto", cliente=s3, modo_de_bloqueo="COMPLIANCE")
        a.guardar(ORIGINAL, b"x")
        assert s3.head_object(Bucket="tdd-estricto", Key=ORIGINAL)["ObjectLockMode"] == "COMPLIANCE"


def test_un_modo_inventado_se_rechaza_al_arrancar() -> None:
    """Y no al subir la primera foto: un almacén mal configurado tiene que
    impedir que la aplicación arranque, no fallar en producción."""
    with pytest.raises(ValueError, match="Modo de bloqueo"):
        AlmacenS3(bucket="b", cliente=object(), modo_de_bloqueo="ESTRICTO")


# ─────────────────────────────────────────────────────────────────────────────
#  Diagnóstico del bucket
# ─────────────────────────────────────────────────────────────────────────────


def test_comprobar_no_dice_nada_de_un_bucket_bien_creado(almacen) -> None:
    a, _ = almacen
    assert a.comprobar() == []


def test_comprobar_detecta_un_bucket_sin_object_lock() -> None:
    """Y explica lo que hace falta saber: no se puede arreglar sobre la
    marcha, hay que crear otro bucket y copiar."""
    with mock_aws():
        s3 = _cliente()
        _bucket(s3, "tdd-sin-worm", con_bloqueo=False)
        problemas = AlmacenS3(bucket="tdd-sin-worm", cliente=s3).comprobar()

    texto = " ".join(problemas)
    assert "versionado" in texto.lower()
    assert "Object Lock" in texto
    assert "AL CREAR" in texto


def test_comprobar_avisa_de_que_falta_el_cors() -> None:
    """No es integridad, pero rompe la aplicación en el navegador de la peor
    forma: la API redirige bien, S3 devuelve el objeto y el navegador se niega
    a entregarlo al JavaScript. La rejilla sale vacía sin un error en el log."""
    with mock_aws():
        s3 = _cliente()
        _bucket(s3, "tdd-sin-cors", con_bloqueo=True)
        problemas = AlmacenS3(bucket="tdd-sin-cors", cliente=s3).comprobar()

    assert len(problemas) == 1
    assert "CORS" in problemas[0]
    assert "navegador" in problemas[0]


def test_comprobar_dice_cuando_el_bucket_ni_existe() -> None:
    with mock_aws():
        problemas = AlmacenS3(bucket="tdd-inexistente", cliente=_cliente()).comprobar()
    assert len(problemas) == 1
    assert "tdd-inexistente" in problemas[0]


# ─────────────────────────────────────────────────────────────────────────────
#  URL firmada
# ─────────────────────────────────────────────────────────────────────────────


def test_la_url_firmada_apunta_al_objeto_y_caduca(almacen) -> None:
    a, _ = almacen
    a.guardar(ORIGINAL, b"x")
    url = a.url_firmada(ORIGINAL, segundos=300)
    assert ORIGINAL in url
    assert "X-Amz-Expires=300" in url
    assert "X-Amz-Signature=" in url


def test_el_almacen_en_disco_no_finge_saber_firmar() -> None:
    """El adaptador de desarrollo no implementa el puerto opcional. Devolver
    una cadena inútil sería peor: quien llame se enteraría en producción."""
    from tdd.evidence.storage import AlmacenEnDisco, AlmacenEnMemoria

    assert not hasattr(AlmacenEnMemoria(), "url_firmada")
    assert not hasattr(AlmacenEnDisco.__init__, "url_firmada")
