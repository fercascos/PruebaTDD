"""Comparador de referencias de precio `[REQ]` §14 de `docs/09-ux-pantallas.md`.

Este módulo existe bajo tres reglas que el cliente fijó por escrito, y las tres
se notan en el código:

**«No inventes APIs ni fuentes de precios.»** Aquí no hay ni una llamada a
ningún sitio. El comparador compara **lo que ya está registrado**: precios que
alguien tecleó, importó de un XLSX o sacó de un PDF adjunto, cada uno con su
procedencia. Ninguna función de este fichero abre una conexión.

**«Nunca selecciones automáticamente un precio como definitivo sin revisión
humana.»** `elegir_recomendada` no existe. Lo que hay es
`comprobar_validacion`, que **rechaza** un intento de validar sin las
condiciones puestas. La base de datos lo exige además con un `CHECK`, así que
ni saltándose esta capa se consigue.

**P-06 · No hay ninguna fuente externa habilitada.** Y lo que se enseña no es
una lista de resultados: es una lista de resultados **más las fuentes que no se
han consultado, con su motivo**. Una lista sin esa columna sugiere que se ha
buscado en todas partes.

Es lógica pura: ni base de datos ni HTTP. Se prueba sin levantar nada.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from tdd.core import idioma


class TipoDeFuente(StrEnum):
    MANUAL = "MANUAL"
    CATALOGO_INTERNO = "CATALOGO_INTERNO"
    BASE_PRECIOS_LICENCIADA = "BASE_PRECIOS_LICENCIADA"
    API_OFICIAL = "API_OFICIAL"
    CATALOGO_FABRICANTE = "CATALOGO_FABRICANTE"


class EstadoDelPrecio(StrEnum):
    SIN_PRECIO = "SIN_PRECIO"
    PENDIENTE_VALIDACION = "PENDIENTE_VALIDACION"
    VALIDADO = "VALIDADO"


class ValidacionRechazada(ValueError):
    """Faltan condiciones para dar un precio por bueno."""


@dataclass(frozen=True, slots=True)
class Fuente:
    code: str
    name: str
    source_type: TipoDeFuente
    is_enabled: bool
    tos_reviewed: bool
    disabled_reason: str | None = None
    license_expires_at: date | None = None
    tos_url: str | None = None


@dataclass(frozen=True, slots=True)
class Referencia:
    id: str
    source_code: str
    source_name: str
    description: str
    unit: str
    unit_price: Decimal
    currency: str
    price_date: date | None = None
    retrieved_at: datetime | None = None
    geo_scope: str | None = None
    includes_tax: bool | None = None
    includes_installation: bool | None = None
    scope_included: str | None = None
    scope_excluded: str | None = None
    provenance_note: str | None = None


@dataclass(frozen=True, slots=True)
class FuenteNoConsultada:
    """Una fuente que **no** se ha mirado, y por qué.

    `[REQ]` §14 · Es la columna que impide que la pantalla mienta por omisión.
    Sin ella, tres referencias parecen decir «esto es lo que hay en el mercado»
    cuando dicen «esto es lo que alguien introdujo».
    """

    code: str
    name: str
    motivo: str


#: Motivo por defecto cuando la fuente no está habilitada y nadie escribió uno.
#: Se redacta aquí y no en la pantalla para que diga lo mismo en el informe, en
#: la API y en la interfaz.
#:
#: Estas tres son la **clave** castellana, no el texto que sale: traducirlas
#: aquí las congelaría en el idioma del primer arranque, porque una constante
#: de módulo se evalúa una vez al importar. La traducción va en
#: `motivo_de_no_consulta`, que es donde se pinta.
MOTIVO_SIN_HABILITAR = (
    "Fuente no habilitada. No se ha realizado ninguna consulta automatizada a este proveedor."
)
MOTIVO_SIN_REVISAR = (
    "Pendiente de revisión de las condiciones de uso por un administrador. "
    "No se ha realizado ninguna consulta automatizada a este proveedor."
)
MOTIVO_LICENCIA_CADUCADA = (
    "La licencia registrada caducó el {fecha}. No se ha realizado ninguna "
    "consulta automatizada a este proveedor."
)


def motivo_de_no_consulta(fuente: Fuente, *, hoy: date) -> str | None:
    """Por qué no se ha consultado una fuente. `None` si sí se puede usar.

    Una fuente `MANUAL` nunca «se consulta»: es el consultor tecleando, así que
    no tiene sentido decir que no se ha llamado a nadie.
    """
    if fuente.source_type is TipoDeFuente.MANUAL:
        return None
    if not fuente.is_enabled:
        # `disabled_reason` lo escribe quien administra, en el idioma que
        # quiera: es un dato, y sale tal cual.
        return fuente.disabled_reason or idioma.traducir(MOTIVO_SIN_HABILITAR)
    if not fuente.tos_reviewed:
        # Redundante con el `CHECK` de la base, y a propósito: si un día alguien
        # relaja la restricción, la pantalla sigue diciendo la verdad.
        return idioma.traducir(MOTIVO_SIN_REVISAR)
    if fuente.license_expires_at is not None and fuente.license_expires_at < hoy:
        return idioma.traducir(
            MOTIVO_LICENCIA_CADUCADA, fecha=fuente.license_expires_at.isoformat()
        )
    return None


#: `[REQ]` Ninguna referencia viene marcada como elegida. Es una lista para que
#: decida una persona, no una recomendación.
AVISO_SIN_SELECCION = (
    "Ninguna referencia se selecciona automáticamente. Un consultor debe "
    "validar el precio que se aplique."
)


@dataclass(frozen=True, slots=True)
class Comparacion:
    referencias: list[Referencia]
    no_consultadas: list[FuenteNoConsultada]
    #: El aviso de arriba, ya traducido. **Sin valor por defecto a propósito**:
    #: un `aviso: str = AVISO_SIN_SELECCION` se evaluaría al importar el módulo
    #: y la primera petición que llegara fijaría el idioma de todas las demás.
    #: Sin defecto, quien construya una `Comparacion` sin traducirlo no compila.
    aviso: str


def comparar(referencias: list[Referencia], fuentes: list[Fuente], *, hoy: date) -> Comparacion:
    """Ordena lo que hay y enumera lo que no se ha mirado.

    Las referencias salen **de más reciente a más antigua** por fecha de precio.
    No es una recomendación: es el único orden que no sugiere preferencia por
    importe, que sería justo la insinuación que no se puede hacer.
    """
    ordenadas = sorted(
        referencias,
        key=lambda r: (r.price_date is None, -(r.price_date.toordinal() if r.price_date else 0)),
    )
    no_consultadas = []
    for fuente in fuentes:
        motivo = motivo_de_no_consulta(fuente, hoy=hoy)
        if motivo is not None:
            no_consultadas.append(
                FuenteNoConsultada(code=fuente.code, name=fuente.name, motivo=motivo)
            )
    return Comparacion(
        referencias=ordenadas,
        no_consultadas=no_consultadas,
        aviso=idioma.traducir(AVISO_SIN_SELECCION),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Actualización por índice
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ActualizacionPorIndice:
    base: Decimal
    indice_origen: Decimal
    indice_destino: Decimal
    factor_geografico: Decimal
    resultado: Decimal
    formula: str


def actualizar_por_indice(
    base: Decimal,
    *,
    indice_origen: Decimal,
    indice_destino: Decimal,
    factor_geografico: Decimal = Decimal("1"),
) -> ActualizacionPorIndice:
    """Traslada un precio de una fecha a otra con un índice.

    `[REQ]` P-06 · **Los dos valores del índice los introduce el usuario.** No
    hay catálogo de índices en el sistema y no se inventa ninguno: publicar una
    cifra del INE que nadie ha verificado sería exactamente inventar una fuente
    de precios. Esto es una calculadora, no un proveedor de datos.

    `[REQ]` Devuelve la fórmula escrita con sus operandos. Un número sin el
    cálculo detrás no se puede defender delante de un cliente, y el resultado
    **no se aplica solo**: quien llama decide.
    """
    if indice_origen <= 0:
        raise ValueError(idioma.traducir("El índice de origen debe ser mayor que cero"))
    if indice_destino <= 0:
        raise ValueError(idioma.traducir("El índice de destino debe ser mayor que cero"))
    if factor_geografico <= 0:
        raise ValueError(idioma.traducir("El factor geográfico debe ser mayor que cero"))

    resultado = (base * indice_destino / indice_origen * factor_geografico).quantize(
        Decimal("0.01")
    )
    formula = f"{base} × ({indice_destino} / {indice_origen}) × {factor_geografico} = {resultado}"
    return ActualizacionPorIndice(
        base=base,
        indice_origen=indice_origen,
        indice_destino=indice_destino,
        factor_geografico=factor_geografico,
        resultado=resultado,
        formula=formula,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Validación humana
# ─────────────────────────────────────────────────────────────────────────────

#: Longitud mínima de la justificación. Corta a propósito: lo que se busca es
#: que alguien escriba una frase, no un informe. «Oferta en firme de proveedor»
#: dice más que un párrafo de relleno.
MINIMO_JUSTIFICACION = 10


#: `[REQ]` Mensaje de un precio sin procedencia. Se redacta aquí para que la
#: API y la pantalla digan lo mismo, y porque explica **qué hacer**: no basta
#: con negarse.
SIN_PROCEDENCIA = (
    "Un precio conserva siempre su procedencia: elija una referencia. Si el "
    "importe no sale de ninguna de las registradas, dé de alta una referencia "
    "manual con su origen y valide contra ella."
)


def comprobar_validacion(
    *,
    importe: Decimal,
    referencia: Referencia | None,
    justificacion: str | None,
) -> str:
    """Comprueba que un precio se puede dar por validado. Devuelve la nota.

    **La referencia es obligatoria.** No es una decisión de esta capa: la base
    de datos lo exige con `precio_exige_referencia`, y si aquí se dejara pasar,
    el resultado sería un error de integridad en vez de un mensaje que explique
    qué falta. Un precio sin procedencia es el que nadie sabe defender seis
    meses después, cuando el cliente pregunta de dónde salió.

    `[REQ]` §14 · La justificación es **obligatoria cuando el importe difiere de
    la referencia elegida**. Cuando coincide, la nota es opcional y se redacta
    sola citando la fuente: exigir que alguien escriba «es el precio de la
    referencia» produce ruido, no trazabilidad.
    """
    texto = (justificacion or "").strip()

    if referencia is None:
        raise ValidacionRechazada(SIN_PROCEDENCIA)

    if importe != referencia.unit_price:
        if len(texto) < MINIMO_JUSTIFICACION:
            raise ValidacionRechazada(
                idioma.traducir(
                    "El importe ({importe}) no coincide con la referencia "
                    "({referencia}): explique por qué (mínimo {minimo} "
                    "caracteres).",
                    importe=importe,
                    referencia=referencia.unit_price,
                    minimo=MINIMO_JUSTIFICACION,
                )
            )
        return texto

    coincide = idioma.traducir(
        "Coincide con la referencia de {fuente}.", fuente=referencia.source_name
    )
    if not texto:
        return coincide
    if len(texto) < MINIMO_JUSTIFICACION:
        # La nota es opcional cuando el importe es el de la referencia, pero la
        # base de datos exige diez caracteres a cualquier precio validado
        # (`validado_exige_persona_y_nota`). Un «ok» tecleado de más no puede
        # tumbar la validación con un error de integridad, y tampoco se tira lo
        # que alguien escribió: se conserva y se le añade la procedencia.
        return f"{texto} — {coincide}"
    return texto


def a_decimal(valor: object, campo: str) -> Decimal:
    """Convierte a `Decimal` sin pasar por `float`.

    Pasar por `float` introduce error en el último céntimo, y estos números
    acaban sumados en la tabla de un informe que alguien firma.
    """
    try:
        return Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(
            idioma.traducir(
                "«{campo}» no es un número válido: {valor}", campo=campo, valor=repr(valor)
            )
        ) from exc
