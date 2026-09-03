"""El lector del plan de autoprotección: lo que aporta son **limitaciones**.

Y es el primer extractor cuyo trabajo principal no es rellenar campos. Un plan
de autoprotección no trae superficies —eso está en la memoria técnica— ni un
CAPEX. Trae dos cosas que a una due diligence le importan mucho:

* **las limitaciones del informe**: lo que el propio documento dice sobre su
  fiabilidad, más lo que se deduce de su fecha y de sus huecos;
* y **el inventario de medios de protección contra incendios**, que es el
  capítulo 4 de la Norma Básica: hidrantes, rociadores, BIE, detección,
  exutorios, alumbrado de emergencia. Cada medio va con el sistema técnico del
  catálogo al que pertenece.

De los medios sale **presencia**, y cantidad solo cuando el plan la dice sin
ambigüedad. Ni activo ni periodicidad de mantenimiento: el activo lo elige quien
acepta —un plan cubre un complejo de seis naves—, y la periodicidad el plan la
declara en bloque («trimestrales, semestrales, anuales y quinquenales según el
tipo de equipo») **sin decir cuál le toca a cuál**.

## Por qué las reglas son éstas y no las de un documento concreto

Se leyó un resumen anonimizado de un plan real. Ese resumen trae una sección
titulada «Alertas, vacíos e inconsistencias» con las reservas ya redactadas, y
la tentación era obvia: buscar ese epígrafe y volcarlo.

No se ha hecho, porque **esa sección no es de un plan de autoprotección**. La
estructura de un PAU la fija el RD 393/2007 (Norma Básica de Autoprotección):
capítulos 1 a 9 y anexos. No hay capítulo 15. Esa sección la escribió quien
preparó el resumen —el propio documento se declara «resumen de trabajo» que «no
sustituye al Plan de Autoprotección completo»—, así que un extractor colgado de
ese epígrafe habría funcionado con **ese** PDF y con ninguno más, y lo habría
hecho pareciendo que funcionaba en general. Es exactamente el error que la
extracción de la memoria técnica ya declara: escrito contra un ejemplo.

Así que las reglas que se aplican son las que se sostienen sobre cualquier plan:

1. **El plazo de revisión.** El RD 393/2007 obliga a revisar el plan al menos
   cada tres años. Es aritmética de fechas, no interpretación.
2. **La fecha ausente.** Sin fecha no se puede comprobar lo anterior, y eso es
   una limitación por sí misma: «no consta» no es «está vigente».
3. **El documento que se declara no vigente.** Un puñado de fórmulas cerradas
   —«no sustituye al», «resumen de trabajo», «borrador», «sin visar»— que un
   redactor escribe cuando el documento no es el bueno.
4. **Las casillas vacías o anonimizadas** de los datos administrativos.

Y **si** el documento trae una sección de reservas, se recoge tal cual, marcada
como declarada por el documento y no deducida. Eso cubre el formato del resumen
sin fingir que es el estándar.

`[LIM]` Escrito contra **un** documento, y encima contra un resumen de uno. Lo
que puedo afirmar: sobre ése produce las limitaciones de abajo. Lo que no puedo
afirmar: que reconozca la portada de un plan completo de doscientas páginas con
sus planos. Hace falta uno de verdad para saberlo, y hasta entonces el extractor
avisa cuando no ha sabido encontrar la fecha en vez de callarse.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation

from tdd.extraccion.puerto import (
    Aportacion,
    EquipoPropuesto,
    LimitacionPropuesta,
    Procedencia,
    registrar,
)
from tdd.memoria.extraccion import normalizar

#: El `doc_type` que este extractor atiende.
TIPO = "PLAN_AUTOPROTECCION"

#: `[REQ]` RD 393/2007, Norma Básica de Autoprotección: el plan se revisa **al
#: menos cada tres años**. No es una recomendación de la aplicación, es el plazo
#: de la norma, y por eso está aquí con su fuente al lado y no escondido en una
#: comparación suelta.
ANOS_DE_VIGENCIA = 3

#: Fórmulas con las que un redactor dice que su documento no es el definitivo.
#: Cerradas y literales: una expresión que cace «borrador» en cualquier contexto
#: marcaría como no vigente un plan que menciona el borrador de otra cosa.
#:
#: Cada entrada es (patrón, cómo se cuenta en el informe).
_NO_VIGENTE: tuple[tuple[str, str], ...] = (
    (r"no sustituye al", "el documento declara que no sustituye al plan completo"),
    (r"resumen de trabajo", "el documento se declara resumen de trabajo"),
    (r"resumen ejecutivo del plan", "el documento es un resumen ejecutivo, no el plan"),
    (r"documento (?:en )?borrador", "el documento se declara borrador"),
    (r"pendiente de (?:visado|registro|aprobaci[oó]n)", "el documento está pendiente de trámite"),
    (r"copia sin valor", "el documento se declara copia sin valor"),
)

#: Cualquier línea que sea un epígrafe numerado: «15. Alertas, vacíos e
#: inconsistencias», «4. Capítulo 0: prólogo». Hace falta reconocerlos **todos**
#: y no solo los de reservas, porque es lo que marca dónde **acaba** una
#: sección. Sin eso, el cuerpo de la última sección se come el resto del
#: documento —medido: 112 limitaciones de un documento que tiene doce—.
_EPIGRAFE_NUMERADO = re.compile(r"^[ \t]*(\d{1,2})[.)][ \t]+(\S[^\n]{0,90})$", re.M)

#: Los epígrafes con los que un redactor —o quien resume— encabeza sus reservas.
_ES_RESERVA = re.compile(
    r"(alertas|vac[ií]os|inconsistencias|limitaciones|salvedades|reservas|observaciones)",
    re.I,
)

#: `[REQ]` Tope de reservas declaradas que se recogen de un documento.
#:
#: No es una preferencia estética. Un documento que produce cincuenta
#: limitaciones no tiene cincuenta limitaciones: significa que el corte por
#: epígrafes ha fallado y se está volcando prosa que no era una salvedad.
#: Volcarlas llenaría el informe de párrafos que nadie escribió como
#: limitación. Al pasarse, se recogen las primeras y **se avisa**, que es la
#: diferencia entre un tope y un truncamiento silencioso.
TOPE_DECLARADAS = 25

#: Ruido de maquetación que entra en el corte: el encabezado que se repite en
#: cada hoja y el pie de página.
_RUIDO = re.compile(r"^(?:resumen\s+anonimizado.*|p[áa]gina\s+\d+)$", re.I)

#: `[REQ]` Glifos que el PDF no sabe traducir a un carácter.
#:
#: `pdfminer` los devuelve como `(cid:127)` cuando la fuente incrustada no trae
#: la tabla que los mapea —es lo que pasa con las viñetas de muchos PDF—. Si no
#: se quitan, un texto que se recoge **literal** y va a un informe firmado
#: aparece con `(cid:127)` delante. Se quitan aquí y no en cada regla porque
#: afecta a todo lo que se lea del documento.
_GLIFO_SIN_MAPA = re.compile(r"\(cid:\d+\)")

#: Una fecha en cualquiera de las tres formas que se ven en una portada.
_FECHA_NUMERICA = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b")
_FECHA_LARGA = re.compile(
    r"\b(\d{1,2})\s+de\s+([a-zé]+)\s+de\s+(\d{4})\b",
    re.I,
)
_MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

#: Etiquetas administrativas cuya casilla vacía limita la trazabilidad. Salen del
#: capítulo 1 de la Norma Básica: titular, licencias, seguros y contacto.
_ADMINISTRATIVOS = (
    "licencia",
    "seguro",
    "poliza",
    "titular",
    "telefono",
    "correo",
    # `[CONTACTO]` es la etiqueta con la que se anonimiza un teléfono o un
    # correo, así que cuenta como dato administrativo aunque no lo diga.
    "contacto",
    "id_fiscal",
)

#: Un hueco: `[FECHA_DOCUMENTO]`, `[CONTACTO]`, o una casilla en blanco.
_HUECO = re.compile(r"\[[A-ZÁÉÍÓÚÑ_0-9]{3,40}\]")

# ─────────────────────────────────────────────────────────────────────────────
#  Los medios de autoprotección: el capítulo 4 de la Norma Básica `[REQ]`
# ─────────────────────────────────────────────────────────────────────────────

#: Los medios que se saben reconocer, con el sistema técnico al que van.
#:
#: `[REQ]` Es **una tabla de datos y no expresiones repartidas por el código**,
#: por la misma razón que el vocabulario de la memoria: el segundo plan que
#: llegue va a nombrarlos de otra forma, y corregirlo tiene que ser cambiar una
#: línea de aquí y no salir a buscar por dónde.
#:
#: El `sistema_code` sale de `data/catalogos/sistemas_tecnicos.csv`. Casi todo
#: es `PCI` porque es lo que enumera este capítulo; el alumbrado de emergencia
#: es `ELEC` y la videovigilancia `SEG`, y ésa es la razón de que el sistema no
#: se deduzca del epígrafe: un mismo epígrafe —«Control de humos y alumbrado»—
#: mezcla dos sistemas.
#:
#: `[LIM]` Cerrada a propósito. Un medio que no esté aquí **no se propone y se
#: declara** en los avisos: es como se descubre el que falta, y es lo que
#: separa «el plan no lo menciona» de «no lo supe leer».
MEDIOS: tuple[tuple[str, str, str], ...] = (
    # (expresión sobre el texto normalizado, sistema, cómo se llama el equipo)
    # `[REQ]` Ojo con el plural: `centrales?` significa «centrale» con una `s`
    # opcional, NO «central». Escrito así, la central de incendios no se
    # reconocía —y en este documento no se veía, porque venía en plural—. Lo
    # mismo le pasaba a rociador, extintor, detector y pulsador: solo cazaban el
    # plural. La forma correcta es `raíz(?:es)?`.
    (r"hidrantes?", "PCI", "Hidrante"),
    (r"rociador(?:es)?", "PCI", "Rociador automático"),
    (r"extintor(?:es)?", "PCI", "Extintor"),
    (r"\bbie\b|bocas? de incendio equipadas?", "PCI", "Boca de incendio equipada (BIE)"),
    (r"detector(?:es)?(?:\s+[oó]pticos?)?", "PCI", "Detector de incendios"),
    (r"pulsador(?:es)?(?:\s+manuales?)?", "PCI", "Pulsador manual de alarma"),
    (r"sirenas?", "PCI", "Sirena de alarma"),
    (r"central(?:es)?(?:\s+general(?:es)?)?\s+de\s+incendios?", "PCI", "Central de incendios"),
    (r"exutorios?", "PCI", "Exutorio de control de humos"),
    (r"dep[oó]sitos?(?:\s+a[eé]reos?)?", "PCI", "Depósito de agua contra incendios"),
    (r"grupos?\s+de\s+presi[oó]n", "PCI", "Grupo de presión contra incendios"),
    (r"puertas?\s+cortafuegos?", "PCI", "Puerta cortafuego"),
    (r"se[nñ]alizaci[oó]n\s+fotoluminiscente", "PCI", "Señalización fotoluminiscente"),
    (r"alumbrado(?:\s+aut[oó]nomo)?\s+de\s+emergencia", "ELEC", "Alumbrado de emergencia"),
    (r"\bcctv\b|c[aá]maras?\s+de\s+videovigilancia", "SEG", "Videovigilancia (CCTV)"),
)

#: El epígrafe del capítulo 4. Se localiza para **acotar dónde se buscan los
#: medios**: la palabra «extintor» aparece también en el capítulo 6, dentro de
#: un procedimiento de actuación —«utilizar el extintor más próximo»—, y ahí no
#: es un inventario, es una instrucción.
_CAPITULO_DE_MEDIOS = re.compile(
    r"cap[ií]tulo\s+4\b|medios\s+de\s+autoprotecci[oó]n|medios\s+(?:materiales|t[eé]cnicos)",
    re.I,
)

#: «Medios humanos» está DENTRO del capítulo 4 y no es un inventario de equipos:
#: es la estructura de personas —Jefe de Emergencia, equipos de intervención—.
#: Sin cortar aquí, «equipos de primera intervención» se propondría como equipo.
_FIN_DE_MEDIOS = re.compile(r"medios\s+humanos|cap[ií]tulo\s+5\b", re.I)

#: Los números que un plan escribe con letra. «Dieciséis hidrantes privados».
_CARDINALES_LARGOS = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11,
    "doce": 12, "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16,
    "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20,
}  # fmt: skip


def _fecha(texto: str) -> dt.date | None:
    """La fecha del plan, si se puede leer de las primeras líneas.

    Se busca **solo en la portada** —los primeros dos mil caracteres— a
    propósito. Un plan cita fechas por todas partes: la de un certificado de
    mantenimiento, la de una licencia, la de la norma. Tomar la primera que
    aparezca en el documento entero daría una fecha con aspecto de portada que
    no es la del plan, y sobre ella se calcularía una caducidad falsa.
    """
    portada = texto[:2000]
    if m := _FECHA_NUMERICA.search(portada):
        dia, mes, ano = (int(g) for g in m.groups())
        try:
            return dt.date(ano, mes, dia)
        except ValueError:
            return None
    if m := _FECHA_LARGA.search(portada):
        # Nombres propios y no los de arriba: el mes viene por su nombre y hay
        # que traducirlo antes de que sea un número.
        nombre_del_mes = normalizar(m.group(2))
        if (numero_de_mes := _MESES.get(nombre_del_mes)) is None:
            return None
        try:
            return dt.date(int(m.group(3)), numero_de_mes, int(m.group(1)))
        except ValueError:
            return None
    return None


def _reservas_declaradas(texto: str) -> tuple[list[tuple[str, str]], bool]:
    """Las reservas que el propio documento redacta, con su epígrafe.

    Devuelve `(reservas, se_ha_pasado_del_tope)`.

    Tres cosas que hay que hacer bien y que no son evidentes hasta que se prueba
    contra un documento de verdad:

    1. **El índice también trae el epígrafe.** «15. Alertas, vacíos e
       inconsistencias» aparece dos veces: en el sumario de la página 2 y como
       encabezado real ocho páginas después. Enganchar el primero y cortar hasta
       el siguiente epígrafe *de reservas* hace que el cuerpo abarque el
       documento entero. Medido antes de arreglarlo: **112 limitaciones** de un
       documento que tiene doce.
    2. **Una sección acaba en el epígrafe siguiente**, sea del tipo que sea. Por
       eso se localizan todos los epígrafes numerados y no solo los de reservas.
    3. **Un sumario se reconoce por su cuerpo**: si lo que hay debajo son casi
       todo epígrafes, es el índice y no la sección.
    """
    epigrafes = list(_EPIGRAFE_NUMERADO.finditer(texto))
    candidatos: list[tuple[str, str]] = []

    for n, actual in enumerate(epigrafes):
        titulo = " ".join(actual.group(2).split())
        if not _ES_RESERVA.search(titulo):
            continue
        fin = epigrafes[n + 1].start() if n + 1 < len(epigrafes) else len(texto)
        cuerpo = texto[actual.end() : fin]
        # Un sumario: debajo del epígrafe hay poco texto y lo que hay son otros
        # epígrafes. Se descarta sin mirar su contenido.
        if len(cuerpo.strip()) < 200:
            continue

        for trozo in re.split(r"\n\s*(?:[•·\-–*]|\d{1,2}[.)])\s*|\n{2,}", cuerpo):
            frase = " ".join(trozo.split())
            if _RUIDO.match(frase):
                continue
            # «Los siguientes puntos surgen del propio documento y deben
            # considerarse:» no es una salvedad, es lo que la introduce. Una
            # frase que acaba en dos puntos anuncia la lista, no la compone.
            if frase.endswith(":"):
                continue
            # Menos de cuarenta caracteres no es una salvedad: son restos de
            # maquetación. Más de mil significa que el corte por viñetas no ha
            # funcionado, y volcarla entera ensuciaría el informe.
            if 40 <= len(frase) <= 1000:
                candidatos.append((frase, titulo))

    return candidatos[:TOPE_DECLARADAS], len(candidatos) > TOPE_DECLARADAS


def _capitulo_de_medios(texto: str) -> str | None:
    """El trozo del documento donde están los medios, o `None`.

    `[REQ]` Acotar importa por los dos lados:

    * **Por delante**, porque «extintor» aparece también en el capítulo 6,
      dentro de un procedimiento de actuación —«utilizar el extintor más
      próximo»—, y ahí no es un inventario, es una instrucción.
    * **Por detrás**, porque «Medios humanos» está DENTRO del capítulo 4 y no
      son equipos: son el Jefe de Emergencia y los equipos de intervención. Sin
      ese corte, «equipos de primera intervención» entraría al inventario.

    `[REQ]` Y se coge **la ocurrencia con más cuerpo**, no la primera. El
    epígrafe del capítulo aparece dos veces: en el sumario y como encabezado
    real. Cogiendo la primera, el trozo era la línea del índice y salían **cero
    medios de un capítulo que enumera doce**. Es el mismo error que ya costó una
    medición con la sección de salvedades, y por eso aquí no se resuelve por
    numeración —un plan completo no numera sus capítulos como este resumen— sino
    por tamaño: una entrada de índice no tiene cuerpo.
    """
    mejor: str | None = None
    for inicio in _CAPITULO_DE_MEDIOS.finditer(texto):
        resto = texto[inicio.end() :]
        fin = _FIN_DE_MEDIOS.search(resto)
        trozo = resto[: fin.start()] if fin else resto
        if mejor is None or len(trozo) > len(mejor):
            mejor = trozo
    # Menos de doscientos caracteres es una entrada de índice, no un capítulo.
    if mejor is None or len(mejor.strip()) < 200:
        return None
    return mejor


def _cantidad_antes_de(plano: str, posicion: int) -> Decimal | None:
    """El número que precede al medio, si lo hay y si es suyo.

    Se mira **solo lo inmediatamente anterior**: «dieciséis hidrantes» sí;
    «un depósito aéreo de 529 m³ y a un grupo de presión con bomba eléctrica
    principal y dos bombas diésel» no puede atribuirle el 529 al grupo de
    presión. Una ventana amplia convertiría cualquier cifra cercana en una
    cantidad, y una cantidad equivocada en un inventario no se ve.
    """
    antes = plano[max(0, posicion - 24) : posicion]
    if (m := re.search(r"(\d[\d.]*)\s*$", antes)) is not None:
        try:
            return Decimal(m.group(1).replace(".", ""))
        except InvalidOperation:  # pragma: no cover - la expresión ya lo acota
            return None
    if (m := re.search(r"\b([a-z]+)\s*$", antes)) is not None and (
        valor := _CARDINALES_LARGOS.get(m.group(1))
    ) is not None:
        return Decimal(valor)
    return None


@dataclass(frozen=True, slots=True)
class PlanDeAutoproteccion:
    """Lee un plan de autoprotección. Determinista, sin IA y sin red."""

    nombre: str = "plan-autoproteccion-v1"
    soporta: tuple[str, ...] = (TIPO,)
    #: `[REQ]` **No es simulado**: las limitaciones salen del documento.
    es_simulada: bool = field(default=False)

    def leer(self, contenido: bytes, procedencia: Procedencia) -> Aportacion:
        import io

        from pdfminer.high_level import extract_text

        aportacion = Aportacion(
            doc_type=procedencia.doc_type,
            extractor=self.nombre,
            es_simulada=self.es_simulada,
        )

        try:
            texto = extract_text(io.BytesIO(contenido))
        except Exception as exc:  # noqa: BLE001 — un PDF roto no tumba la API
            aportacion.avisos.append(
                f"No se ha podido leer el documento ({type(exc).__name__}). Las "
                "limitaciones del plan hay que revisarlas a mano."
            )
            return aportacion

        # Antes de cualquier regla: un `(cid:127)` que sobreviva hasta aquí
        # acabaría copiado tal cual en el apartado de limitaciones del informe.
        texto = _GLIFO_SIN_MAPA.sub("", texto)

        if len(texto.strip()) < 200:
            aportacion.avisos.append(
                "El documento apenas tiene texto: probablemente sea un escaneado. "
                "Haría falta OCR, que no está construido."
            )
            return aportacion

        self._por_fecha(texto, aportacion, procedencia)
        self._por_declararse_no_vigente(texto, aportacion, procedencia)
        self._por_casillas_vacias(texto, aportacion, procedencia)
        self._declaradas(texto, aportacion, procedencia)
        self._medios(texto, aportacion, procedencia)
        return aportacion

    # ── Las reglas, una por método para que se lean sueltas ─────────────────

    def _por_fecha(self, texto: str, a: Aportacion, p: Procedencia) -> None:
        """`[REQ]` El plazo de revisión del RD 393/2007: tres años."""
        fecha = _fecha(texto)
        if fecha is None:
            a.limitaciones.append(
                LimitacionPropuesta(
                    texto=(
                        "No se ha podido leer la fecha del plan de autoprotección, así que "
                        "no puede comprobarse si está dentro del plazo de revisión de tres "
                        "años que exige el RD 393/2007. Hay que confirmarla en el documento."
                    ),
                    motivo="INCOMPLETO",
                    procedencia=replace(p, seccion="Portada"),
                )
            )
            return

        limite = fecha.replace(year=fecha.year + ANOS_DE_VIGENCIA)
        if limite < dt.date.today():
            a.limitaciones.append(
                LimitacionPropuesta(
                    texto=(
                        f"El plan de autoprotección está fechado el {fecha:%d/%m/%Y} y el "
                        f"RD 393/2007 obliga a revisarlo al menos cada {ANOS_DE_VIGENCIA} "
                        f"años: el plazo venció el {limite:%d/%m/%Y}. No consta revisión "
                        "posterior en el documento."
                    ),
                    motivo="CADUCADO",
                    # La fecha, literal y con su formato: es lo que hay que ir a
                    # comprobar a la portada.
                    procedencia=replace(
                        p, seccion="Portada", evidencia=f"Fecha del plan: {fecha:%d/%m/%Y}"
                    ),
                )
            )

    def _por_declararse_no_vigente(self, texto: str, a: Aportacion, p: Procedencia) -> None:
        plano = normalizar(texto)
        for patron, como_se_cuenta in _NO_VIGENTE:
            if (m := re.search(patron, plano)) is None:
                continue
            a.limitaciones.append(
                LimitacionPropuesta(
                    texto=(
                        f"El documento entregado no es el plan de autoprotección vigente: "
                        f"{como_se_cuenta}. Para la revisión hace falta el plan completo con "
                        "sus planos y anexos."
                    ),
                    motivo="NO_VIGENTE",
                    procedencia=replace(
                        p,
                        seccion="Portada",
                        evidencia="(texto normalizado) …"
                        + plano[max(0, m.start() - 70) : m.end() + 70].strip()
                        + "…",
                    ),
                )
            )
            # Una sola vez: dos fórmulas distintas de decir lo mismo no son dos
            # limitaciones, y en el informe saldrían como dos párrafos iguales.
            return

    def _por_casillas_vacias(self, texto: str, a: Aportacion, p: Procedencia) -> None:
        """Huecos en los datos administrativos del capítulo 1.

        `[REQ]` No se enumeran uno a uno: un plan anonimizado trae docenas de
        etiquetas y una limitación por cada una llenaría el informe de párrafos
        que dicen lo mismo. Se cuenta cuántas y se nombran las primeras.
        """
        plano = normalizar(texto)
        etiquetas = sorted(set(_HUECO.findall(texto)))
        administrativas = [
            e for e in etiquetas if any(clave in normalizar(e) for clave in _ADMINISTRATIVOS)
        ]
        if not etiquetas:
            return

        # Que el documento venga anonimizado es distinto de que le falten datos.
        # Se dice como lo que es, sin decidir cuál de las dos cosas es: quien
        # valida lo sabe y la aplicación no.
        muestra = ", ".join(etiquetas[:5])
        a.limitaciones.append(
            LimitacionPropuesta(
                texto=(
                    f"El plan trae {len(etiquetas)} datos sustituidos por etiquetas o sin "
                    f"rellenar ({muestra}"
                    + (", …" if len(etiquetas) > 5 else "")
                    + "). "
                    + (
                        "Entre ellos hay datos administrativos —licencias, seguros o "
                        "contactos—, así que la trazabilidad administrativa del "
                        "establecimiento no queda acreditada con este documento."
                        if administrativas
                        else "Hay que contrastarlos con el documento original."
                    )
                ),
                motivo="INCOMPLETO",
                procedencia=replace(p, seccion="Capítulo 1 · Titular y emplazamiento"),
            )
        )
        _ = plano  # la muestra sale del texto original, no del normalizado

    def _medios(self, texto: str, a: Aportacion, p: Procedencia) -> None:
        """`[REQ]` El capítulo 4: los medios de autoprotección, al inventario.

        Lo que sale de aquí es **presencia**, y cantidad solo cuando el plan la
        dice sin ambigüedad. «Dieciséis hidrantes privados» son dieciséis;
        «rociadores automáticos sobre la superficie industrial» son rociadores
        sin número, y proponer un 1 por omisión pondría un uno en un inventario
        que después alguien lee como cierto.

        `[REQ]` No se propone **periodicidad de mantenimiento**. El plan declara
        revisiones «trimestrales, semestrales, anuales y quinquenales según el
        tipo de equipo» y **no dice cuál le toca a cuál**. Repartirlas por
        analogía sería inventarse el plan de mantenimiento del edificio. La
        columna existe y la rellena una persona; aquí se avisa de que el plan
        habla de periodicidades para que nadie dé por hecho que ya están.
        """
        capitulo = _capitulo_de_medios(texto)
        if capitulo is None:
            a.avisos.append(
                "No se ha encontrado el capítulo de medios de autoprotección (capítulo 4 "
                "de la Norma Básica), así que no se ha propuesto ningún equipo. El "
                "inventario de protección contra incendios hay que hacerlo a mano."
            )
            return

        plano = normalizar(capitulo)
        vistos: set[str] = set()
        for patron, sistema, como_se_llama in MEDIOS:
            # `[REQ]` Todas las apariciones, no la primera. En este capítulo cada
            # medio sale dos veces: como subtítulo —«Hidrantes»— y en la frase
            # que lo describe —«Dieciséis hidrantes privados»—. La cantidad está
            # en la segunda, así que quedándose con la primera se perdía: el
            # inventario salía entero sin números.
            apariciones = list(re.finditer(patron, plano))
            if not apariciones or como_se_llama in vistos:
                continue
            vistos.add(como_se_llama)
            m = next(
                (a for a in apariciones if _cantidad_antes_de(plano, a.start()) is not None),
                apariciones[0],
            )
            # La frase de alrededor: es lo que va a las notas del equipo y lo
            # que permite comprobar de dónde salió.
            frase = " ".join(plano[max(0, m.start() - 90) : m.end() + 110].split())
            a.equipos.append(
                EquipoPropuesto(
                    sistema_code=sistema,
                    equipment_type=como_se_llama,
                    cantidad=_cantidad_antes_de(plano, m.start()),
                    descripcion=f"…{frase}…",
                    procedencia=replace(
                        p,
                        seccion="Capítulo 4 · Medios de autoprotección",
                        evidencia=f"(texto normalizado) …{frase}…",
                    ),
                )
            )

        if not a.equipos:
            a.avisos.append(
                "Se ha encontrado el capítulo de medios pero no se ha reconocido ninguno "
                "de los que la aplicación sabe leer. Puede que el plan los nombre de otra "
                "forma: el inventario hay que revisarlo a mano."
            )
            return

        sin_cantidad = sum(1 for e in a.equipos if e.cantidad is None)
        if sin_cantidad:
            a.avisos.append(
                f"{sin_cantidad} de los {len(a.equipos)} medios propuestos vienen SIN "
                "cantidad porque el plan no la dice. Se dejan sin número en vez de "
                "poner un 1: un uno en un inventario se lee después como cierto."
            )
        # `[PDV]` El RIPCI (RD 513/2017) fija periodicidades por tipo de equipo y
        # podría sembrar valores por omisión. No se hace: exigiría transcribir
        # una tabla reglamentaria que nadie de este proyecto ha validado, y un
        # plan de mantenimiento equivocado es peor que uno vacío.
        if re.search(r"trimestral|semestral|anual|quinquenal", plano or normalizar(texto)):
            a.avisos.append(
                "El plan declara periodicidades de revisión (trimestral, semestral, anual "
                "o quinquenal) pero NO dice cuál corresponde a cada equipo. La "
                "periodicidad de los equipos propuestos queda vacía: hay que ponerla."
            )

    def _declaradas(self, texto: str, a: Aportacion, p: Procedencia) -> None:
        """Las reservas que el propio documento redacta, tal cual.

        `[REQ]` No se reescriben. Están redactadas por quien conoce el edificio
        y el informe las va a citar: parafrasearlas cambiaría el alcance de una
        salvedad técnica por el de un resumen automático.

        `[LIM]` Un plan de autoprotección **no suele traer esta sección**: la
        Norma Básica fija capítulos 1 a 9 y anexos, y ninguno es «limitaciones».
        Se lee cuando está —los resúmenes de trabajo la traen— y no se cuenta
        con ella.
        """
        reservas, se_ha_pasado = _reservas_declaradas(texto)
        for frase, epigrafe in reservas:
            a.limitaciones.append(
                LimitacionPropuesta(
                    texto=frase,
                    motivo="DECLARADA",
                    # La evidencia es la propia frase: ya es literal del
                    # documento, así que repetirla en `evidencia` no añadiría
                    # nada. Lo que sí añade es el epígrafe del que salió.
                    procedencia=replace(p, seccion=epigrafe),
                )
            )
        if se_ha_pasado:
            a.avisos.append(
                f"El documento declara más de {TOPE_DECLARADAS} salvedades y solo se han "
                f"recogido las {TOPE_DECLARADAS} primeras. Un número así suele significar "
                "que se ha leído como salvedad prosa que no lo era: conviene revisar la "
                "sección en el documento antes de aceptar ninguna."
            )


registrar(PlanDeAutoproteccion())
