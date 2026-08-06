"""Importación del inventario de equipo desde XLSX `[REQ]` §7 / P-15.

El equipo vive en Excel: el inventario de una nave con instalaciones llega en
una hoja que alguien rellenó durante la visita, no fila a fila en un formulario.
Esto lo lee.

Tres reglas que se notan en el código:

**Nada se aplica sin previsualizar.** El análisis no escribe. Devuelve fila a
fila qué va a pasar y por qué, y aplicar es otra llamada. Una importación que
mete 300 filas y luego dice «12 dieron error» obliga a limpiar a mano lo que ya
entró.

**Nada se sobrescribe solo.** Una fila cuya etiqueta ya existe en ese activo
sale marcada `YA_EXISTE` y **no se toca**. Actualizarla es una decisión
explícita del que importa, con su casilla. La ficha que hay en la base la
escribió alguien en una visita a la que no se vuelve.

**Lo que no se entiende se dice, no se adivina.** Un sistema técnico que no
casa con el catálogo no se aproxima al más parecido: la fila entra sin
clasificar y el aviso lo cuenta. Un activo que no existe en el encargo es un
error, no una invitación a crearlo.

El análisis es lógica pura: recibe listas de diccionarios y catálogos ya
leídos. Se prueba sin base de datos y sin ficheros.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum


def clave(texto: str | None) -> str:
    """Normaliza para comparar: sin tildes, sin espacios de más, en minúsculas.

    En un Excel rellenado a mano conviven «Climatización», «climatizacion» y
    «CLIMATIZACIÓN ». Las tres son lo mismo y rechazarlas por la tilde sería
    hacer perder el tiempo a quien importa.
    """
    if texto is None:
        return ""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", str(texto)) if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_tildes.split()).lower()


#: Cabeceras admitidas para cada campo. La primera es la que lleva la plantilla
#: que se descarga; las demás existen porque la hoja llega de fuera y nadie va a
#: escribir «equipment_type» en una columna.
CABECERAS: dict[str, tuple[str, ...]] = {
    "asset": ("activo", "edificio", "inmueble"),
    "tag": ("etiqueta", "tag", "codigo", "referencia"),
    "equipment_type": ("tipo de equipo", "tipo", "equipo", "descripcion"),
    "technical_system": ("sistema tecnico", "sistema", "instalacion"),
    "manufacturer": ("fabricante", "marca"),
    "model": ("modelo",),
    "serial_number": ("numero de serie", "n serie", "no de serie", "serie", "num serie"),
    "install_year": ("ano de instalacion", "ano instalacion", "ano", "instalado"),
    "expected_life_years": ("vida util esperada", "vida util", "vida util anos", "vida"),
    "condition": ("estado de conservacion", "estado", "conservacion"),
    "obsolescence": ("obsolescencia",),
    "criticality": ("criticidad",),
    "quantity": ("cantidad", "uds", "unidades"),
    "unit": ("unidad", "ud"),
    "has_documentation": ("documentacion", "hay documentacion", "tiene documentacion"),
    "notes": ("observaciones", "notas", "comentarios"),
}

OBLIGATORIAS = ("asset", "equipment_type")

#: Etiquetas de los enumerados, tal como se leen en la pantalla. Se admite
#: también el código de la base para que exportar e importar sea reversible.
ENUMERADOS: dict[str, dict[str, str]] = {
    "condition": {
        "bueno": "BUENO",
        "aceptable": "ACEPTABLE",
        "deficiente": "DEFICIENTE",
        "muy deficiente": "MUY_DEFICIENTE",
        "fuera de servicio": "FUERA_DE_SERVICIO",
    },
    "obsolescence": {
        "actual": "ACTUAL",
        "proximo a obsoleto": "PROXIMO_A_OBSOLETO",
        "obsoleto": "OBSOLETO",
        "sin repuestos": "SIN_REPUESTOS",
    },
    "criticality": {"alta": "ALTA", "media": "MEDIA", "baja": "BAJA"},
}

SI = {"si", "s", "true", "verdadero", "x", "1", "yes"}
NO = {"no", "n", "false", "falso", "0", ""}


class Estado(StrEnum):
    NUEVA = "NUEVA"
    #: Ya hay un equipo con esa etiqueta en ese activo. **No se toca** salvo
    #: que quien importa lo pida expresamente.
    YA_EXISTE = "YA_EXISTE"
    #: La etiqueta se repite dentro del propio fichero.
    DUPLICADA_EN_FICHERO = "DUPLICADA_EN_FICHERO"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class Activo:
    id: str
    name: str
    asset_code: str | None = None


@dataclass(frozen=True, slots=True)
class Sistema:
    id: str
    code: str
    name_es: str


@dataclass
class FilaAnalizada:
    #: Número de fila en la hoja, contando la cabecera. Es lo que el usuario ve
    #: en Excel: decir «fila 3» y que sea la 3 ahorra mucho tiempo.
    fila: int
    estado: Estado
    errores: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    #: Los valores ya convertidos, listos para insertar. Vacío si hay error.
    valores: dict[str, object] = field(default_factory=dict)
    #: Lo que se leyó, para poder enseñar la fila tal cual venía.
    crudo: dict[str, str] = field(default_factory=dict)
    #: Identificador del equipo existente, cuando `estado` es `YA_EXISTE`.
    existente_id: str | None = None


@dataclass
class Analisis:
    filas: list[FilaAnalizada]
    #: Cabeceras de la hoja que no se han reconocido. Se enumeran en vez de
    #: ignorarse en silencio: una columna «Nº serie» mal escrita perdería el
    #: dato sin que nadie se enterase hasta buscarlo meses después.
    columnas_ignoradas: list[str] = field(default_factory=list)
    columnas_ausentes: list[str] = field(default_factory=list)

    @property
    def nuevas(self) -> list[FilaAnalizada]:
        return [f for f in self.filas if f.estado is Estado.NUEVA]

    @property
    def ya_existen(self) -> list[FilaAnalizada]:
        return [f for f in self.filas if f.estado is Estado.YA_EXISTE]

    @property
    def con_error(self) -> list[FilaAnalizada]:
        return [f for f in self.filas if f.estado in (Estado.ERROR, Estado.DUPLICADA_EN_FICHERO)]

    def resumen(self) -> str:
        partes = [f"{len(self.nuevas)} equipos nuevos"]
        if self.ya_existen:
            partes.append(f"{len(self.ya_existen)} ya existentes (no se tocan)")
        if self.con_error:
            partes.append(f"{len(self.con_error)} con error")
        return " · ".join(partes)


def mapear_cabeceras(cabeceras: list[str]) -> tuple[dict[int, str], list[str], list[str]]:
    """Qué columna de la hoja es qué campo.

    Devuelve el mapa por índice, las cabeceras que no se han reconocido y los
    campos obligatorios que faltan. Las tres cosas se enseñan: importar contra
    una hoja de la que se ha ignorado media columna es peor que no importar.
    """
    por_alias = {clave(a): campo for campo, alias in CABECERAS.items() for a in alias}
    mapa: dict[int, str] = {}
    ignoradas: list[str] = []
    for i, cabecera in enumerate(cabeceras):
        campo = por_alias.get(clave(cabecera))
        if campo is None or campo in mapa.values():
            if str(cabecera or "").strip():
                ignoradas.append(str(cabecera).strip())
            continue
        mapa[i] = campo
    ausentes = [c for c in OBLIGATORIAS if c not in mapa.values()]
    return mapa, ignoradas, ausentes


def _entero(valor: str, campo: str, errores: list[str]) -> int | None:
    texto = (valor or "").strip()
    if not texto:
        return None
    try:
        # Excel devuelve «2010» pero también «2010.0» cuando la celda es
        # numérica: convertir directo a int reventaría en el segundo caso.
        return int(Decimal(texto))
    except (InvalidOperation, ValueError):
        errores.append(f"«{campo}»: «{texto}» no es un número entero")
        return None


def _analizar_fila(
    numero: int,
    crudo: dict[str, str],
    *,
    activos: list[Activo],
    sistemas: list[Sistema],
) -> FilaAnalizada:
    errores: list[str] = []
    avisos: list[str] = []
    valores: dict[str, object] = {}

    # ── Activo: obligatorio y tiene que existir ya en el encargo ─────────────
    # No se crea sobre la marcha. Un activo es una ficha con veinte campos y
    # una tipología que manda sobre las zonas; inventarlo a partir de un nombre
    # suelto de una celda produciría un edificio a medias que nadie sabría que
    # está a medias.
    texto_activo = (crudo.get("asset") or "").strip()
    if not texto_activo:
        errores.append("Falta el activo")
    else:
        buscado = clave(texto_activo)
        encontrado = next(
            (a for a in activos if clave(a.name) == buscado or clave(a.asset_code) == buscado),
            None,
        )
        if encontrado is None:
            errores.append(
                f"«{texto_activo}» no es un activo de este encargo. "
                f"Dé de alta el activo antes de importar su inventario."
            )
        else:
            valores["asset_id"] = encontrado.id

    tipo = (crudo.get("equipment_type") or "").strip()
    if not tipo:
        errores.append("Falta el tipo de equipo")
    else:
        valores["equipment_type"] = tipo[:120]

    etiqueta = (crudo.get("tag") or "").strip()
    valores["tag"] = etiqueta[:40] or None

    # ── Sistema técnico: opcional, y si no casa NO se aproxima ───────────────
    texto_sistema = (crudo.get("technical_system") or "").strip()
    valores["technical_system_id"] = None
    if texto_sistema:
        buscado = clave(texto_sistema)
        sistema = next(
            (s for s in sistemas if clave(s.name_es) == buscado or clave(s.code) == buscado), None
        )
        if sistema is None:
            avisos.append(
                f"«{texto_sistema}» no es ninguno de los 14 sistemas técnicos: "
                f"el equipo entra sin clasificar."
            )
        else:
            valores["technical_system_id"] = sistema.id

    for campo in ("manufacturer", "model", "serial_number"):
        texto = (crudo.get(campo) or "").strip()
        valores[campo] = texto[:120] or None
    valores["notes"] = (crudo.get("notes") or "").strip() or None

    # ── Vida útil: los dos datos o ninguno ───────────────────────────────────
    instalacion = _entero(crudo.get("install_year", ""), "Año de instalación", errores)
    vida = _entero(crudo.get("expected_life_years", ""), "Vida útil esperada", errores)
    if (instalacion is None) != (vida is None):
        errores.append(
            "El año de instalación y la vida útil esperada van juntos o no van: "
            "con solo uno de los dos no hay vida residual que calcular."
        )
    if instalacion is not None and not (1800 <= instalacion <= 2200):
        errores.append(f"El año de instalación ({instalacion}) está fuera de rango")
    if vida is not None and not (0 < vida <= 200):
        errores.append(f"La vida útil esperada ({vida}) está fuera de rango")
    valores["install_year"] = instalacion
    valores["expected_life_years"] = vida

    # ── Enumerados ───────────────────────────────────────────────────────────
    for campo, tabla in ENUMERADOS.items():
        texto = (crudo.get(campo) or "").strip()
        if not texto:
            valores[campo] = None
            continue
        # Se admite la etiqueta de pantalla («Muy deficiente») y el código de
        # la base («MUY_DEFICIENTE»), para que exportar e importar sea reversible.
        codigo = tabla.get(clave(texto))
        if codigo is None and texto.upper() in set(tabla.values()):
            codigo = texto.upper()
        if codigo is None:
            avisos.append(
                f"«{campo}»: «{texto}» no es un valor conocido "
                f"({', '.join(sorted(tabla))}). Se deja sin valorar."
            )
            valores[campo] = None
        else:
            valores[campo] = codigo

    # ── Cantidad, unidad y documentación ─────────────────────────────────────
    texto_cantidad = (crudo.get("quantity") or "").strip()
    if texto_cantidad:
        try:
            cantidad = Decimal(texto_cantidad.replace(",", "."))
        except InvalidOperation:
            errores.append(f"«Cantidad»: «{texto_cantidad}» no es un número")
            cantidad = Decimal("1")
        if cantidad <= 0:
            errores.append("La cantidad debe ser mayor que cero")
            cantidad = Decimal("1")
    else:
        cantidad = Decimal("1")
    valores["quantity"] = cantidad
    valores["unit"] = ((crudo.get("unit") or "").strip() or "ud")[:20]

    texto_doc = clave(crudo.get("has_documentation"))
    if texto_doc in SI:
        valores["has_documentation"] = True
    elif texto_doc in NO:
        valores["has_documentation"] = False
    else:
        avisos.append(f"«Documentación»: «{texto_doc}» no se entiende. Se toma como «no».")
        valores["has_documentation"] = False

    estado = Estado.ERROR if errores else Estado.NUEVA
    return FilaAnalizada(
        fila=numero,
        estado=estado,
        errores=errores,
        avisos=avisos,
        valores={} if errores else valores,
        crudo=crudo,
    )


def analizar(
    cabeceras: list[str],
    filas: list[list[str]],
    *,
    activos: list[Activo],
    sistemas: list[Sistema],
    etiquetas_existentes: dict[tuple[str, str], str],
) -> Analisis:
    """Analiza la hoja entera **sin escribir nada**.

    `etiquetas_existentes` mapea `(asset_id, etiqueta_normalizada)` al `id` del
    equipo que ya está en la base. Se pasa desde fuera para que esta función no
    toque la base de datos y se pueda probar sin levantar nada.
    """
    mapa, ignoradas, ausentes = mapear_cabeceras(cabeceras)
    if ausentes:
        # Sin activo o sin tipo de equipo no hay nada que importar: se devuelve
        # el diagnóstico y ni se recorren las filas, para no enterrar el
        # problema real bajo trescientos errores idénticos.
        legibles = {"asset": "Activo", "equipment_type": "Tipo de equipo"}
        return Analisis(
            filas=[],
            columnas_ignoradas=ignoradas,
            columnas_ausentes=[legibles.get(c, c) for c in ausentes],
        )

    analizadas: list[FilaAnalizada] = []
    vistas: dict[tuple[str, str], int] = {}

    for i, celdas in enumerate(filas):
        crudo = {campo: (celdas[j] if j < len(celdas) else "") for j, campo in mapa.items()}
        if not any((v or "").strip() for v in crudo.values()):
            continue  # Fila en blanco: en una hoja real hay decenas al final.

        numero = i + 2  # +1 por la cabecera, +1 porque Excel empieza en 1
        fila = _analizar_fila(numero, crudo, activos=activos, sistemas=sistemas)

        # La etiqueta identifica al equipo DENTRO del activo, así que el choque
        # se busca por la pareja. Dos edificios pueden tener los dos su «CL-01»
        # y no es un duplicado.
        etiqueta = fila.valores.get("tag") if fila.estado is Estado.NUEVA else None
        activo_id = fila.valores.get("asset_id") if fila.estado is Estado.NUEVA else None
        if etiqueta and activo_id:
            llave = (str(activo_id), clave(str(etiqueta)))
            if llave in vistas:
                fila.estado = Estado.DUPLICADA_EN_FICHERO
                fila.errores.append(
                    f"La etiqueta «{etiqueta}» ya aparece en la fila {vistas[llave]} "
                    f"para el mismo activo."
                )
                fila.valores = {}
            elif llave in etiquetas_existentes:
                fila.estado = Estado.YA_EXISTE
                fila.existente_id = etiquetas_existentes[llave]
                fila.avisos.append(
                    f"Ya hay un equipo con la etiqueta «{etiqueta}» en ese activo. "
                    f"No se toca salvo que pida actualizar los existentes."
                )
                vistas[llave] = numero
            else:
                vistas[llave] = numero

        analizadas.append(fila)

    return Analisis(filas=analizadas, columnas_ignoradas=ignoradas)
