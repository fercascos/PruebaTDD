"""De una fila de texto a una lectura, o a una incidencia que se puede corregir.

Ninguna fila mala tumba la carga. Cada una produce su incidencia con **número
de fila, columna y valor**, porque el destinatario de este mensaje es quien
tiene el Excel abierto en la otra pantalla y necesita saber dónde tocar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from esg.indicadores.unidades import VECTORES
from esg.ingesta.lectura_tabular import texto_de
from esg.ingesta.mapeo import Mapeo

_FORMATOS_DE_FECHA = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d", "%d/%m/%y")

_VECTOR_ALIAS = {
    "agua": "AGUA",
    "water": "AGUA",
    "electricidad": "ELECTRICIDAD",
    "electricity": "ELECTRICIDAD",
    "luz": "ELECTRICIDAD",
    "energia electrica": "ELECTRICIDAD",
    "gas": "GAS",
    "gas natural": "GAS",
    "natural gas": "GAS",
    "residuos": "RESIDUOS",
    "residuo": "RESIDUOS",
    "waste": "RESIDUOS",
    "basura": "RESIDUOS",
}

_CALIDAD_ALIAS = {
    "medido": "MEDIDO",
    "real": "MEDIDO",
    "lectura real": "MEDIDO",
    "measured": "MEDIDO",
    "estimado": "ESTIMADO",
    "estimada": "ESTIMADO",
    "estimated": "ESTIMADO",
}


@dataclass(frozen=True, slots=True)
class Incidencia:
    fila: int | None
    columna: str | None
    codigo: str
    mensaje: str
    valor: str | None = None


@dataclass(frozen=True, slots=True)
class FilaDeConsumo:
    fila: int
    suministro: str
    vector: str
    inicio: date
    #: Ya **exclusiva**: si el fichero decía «hasta el 31/03», aquí es el 01/04.
    fin: date
    cantidad: Decimal
    unidad: str
    calidad: str = "MEDIDO"
    activo: str | None = None
    importe: Decimal | None = None
    moneda: str | None = None
    factor_gas: Decimal | None = None
    fraccion: str | None = None
    referencia: str | None = None


def analizar_numero(bruto: str) -> Decimal:
    """Números como los escribe la gente: `1.234,56`, `1,234.56`, `1234,5`.

    La regla es la del **último separador**: el que aparece más a la derecha es
    el decimal y el otro es de miles. Cubre los dos convenios sin preguntar de
    qué país viene el fichero, que es un dato que casi nunca se tiene.
    """
    texto = bruto.strip().replace(" ", "").replace(" ", "")
    if not texto:
        raise InvalidOperation(bruto)
    negativo = texto.startswith("-")
    texto = texto.lstrip("+-")
    ultimo_punto = texto.rfind(".")
    ultima_coma = texto.rfind(",")
    if ultimo_punto >= 0 and ultima_coma >= 0:
        if ultima_coma > ultimo_punto:
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif ultima_coma >= 0:
        # Una sola coma: decimal salvo que separe grupos de tres (1,234).
        entero, _, resto = texto.partition(",")
        texto = entero + resto if len(resto) == 3 and len(entero) <= 3 else texto.replace(",", ".")
    valor = Decimal(texto)
    return -valor if negativo else valor


def analizar_fecha(bruto: str) -> date:
    texto = bruto.strip()
    for formato in _FORMATOS_DE_FECHA:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    raise ValueError(bruto)


def analizar_fila(
    numero: int, fila: dict[str, Any], mapeo: Mapeo
) -> tuple[FilaDeConsumo | None, list[Incidencia]]:
    """Analiza una fila. Devuelve la lectura **o** sus incidencias, nunca las dos."""
    problemas: list[Incidencia] = []

    def crudo(campo: str) -> str:
        columna = mapeo.columna(campo)
        return texto_de(fila.get(columna)) if columna else ""

    def falta(campo: str, mensaje: str, valor: str | None = None) -> None:
        problemas.append(
            Incidencia(numero, mapeo.columna(campo), f"{campo}_invalido", mensaje, valor)
        )

    suministro = crudo("suministro")
    if not suministro:
        falta("suministro", "Falta el código de suministro (CUPS, contador o contrato)")

    vector_texto = crudo("vector")
    vector = mapeo.vector_por_defecto or ""
    if vector_texto:
        clave = " ".join(vector_texto.lower().split())
        vector = _VECTOR_ALIAS.get(clave, vector_texto.upper())
    if vector not in VECTORES:
        falta(
            "vector",
            f"Vector no reconocido. Se admiten: {', '.join(VECTORES)}",
            vector_texto or None,
        )

    fechas: dict[str, date] = {}
    for campo in ("inicio", "fin"):
        texto = crudo(campo)
        if not texto:
            falta(campo, f"Falta la fecha de {campo}")
            continue
        try:
            fechas[campo] = analizar_fecha(texto)
        except ValueError:
            falta(campo, "Fecha no reconocida (se admite aaaa-mm-dd o dd/mm/aaaa)", texto)

    cantidad: Decimal | None = None
    texto_cantidad = crudo("cantidad")
    if not texto_cantidad:
        falta("cantidad", "Falta la cantidad consumida")
    else:
        try:
            cantidad = analizar_numero(texto_cantidad)
        except (InvalidOperation, ArithmeticError):
            falta("cantidad", "No es un número", texto_cantidad)
        else:
            if cantidad < 0:
                # Un consumo negativo es una regularización, y se carga como
                # tal. Aceptarlo aquí lo mezclaría con el consumo del mes y
                # nadie volvería a saber cuál era cuál.
                falta(
                    "cantidad",
                    "Cantidad negativa: una regularización no se carga como consumo",
                    texto_cantidad,
                )

    unidad = crudo("unidad")
    if not unidad:
        falta("unidad", "Falta la unidad")

    if problemas:
        return None, problemas

    inicio, fin_bruto = fechas["inicio"], fechas["fin"]
    fin = fin_bruto + timedelta(days=1) if mapeo.fin_inclusivo else fin_bruto
    if fin <= inicio:
        return None, [
            Incidencia(
                numero,
                mapeo.columna("fin"),
                "periodo_invalido",
                "La fecha de fin no es posterior a la de inicio",
                fin_bruto.isoformat(),
            )
        ]

    calidad_texto = " ".join(crudo("calidad").lower().split())
    calidad = _CALIDAD_ALIAS.get(calidad_texto, "MEDIDO" if not calidad_texto else "")
    if not calidad:
        return None, [
            Incidencia(
                numero,
                mapeo.columna("calidad"),
                "calidad_invalida",
                "Calidad no reconocida: se admite «medido» o «estimado»",
                calidad_texto,
            )
        ]

    factor_gas: Decimal | None = None
    if crudo("factor_gas"):
        try:
            factor_gas = analizar_numero(crudo("factor_gas"))
        except (InvalidOperation, ArithmeticError):
            return None, [
                Incidencia(
                    numero,
                    mapeo.columna("factor_gas"),
                    "factor_gas_invalido",
                    "El poder calorífico no es un número",
                    crudo("factor_gas"),
                )
            ]

    importe: Decimal | None = None
    if crudo("importe"):
        try:
            importe = analizar_numero(crudo("importe"))
        except (InvalidOperation, ArithmeticError):
            # Un importe ilegible NO invalida la fila: el consumo es el dato, el
            # importe es acompañamiento. Se avisa y se sigue.
            problemas.append(
                Incidencia(
                    numero,
                    mapeo.columna("importe"),
                    "importe_ignorado",
                    "El importe no es un número: la fila se carga sin importe",
                    crudo("importe"),
                )
            )

    assert cantidad is not None
    return (
        FilaDeConsumo(
            fila=numero,
            suministro=suministro,
            vector=vector,
            inicio=inicio,
            fin=fin,
            cantidad=cantidad,
            unidad=unidad,
            calidad=calidad,
            activo=crudo("activo") or None,
            importe=importe,
            moneda=(crudo("moneda") or None),
            factor_gas=factor_gas,
            fraccion=(crudo("fraccion").upper() or None),
            referencia=(crudo("referencia") or None),
        ),
        problemas,
    )
