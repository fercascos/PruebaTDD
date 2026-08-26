"""Concurrencia optimista: `ETag` al leer, `If-Match` al escribir.

`[REQ]` El problema, con nombres: Marta abre un hallazgo, Luis abre el mismo
hallazgo, Marta corrige la descripción y guarda, Luis guarda su cambio de
riesgo treinta segundos después. Sin esto **la corrección de Marta desaparece
sin que nadie se entere**. Queda en `audit_log`, pero solo la encuentra quien
ya sospecha que pasó, y para sospecharlo hay que echar de menos algo que uno
mismo no escribió.

Cómo funciona, en dos frases: cada lectura devuelve `ETag: "<versión>"`, y cada
escritura manda esa misma versión en `If-Match`. Si la fila ya va por otra, la
escritura se rechaza **antes de tocar nada** y el mensaje dice quién la cambió
y cuándo, para que quien lo lee sepa con quién hablar en vez de quedarse con un
«conflicto» a secas.

**Dos niveles de exigencia, y la razón de que no sea uno solo:**

* En hallazgos y líneas de CAPEX la cabecera es **obligatoria** (`428` si
  falta). Son el trabajo que de verdad se edita a cuatro manos, y dejarla
  opcional ahí significaría que una pantalla nueva que se olvide de mandarla
  pierde la protección sin que nadie lo note.
* En el resto se **honra si viene** y se deja pasar si no. Las importaciones y
  los guiones de mantenimiento escriben sin haber leído antes, y exigirles una
  versión que no tienen los obligaría a una lectura previa que no elimina la
  carrera —entre la lectura y la escritura cabe otra petición— y solo añadiría
  ruido.

`[LIM]` Esto detecta escrituras simultáneas; **no reserva** el registro. Dos
personas pueden seguir abriendo el mismo hallazgo a la vez: lo que ya no puede
pasar es que la segunda pise a la primera en silencio. Un bloqueo real
—«Marta está editando esto»— necesita presencia en tiempo real, que la
aplicación no tiene y que es otra tarea.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, Request, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session


class VersionRequerida(HTTPException):
    """Falta `If-Match` en una ruta donde es obligatoria."""

    def __init__(self, que: str) -> None:
        super().__init__(
            status.HTTP_428_PRECONDITION_REQUIRED,
            f"Para modificar {que} hay que decir sobre qué versión se escribe. "
            "Envíe la cabecera If-Match con el ETag que devolvió la lectura.",
        )


class VersionCaducada(HTTPException):
    """La fila cambió desde que quien escribe la leyó."""

    def __init__(self, detalle: str) -> None:
        super().__init__(status.HTTP_412_PRECONDITION_FAILED, detalle)


def etiqueta(version: int | None) -> str:
    """El `ETag` de una versión.

    Comillas dobles y **sin `W/`**: `If-Match` exige comparación fuerte, y un
    ETag débil lo haría fallar en los clientes que siguen la norma.
    """
    return f'"{version if version is not None else 0}"'


def poner(respuesta: Response, version: int | None) -> None:
    """Sella la respuesta con la versión de la fila que lleva dentro."""
    respuesta.headers["ETag"] = etiqueta(version)


def _pedida(request: Request) -> str | None:
    """El valor de `If-Match`, normalizado, o `None` si no viene.

    Acepta `W/"3"` además de `"3"` aunque no debería llegar: rechazarlo por la
    `W` daría un 412 que parece un conflicto de edición sin serlo, y depurar
    eso desde la pantalla es un mal rato evitable.
    """
    crudo = request.headers.get("if-match")
    if crudo is None:
        return None
    valor = crudo.strip()
    if valor.startswith("W/"):
        valor = valor[2:]
    return valor.strip('"').strip()


def _quien_y_cuando(s: Session, tabla: str, fila_id: uuid.UUID) -> str:
    """«…lo cambió Marta el 26/08 a las 10:31» — o algo más vago si no consta.

    Sale de `updated_by`, que rellena el disparador. Cuando la fila la tocó una
    migración no hay autor, y entonces se dice eso en vez de inventarse uno.
    """
    fila = (
        s.execute(
            text(  # noqa: S608 — `tabla` no viene del usuario: es literal del código
                f"SELECT u.full_name, t.updated_by FROM {tabla} t "
                "LEFT JOIN app_user u ON u.id = t.updated_by WHERE t.id = :i"
            ),
            {"i": str(fila_id)},
        )
        .mappings()
        .first()
    )
    if fila is None or not fila["full_name"]:
        return "Alguien lo ha modificado"
    return f"{fila['full_name']} lo ha modificado"


def comprobar(
    request: Request,
    s: Session,
    *,
    tabla: str,
    fila_id: uuid.UUID,
    version_actual: int | None,
    que: str,
    obligatoria: bool = False,
) -> None:
    """Deja pasar la escritura, o la corta con `428` / `412`.

    `tabla` es un literal del código, nunca entrada del usuario: se usa para
    decir **quién** cambió la fila, y por eso viaja como nombre y no como
    consulta ya montada.
    """
    pedida = _pedida(request)

    if pedida is None:
        if obligatoria:
            raise VersionRequerida(que)
        return

    # `*` significa «existe», que ya se ha comprobado al leer la fila.
    if pedida == "*":
        return

    if pedida != str(version_actual):
        raise VersionCaducada(
            f"{_quien_y_cuando(s, tabla, fila_id)} desde que usted lo abrió. "
            "Sus cambios no se han guardado para no borrar los suyos: vuelva a "
            "cargar, compruebe qué ha cambiado y aplique lo que siga haciendo falta."
        )


def version_de(fila: Any) -> int | None:
    """La versión de una fila leída, venga como diccionario o como objeto."""
    if fila is None:
        return None
    if isinstance(fila, dict):
        return fila.get("row_version")
    return getattr(fila, "row_version", None)
