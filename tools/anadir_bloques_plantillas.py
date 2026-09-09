#!/usr/bin/env python3
"""Da sitio en la hoja `CapEx` a los bloques que la plantilla no traía.

Son **tres**, y llegaron en dos tandas:

1. **Operativos** e **Imprevistos**. Las dos plantillas los declaraban en «00
   Datos Categorías» pero la hoja `CapEx` no tenía ninguna fila donde
   escribirlos: solo había 20 bloques —15 de Hard Costs, Medioambiental, ESG y
   los 3 de Soft Costs—. Una actuación clasificada como Operativos no tenía
   sitio, e `Imprevistos` existía únicamente como un porcentaje suelto en «00
   Datos Activo»!C45.
2. **`SC.S04 «Otros»`**, la cuarta categoría de soft costs `[REQ]` P-45. La
   trajo el árbol del cliente y la hoja no la tenía: su total era
   `=J220+J232+J244`, la suma exacta de las otras tres. El cliente confirmó que
   **su plantilla puede cambiar**, así que se le da tramo propio en vez de
   escribirla en el de una vecina, donde habría sumado a un subtotal que no es
   el suyo sin que la hoja descuadrase.

**Se añaden al final, no se insertan.** Las filas 256 en adelante están vacías
en la plantilla original, así que los bloques van detrás de la última usada. Es
lo que hace esto viable: al no desplazarse ninguna fila existente, ninguna
fórmula, celda combinada, regla de formato condicional ni origen de tabla
dinámica cambia de sitio. Insertar en medio habría obligado a recalcular todo
eso a mano.

`[REC]` **El de soft costs va el primero de los tres**, justo detrás de la fila
254, que es donde acaba `S03`. No es cosmética: la hoja se lee de arriba abajo y
una cuarta categoría de soft costs colocada después de «IMPREVISTOS» se leería
como una sección aparte. Por eso **este programa reescribe los tres bloques
enteros cada vez** en vez de añadir el que falta: mover Operativos e Imprevistos
doce filas más abajo es regenerarlos en su sitio nuevo, no desplazar filas.

Cada bloque se **clona del medioambiental** —sección, subtotal y diez filas de
datos— para heredar sus estilos celda a celda, y luego se le cambia lo propio.
Las referencias de fila que apuntan dentro del bloque se desplazan; las que
apuntan fuera, como `$O$12`, no se tocan: es la diferencia entre un subtotal que
suma sus filas y uno que suma las del vecino. El bloque de soft costs se clona
**sin la fila de sección**, porque no es una sección: es una categoría más de
una que ya tiene la suya en la 219.

`Imprevistos` se monta como los soft costs, con su importe calculado a partir
del porcentaje de «00 Datos Activo»!C45, porque es como lo tenía pensado la
plantilla: un tanto por ciento de los hard costs, no una lista de actuaciones.

`[LIM]` **Los tres bloques quedan sin desplegable en la columna «Categoría».**
Las validaciones de la plantilla enumeran rangos concretos —`D221:D230`,
`D234:D242`— y ampliarlas es tocar una referencia relativa que aquí no se puede
comprobar abriendo Excel. No afecta a lo que exporta la aplicación, que escribe
la etiqueta directamente; afecta a quien rellene esas filas a mano. Conviene
saber además que **la propia plantilla del cliente ya tenía ese hueco** en
`D245:D254`, las diez filas de `S03`.

Uso:  python3 tools/anadir_bloques_plantillas.py [--check]
"""

from __future__ import annotations

import argparse
import copy
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLAS = RAIZ / "apps" / "api" / "src" / "tdd" / "exports" / "plantillas"
FICHEROS = ("capex_ddt_es.xltm", "capex_ddt_en.xltm")

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XML_ESPACIO = "{http://www.w3.org/XML/1998/namespace}space"
POS_CAPEX = 4

#: El bloque que se clona: sección, subtotal, diez filas de datos y la fila de
#: separación que va detrás, que trae el borde grueso de cierre.
MODELO_SECCION = 193
MODELO_SUBTOTAL = 194
MODELO_PRIMERA = 195
MODELO_ULTIMA = 204
MODELO_SEPARADOR = 205
FILAS_DE_DATOS = MODELO_ULTIMA - MODELO_PRIMERA + 1


@dataclass(frozen=True, slots=True)
class Bloque:
    """Un bloque nuevo, situado por su **primera fila en la hoja destino**."""

    fila: int
    #: Lo que va en la columna «Item» de sus filas de datos. Se hereda del
    #: modelo si no se pone, y el modelo es el medioambiental: sin esto las
    #: filas nuevas dirían «M».
    item: str
    #: Lo que va en la columna «Tipo de Coste».
    tipo_es: str
    tipo_en: str
    #: Título de la fila de sección. **Vacío significa que el bloque no lleva
    #: sección**: es una categoría más de un tipo de coste que ya tiene la suya.
    titulo_es: str = ""
    titulo_en: str = ""
    #: Lo que va en «Categoría». Vacío = lo elige el usuario del desplegable.
    categoria: str = ""
    #: Celda de «00 Datos Categorías» de la que sale el nombre de la categoría,
    #: para los bloques sin sección. La fila de subtotal la lee de ahí y las de
    #: datos la copian de la de subtotal, como hacen `S01` y `S02`.
    categoria_desde: str = ""
    #: Solo Imprevistos: se calcula como un % de los hard costs.
    porcentaje_desde: str = ""
    etiqueta_es: str = ""
    etiqueta_en: str = ""

    @property
    def con_seccion(self) -> bool:
        return bool(self.titulo_es)

    @property
    def subtotal(self) -> int:
        return self.fila + 1 if self.con_seccion else self.fila

    @property
    def primera(self) -> int:
        return self.subtotal + 1

    @property
    def ultima(self) -> int:
        return self.primera + FILAS_DE_DATOS - 1


#: `[REQ]` El orden es el de la hoja: soft costs pegado a los suyos, y detrás
#: los dos tipos de coste que no tenían tramo.
BLOQUES = (
    Bloque(
        fila=256,
        item="SC",
        tipo_es="Soft_Cost",
        tipo_en="Soft_Cost",
        categoria_desde="D7",
    ),
    Bloque(
        fila=268,
        titulo_es="OPERATIVOS",
        titulo_en="OPERATING",
        tipo_es="Operativos",
        tipo_en="Operating",
        item="OP",
        # Tres categorías —Consumos obra, Limpieza y Otros—, así que la celda se
        # deja en blanco: la escribe la aplicación al exportar y el desplegable
        # en cascada al rellenar a mano.
        categoria="",
    ),
    Bloque(
        fila=281,
        titulo_es="IMPREVISTOS",
        titulo_en="CONTINGENCIES",
        tipo_es="Imprevistos",
        tipo_en="Contingencies",
        item="IMP",
        categoria="General",
        porcentaje_desde="C45",
        etiqueta_es="Imprevistos",
        etiqueta_en="Contingencies",
    ),
)

#: Hoja de la que sale el nombre de la categoría, por idioma.
HOJA_CATEGORIAS = {False: "'00 Datos Categorías'", True: "'00 Category Data'"}

#: Fila del TOTAL general y las filas de sección que suma. Se **reescribe
#: entera** en vez de parchearla: al mover Operativos e Imprevistos, parchear
#: habría dejado dentro las referencias viejas y contado su importe dos veces.
FILA_TOTAL = 11
SECCIONES_DEL_TOTAL = (12, 193, 206, 219, 268, 281)
#: Fila del total de SOFT COSTS y los subtotales de las categorías que suma.
#: La cuarta es la que añade este programa.
FILA_SOFT_COSTS = 219
SUBTOTALES_SOFT_COSTS = (220, 232, 244, 256)

COLUMNAS_PLAZO = "JKLMN"
#: Las de plazo más la del total de la fila. La inglesa lleva las sumas también
#: en `O`; la española pone ahí un `SUM` de su propia fila, que no hay que tocar.
COLUMNAS_DE_IMPORTE = COLUMNAS_PLAZO + "O"

#: Última fila ocupada después de añadirlo todo, contando la de separación que
#: cierra el último bloque: es la convención de la plantilla, cuyo área de
#: impresión llegaba a la 255 y no a la 254. Área de impresión y origen de las
#: tablas dinámicas tienen que llegar hasta aquí.
ULTIMA_FILA = BLOQUES[-1].ultima + 1
#: Origen de la tabla dinámica que alimenta «Resumen CapEx» y sus gráficos. Se
#: quedaba en la 256 y dejaba fuera todo lo añadido: sin esto, el importe de
#: Operativos, Imprevistos y `SC.S04` cuadra en los totales y **no aparece en
#: los gráficos**. El número de fichero cambia entre idiomas, así que se busca
#: por el rango y no por el nombre.
ORIGEN_DINAMICAS_VIEJO = "C10:Q256"


def _q(t: str) -> str:
    return f"{{{NS}}}{t}"


def _ruta(zf: zipfile.ZipFile, posicion: int) -> str:
    libro = zf.read("xl/workbook.xml").decode("utf-8")
    rels = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    destinos = dict(re.findall(r'Id="([^"]+)"[^>]*Target="(worksheets/[^"]+)"', rels))
    hojas = re.findall(r'<sheet name="[^"]+"[^>]*r:id="([^"]+)"', libro)
    return "xl/" + destinos[hojas[posicion]]


def _columna(letras: str) -> int:
    n = 0
    for c in letras:
        n = n * 26 + (ord(c) - 64)
    return n


def _letras(n: int) -> str:
    salida = ""
    while n:
        n, resto = divmod(n - 1, 26)
        salida = chr(65 + resto) + salida
    return salida


REFERENCIA = re.compile(r"(\$?)([A-Z]{1,3})(\$?)(\d+)")


def _traducir(texto: str, origen: str, destino: str) -> str:
    """La fórmula escrita para `origen`, reescrita para `destino`.

    Es lo que hace Excel con una **fórmula compartida**: solo una celda del
    grupo guarda el texto y las demás lo derivan desplazando las referencias
    relativas y respetando las absolutas. Hace falta porque los bloques se
    clonan celda a celda: una celda copiada que siguiera diciendo «soy del grupo
    78» apuntaría a un maestro que ya no la incluye.
    """
    o = REFERENCIA.fullmatch(origen)
    d = REFERENCIA.fullmatch(destino)
    if o is None or d is None:  # pragma: no cover - referencias de la plantilla
        raise ValueError(f"referencia ilegible: {origen!r} → {destino!r}")
    dcol = _columna(d.group(2)) - _columna(o.group(2))
    dfila = int(d.group(4)) - int(o.group(4))

    def sustituir(m: re.Match[str]) -> str:
        fija_col, col, fija_fila, fila = m.groups()
        if not fija_col:
            col = _letras(_columna(col) + dcol)
        if not fija_fila:
            fila = str(int(fila) + dfila)
        return f"{fija_col}{col}{fija_fila}{fila}"

    return REFERENCIA.sub(sustituir, texto)


def _maestros(raiz: etree._Element) -> dict[str, tuple[str, str]]:
    """`si` del grupo → `(celda maestra, fórmula)`, de toda la hoja."""
    salida: dict[str, tuple[str, str]] = {}
    for celda in raiz.iter(_q("c")):
        f = celda.find(_q("f"))
        if f is None or f.get("t") != "shared" or not f.text:
            continue
        si = f.get("si")
        if si is not None:
            salida[si] = (celda.get("r") or "", f.text)
    return salida


def _desplazar(texto: str, delta: int, desde: int, hasta: int) -> str:
    """Suma `delta` a las filas de `texto` que caen dentro de `[desde, hasta]`.

    Las de fuera se dejan intactas: `$O$12` apunta al total de hard costs y
    tiene que seguir apuntando ahí desde el bloque nuevo.
    """

    def sustituir(m: re.Match[str]) -> str:
        fila = int(m.group(2))
        return f"{m.group(1)}{fila + delta}" if desde <= fila <= hasta else m.group(0)

    return re.sub(r"(\$?[A-Z]{1,3}\$?)(\d+)", sustituir, texto)


def _texto_en(celda: etree._Element, valor: str) -> None:
    for hijo in list(celda):
        celda.remove(hijo)
    celda.attrib.pop("t", None)
    if valor == "":
        return
    celda.set("t", "inlineStr")
    t = etree.SubElement(etree.SubElement(celda, _q("is")), _q("t"))
    t.text = valor
    t.set(XML_ESPACIO, "preserve")


def _formula(celda: etree._Element, valor: str) -> None:
    for hijo in list(celda):
        celda.remove(hijo)
    celda.attrib.pop("t", None)
    etree.SubElement(celda, _q("f")).text = valor


def _celdas(fila: etree._Element) -> dict[str, etree._Element]:
    return {re.sub(r"\d+", "", c.get("r") or ""): c for c in fila}


#: Una fórmula que es solo una cadena de referencias sumadas: `+J220+J232`. Son
#: las que reescribe `_rehacer_suma`; un `SUM(J11:N11)` no se toca, porque ya
#: cuenta lo que tiene que contar y cambiarlo sería tocar la hoja por gusto.
CADENA_DE_SUMANDOS = re.compile(r"\+?[A-Z]{1,3}\d+(?:\+[A-Z]{1,3}\d+)*")


def _rehacer_suma(fila: etree._Element, sumandos: tuple[int, ...]) -> None:
    """Deja las columnas de importe sumando exactamente esas filas.

    Se reescribe **el texto de la fórmula y nada más**. Las celdas que no lo
    llevan son las que derivan de una compartida: la plantilla inglesa tiene
    `J11` como maestra de `J11:O11`, y sustituir la fórmula por una suelta
    dejaba a `O11` apuntando a un grupo que ya no existía —la celda del TOTAL,
    vacía—. Cambiando solo el texto, las cinco derivadas siguen al maestro.
    """
    for col, celda in _celdas(fila).items():
        if col not in COLUMNAS_DE_IMPORTE:
            continue
        f = celda.find(_q("f"))
        if f is None or not f.text or not CADENA_DE_SUMANDOS.fullmatch(f.text):
            continue
        f.text = "".join(f"+{col}{n}" for n in sumandos)
        v = celda.find(_q("v"))
        if v is not None:
            celda.remove(v)


def anadir(bruto: bytes, bloques: tuple[Bloque, ...], *, ingles: bool) -> bytes:
    raiz = etree.fromstring(bruto)
    datos = raiz.find(_q("sheetData"))
    por_fila = {int(f.get("r")): f for f in datos.iterfind(_q("row"))}
    maestros = _maestros(raiz)

    for bloque in bloques:
        origen_desde = MODELO_SECCION if bloque.con_seccion else MODELO_SUBTOTAL
        # La fila de separación se clona también: al mover un bloque, la que
        # deja atrás tiene que volver a ser una separación y no media tabla.
        delta = bloque.fila - origen_desde
        nuevas: list[etree._Element] = []
        for origen in range(origen_desde, MODELO_SEPARADOR + 1):
            fila = copy.deepcopy(por_fila[origen])
            fila.set("r", str(origen + delta))
            for celda in fila:
                ref_original = celda.get("r")
                celda.set("r", _desplazar(ref_original, delta, origen_desde, MODELO_SEPARADOR))
                f = celda.find(_q("f"))
                if f is not None:
                    # Una fórmula compartida deja de serlo: la copia se lleva el
                    # texto ya escrito para su celda. Si se quedara diciendo «soy
                    # del grupo 78», apuntaría a un maestro cuyo rango declarado
                    # no la incluye, y ahí Excel deja de ser predecible.
                    texto = f.text
                    if not texto and f.get("t") == "shared":
                        origen_ref, plantilla = maestros[f.get("si")]
                        texto = _traducir(plantilla, origen_ref, ref_original)
                    if texto:
                        f.text = _desplazar(texto, delta, origen_desde, MODELO_SEPARADOR)
                    f.attrib.pop("t", None)
                    f.attrib.pop("si", None)
                    f.attrib.pop("ref", None)
                # El valor cacheado ya no vale: que Excel lo recalcule.
                v = celda.find(_q("v"))
                if v is not None and f is not None:
                    celda.remove(v)
            nuevas.append(fila)

        por_numero = {int(f.get("r")): f for f in nuevas}
        subtotal = por_numero[bloque.subtotal]
        if bloque.con_seccion:
            seccion = por_numero[bloque.fila]
            _texto_en(_celdas(seccion)["A"], bloque.titulo_en if ingles else bloque.titulo_es)
            # El subtotal del modelo dice «=+A193»; aquí apunta a su sección.
            _formula(_celdas(subtotal)["A"], f"+A{bloque.fila}")
        else:
            # Sin sección: el nombre sale de «00 Datos Categorías», igual que en
            # los otros tres bloques de soft costs. Si el cliente renombra ahí
            # su categoría, la hoja la sigue sin tocar este programa.
            hoja = HOJA_CATEGORIAS[ingles]
            _formula(_celdas(subtotal)["A"], f"+{hoja}!{bloque.categoria_desde}")

        for i in range(FILAS_DE_DATOS):
            n = bloque.primera + i
            celdas = _celdas(por_numero[n])
            _texto_en(celdas["A"], bloque.item)
            _texto_en(celdas["C"], bloque.tipo_en if ingles else bloque.tipo_es)
            if bloque.categoria_desde:
                _formula(celdas["D"], f"+$A${bloque.subtotal}")
            else:
                _texto_en(celdas["D"], bloque.categoria)
            if bloque.porcentaje_desde and i == 0:
                # `[REQ]` Manda «00 Datos Activo»: el porcentaje se lee de ahí y
                # no se escribe a mano, que es lo que decidió el cliente.
                hoja = "'00 Asset Data'" if ingles else "'00 Datos Activo'"
                _texto_en(celdas["G"], bloque.etiqueta_en if ingles else bloque.etiqueta_es)
                _formula(celdas["T"], f"+{hoja}!{bloque.porcentaje_desde}")
                _formula(celdas["U"], "+$O$12")
                for col in COLUMNAS_PLAZO:
                    _formula(celdas[col], f"+$T{n}*{col}$12")

        # Las filas de destino **ya existen** en el XML: están vacías pero con
        # su estilo y su alto. Se sustituyen en su sitio; añadirlas sin más
        # dejaría dos filas con el mismo número y Excel daría el fichero por
        # corrupto.
        for fila in nuevas:
            n = int(fila.get("r"))
            viejo = por_fila.get(n)
            if viejo is None:
                datos.append(fila)
            else:
                viejo.getparent().replace(viejo, fila)
            por_fila[n] = fila

    _rehacer_suma(por_fila[FILA_SOFT_COSTS], SUBTOTALES_SOFT_COSTS)
    _rehacer_suma(por_fila[FILA_TOTAL], SECCIONES_DEL_TOTAL)

    # Las filas tienen que ir en orden o Excel se queja del fichero.
    orden = sorted(datos.iterfind(_q("row")), key=lambda f: int(f.get("r")))
    for f in orden:
        datos.append(f)
    return etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True)


def _ampliar_area_de_impresion(libro: str, ultima: int) -> str:
    """El área de impresión acababa antes y dejaría fuera lo nuevo."""
    return re.sub(
        r"(<definedName name=\"_xlnm.Print_Area\" localSheetId=\"4\">CapEx!\$A\$9:\$Q\$)\d+",
        rf"\g<1>{ultima}",
        libro,
    )


def _ampliar_origen_de_dinamicas(cache: bytes, ultima: int) -> bytes:
    return cache.replace(
        f'ref="{ORIGEN_DINAMICAS_VIEJO}"'.encode(),
        f'ref="C10:Q{ultima}"'.encode(),
    )


def _puesto(por_fila: dict[int, etree._Element], bloque: Bloque) -> bool:
    """¿Está **este** bloque en su sitio?

    Se mira la columna «Item» de su última fila de datos, y no que la fila tenga
    contenido: las filas de destino existen desde el principio y, después de
    mover Operativos e Imprevistos, las de un bloque son las de otro. `SC` en la
    266 y `OP` en la 266 son dos hojas distintas.
    """
    fila = por_fila.get(bloque.ultima)
    if fila is None:
        return False
    celda = _celdas(fila).get("A")
    if celda is None:
        return False
    return "".join(celda.itertext()).strip() == bloque.item


def procesar(fichero: Path, *, comprobar: bool) -> bool:
    ingles = fichero.name.endswith("_en.xltm")
    with zipfile.ZipFile(fichero) as z:
        nombres = z.namelist()
        partes = {n: z.read(n) for n in nombres}
        ruta = _ruta(z, POS_CAPEX)

    raiz = etree.fromstring(partes[ruta])
    por_fila = {int(f.get("r")): f for f in raiz.find(_q("sheetData")).iterfind(_q("row"))}
    if all(_puesto(por_fila, b) for b in BLOQUES):
        return False
    if comprobar:
        return True

    partes[ruta] = anadir(partes[ruta], BLOQUES, ingles=ingles)
    partes["xl/workbook.xml"] = _ampliar_area_de_impresion(
        partes["xl/workbook.xml"].decode("utf-8"), ULTIMA_FILA
    ).encode("utf-8")
    for n in nombres:
        if "pivotCacheDefinition" in n:
            partes[n] = _ampliar_origen_de_dinamicas(partes[n], ULTIMA_FILA)

    with zipfile.ZipFile(fichero, "w", zipfile.ZIP_DEFLATED) as salida:
        for n in nombres:
            salida.writestr(n, partes[n])
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="no escribe; falla si faltan")
    args = ap.parse_args()

    pendientes = [f for f in FICHEROS if procesar(PLANTILLAS / f, comprobar=args.check)]
    if not pendientes:
        print("Las plantillas ya tienen los tres bloques en su sitio.")
        return 0
    for f in pendientes:
        if args.check:
            print(f"FALTAN LOS BLOQUES en {f}", file=sys.stderr)
        else:
            print(f"{f}: escritos los bloques de soft costs «Otros», Operativos e Imprevistos")
    return 1 if args.check else 0


if __name__ == "__main__":
    raise SystemExit(main())
