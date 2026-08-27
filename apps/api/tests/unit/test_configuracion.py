"""La configuración que impide arrancar mal.

`[REQ]` Las dos comprobaciones de aquí existen por el mismo motivo: hay ajustes
cuya ausencia **no rompe el arranque, rompe algo más tarde y en silencio**. Un
arranque que falla con un mensaje claro es infinitamente mejor que una
aplicación en pie que sirve fotografías que el navegador no puede leer.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tdd.core.config import Settings


def test_s3_sin_bucket_no_arranca() -> None:
    """Sin esto, la aplicación levantaría y fallaría en la primera subida, que
    es en una visita y sin cobertura para depurar."""
    with pytest.raises(ValidationError, match="STORAGE_BUCKET"):
        Settings(app_env="test", storage_backend="s3", storage_region="eu-west-1")


def test_s3_sin_region_no_arranca() -> None:
    """`[REQ]` La firma v4 **cubre la región**.

    Con la equivocada —o con la que botocore elija por su cuenta— subir puede
    funcionar, porque el cliente sigue la redirección de S3. Pero la URL firmada
    sale firmada para otra región y el navegador recibe un `403`: la rejilla de
    fotografías vuelve a salir vacía **y el servidor no registra ningún error**,
    porque desde su lado todo fue bien.

    Ese fallo exacto ya se pagó una vez por el extremo público, cuando la URL
    apuntaba a un nombre que el navegador no resolvía. No se paga dos veces.
    """
    with pytest.raises(ValidationError, match="STORAGE_REGION"):
        Settings(app_env="test", storage_backend="s3", storage_bucket="tdd-evidencia")


def test_con_bucket_y_region_arranca() -> None:
    ajustes = Settings(
        app_env="test",
        storage_backend="s3",
        storage_bucket="tdd-evidencia",
        storage_region="eu-west-1",
    )
    assert ajustes.storage_bucket == "tdd-evidencia"
    # Y el Object Lock viene puesto: apagarlo tiene que ser una decisión
    # explícita de alguien, no el valor por omisión.
    assert ajustes.storage_enable_object_lock is True
    assert ajustes.storage_object_lock_mode == "GOVERNANCE"


def test_el_adaptador_de_disco_no_exige_nada_de_eso() -> None:
    """En local no hay bucket ni región, y no debe haber que inventarlos."""
    ajustes = Settings(app_env="local")
    assert ajustes.storage_backend == "disco"
