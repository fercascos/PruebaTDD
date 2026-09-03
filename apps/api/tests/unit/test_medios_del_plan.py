"""`[REQ]` El capítulo 4 del plan de autoprotección, al inventario de equipo.

`[REQ]` No hay ningún plan de cliente en el repositorio. Aquí se fabrican textos
con la misma forma.

Lo que se fija es lo que hace que un inventario sacado de un documento sea
utilizable en una visita:

* que **el índice no se confunda con el capítulo** —el mismo error que ya costó
  una medición con las salvedades, y que aquí daba **cero medios**—;
* que la cantidad se lea **de la frase que la lleva** y no del subtítulo;
* que un medio **sin cantidad se quede sin cantidad**, en vez de valer uno;
* que «Medios humanos» **no entre**: son personas, no equipos;
* y que la periodicidad de mantenimiento **no se invente**.
"""

from __future__ import annotations

import io
from decimal import Decimal

from tdd.extraccion.plan_autoproteccion import (
    MEDIOS,
    PlanDeAutoproteccion,
    _cantidad_antes_de,
    _capitulo_de_medios,
)
from tdd.extraccion.puerto import Procedencia

#: Con la forma observada en un plan real: un índice al principio, el capítulo 4
#: con un subtítulo por medio, y «Medios humanos» al final del capítulo.
PLAN = """\
Plan de Autoprotección del complejo
Fecha: 01/06/2025

Índice

1. Capítulo 3: inventario y evaluación de riesgos

2. Capítulo 4: medios de autoprotección

3. Capítulo 5: mantenimiento

1. Capítulo 3: inventario y evaluación de riesgos

Se describen los riesgos internos y externos del establecimiento, así como los
ocupantes previstos y la carga de fuego estimada de cada zona del complejo.

2. Capítulo 4: medios de autoprotección

Abastecimiento de agua

Red de agua contra incendios conectada a un depósito aéreo de 529 m³ y a un
grupo de presión con bomba eléctrica principal y dos bombas diésel.

Hidrantes

Dieciséis hidrantes privados distribuidos por el perímetro del complejo.

Extinción automática

Rociadores automáticos sobre la superficie industrial de almacenamiento.

Detección y alarma

Central de incendios por nave, detectores ópticos, pulsadores manuales y sirenas.

Medios humanos

Estructura prevista: Director del Plan, Jefe de Emergencia, Equipo de Primera
Intervención y Equipo de Alarma y Evacuación, con apoyo técnico y de primeros
auxilios según la ocupación de cada nave.

3. Capítulo 5: mantenimiento

El plan contempla revisiones trimestrales, semestrales, anuales y quinquenales
según el tipo de equipo, con registro documental de cada operación realizada.
"""


def leer(texto: str = PLAN) -> list:
    a = PlanDeAutoproteccion().leer(_pdf(texto), Procedencia(doc_type="PLAN_AUTOPROTECCION"))
    return a.equipos


def tipos(texto: str = PLAN) -> set[str]:
    return {e.equipment_type for e in leer(texto)}


# ─────────────────────────────────────────────────────────────────────────────
#  Dónde se busca
# ─────────────────────────────────────────────────────────────────────────────


def test_el_indice_no_se_confunde_con_el_capitulo() -> None:
    """`[REQ]` El epígrafe del capítulo 4 aparece dos veces: en el sumario y
    como encabezado real. Cogiendo el primero, el trozo era una línea de índice
    y salían **cero medios de un capítulo que enumera doce**.

    Se resuelve por tamaño y no por numeración: un plan completo no numera sus
    capítulos como este resumen, pero una entrada de índice nunca tiene cuerpo.
    """
    capitulo = _capitulo_de_medios(PLAN)
    assert capitulo is not None
    assert "Dieciséis hidrantes" in capitulo
    assert len(capitulo) > 200


def test_los_medios_humanos_no_entran_al_inventario() -> None:
    """`[REQ]` «Equipo de Primera Intervención» es un equipo de personas. Sin
    cortar en «Medios humanos», entraría al inventario de equipo."""
    capitulo = _capitulo_de_medios(PLAN)
    assert capitulo is not None
    assert "Jefe de Emergencia" not in capitulo
    assert "Primera Intervención" not in capitulo


def test_un_documento_sin_capitulo_de_medios_lo_dice() -> None:
    """Y no propone nada. «No lo he encontrado» y «no había» son distintos."""
    a = PlanDeAutoproteccion().leer(
        _pdf("Plan de Autoprotección\nFecha: 01/06/2025\n" + ("relleno neutro " * 40)),
        Procedencia(doc_type="PLAN_AUTOPROTECCION"),
    )
    assert a.equipos == []
    assert any("no se ha encontrado el capítulo" in v.lower() for v in a.avisos)


# ─────────────────────────────────────────────────────────────────────────────
#  Las cantidades
# ─────────────────────────────────────────────────────────────────────────────


def test_la_cantidad_sale_de_la_frase_y_no_del_subtitulo() -> None:
    """`[REQ]` Cada medio aparece dos veces: como subtítulo —«Hidrantes»— y en
    la frase que lo describe —«Dieciséis hidrantes privados»—. La cantidad está
    en la segunda; quedándose con la primera, el inventario salía **entero sin
    números**."""
    hidrante = next(e for e in leer() if e.equipment_type == "Hidrante")
    assert hidrante.cantidad == Decimal("16")


def test_un_medio_sin_cantidad_se_queda_sin_cantidad() -> None:
    """`[REQ]` «Rociadores automáticos sobre la superficie de almacenamiento» no
    trae número. Poner un 1 por omisión metería un uno en un inventario que
    alguien va a leer después como cierto."""
    rociador = next(e for e in leer() if e.equipment_type == "Rociador automático")
    assert rociador.cantidad is None


def test_una_cifra_cercana_no_se_atribuye_al_medio_de_al_lado() -> None:
    """«un depósito aéreo de 529 m³ y a un grupo de presión» — el 529 es del
    depósito y en metros cúbicos, y el grupo de presión es uno."""
    equipos = {e.equipment_type: e.cantidad for e in leer()}
    assert equipos["Depósito de agua contra incendios"] == Decimal("1")
    assert equipos["Grupo de presión contra incendios"] == Decimal("1")


def test_los_cardinales_se_leen_hasta_veinte() -> None:
    assert _cantidad_antes_de("dieciseis hidrantes", len("dieciseis ")) == Decimal("16")
    assert _cantidad_antes_de("un deposito", len("un ")) == Decimal("1")
    assert _cantidad_antes_de("veinte extintores", len("veinte ")) == Decimal("20")
    # Lo que no es un número no lo es: «varios» no son tres.
    assert _cantidad_antes_de("varios extintores", len("varios ")) is None


def test_una_ventana_amplia_no_convierte_cualquier_cifra_en_cantidad() -> None:
    """Se mira solo lo inmediatamente anterior: una cifra a treinta caracteres
    de distancia es de otra frase."""
    lejos = "529 m3 de agua en el deposito general del complejo y rociadores"
    assert _cantidad_antes_de(lejos, lejos.index("rociadores")) is None


# ─────────────────────────────────────────────────────────────────────────────
#  Qué se reconoce
# ─────────────────────────────────────────────────────────────────────────────


def test_cada_medio_va_a_su_sistema_tecnico() -> None:
    """El sistema no se deduce del epígrafe: «Control de humos y alumbrado»
    mezcla dos sistemas distintos."""
    texto = PLAN.replace(
        "Central de incendios por nave, detectores ópticos, pulsadores manuales y sirenas.",
        "Central de incendios por nave. Alumbrado de emergencia autónomo y CCTV perimetral.",
    )
    por_sistema = {e.equipment_type: e.sistema_code for e in leer(texto)}
    assert por_sistema["Hidrante"] == "PCI"
    assert por_sistema["Alumbrado de emergencia"] == "ELEC"
    assert por_sistema["Videovigilancia (CCTV)"] == "SEG"


def test_el_singular_tambien_cuenta() -> None:
    """`[REQ]` `centrales?` significa «centrale» con una `s` opcional, NO
    «central». Escrito así, cinco medios solo se reconocían en plural, y en el
    documento con el que se escribió esto todos venían en plural: no se veía."""
    texto = PLAN.replace(
        "Central de incendios por nave, detectores ópticos, pulsadores manuales y sirenas.",
        "Una central de incendios en la garita, un detector óptico y un pulsador manual.",
    )
    reconocidos = tipos(texto)
    assert "Central de incendios" in reconocidos
    assert "Detector de incendios" in reconocidos
    assert "Pulsador manual de alarma" in reconocidos


def test_el_vocabulario_de_medios_no_tiene_el_fallo_del_plural() -> None:
    """La regla, sobre la tabla entera: una raíz acabada en consonante necesita
    `(?:es)?` y no `s?`. Es el fallo de arriba, comprobado de una vez."""
    import re

    for patron, _sistema, nombre in MEDIOS:
        assert not re.search(r"[bcdfglmnprstz]s\?", patron), (
            f"«{nombre}»: el patrón «{patron}» solo caza el plural. "
            "Una raíz acabada en consonante lleva `(?:es)?`."
        )


def test_lo_que_no_esta_en_el_vocabulario_se_dice() -> None:
    """`[LIM]` La tabla es cerrada. Un capítulo de medios donde no se reconoce
    ninguno se declara en vez de devolver una lista vacía y callar."""
    texto = PLAN.replace(
        "2. Capítulo 4: medios de autoprotección", "2. Capítulo 4: medios de autoprotección\n"
    )
    solo_raros = texto[: texto.index("Abastecimiento de agua")] + (
        "Se dispone de sistemas de proteccion pasiva mediante compartimentacion "
        "estructural y tratamientos ignifugos aplicados en obra sobre los elementos "
        "portantes principales de cada una de las naves del complejo logistico.\n"
        "\nMedios humanos\n\nDirector del Plan.\n"
    )
    a = PlanDeAutoproteccion().leer(_pdf(solo_raros), Procedencia(doc_type="PLAN_AUTOPROTECCION"))
    assert a.equipos == []
    assert any("no se ha reconocido ninguno" in v for v in a.avisos)


# ─────────────────────────────────────────────────────────────────────────────
#  El mantenimiento no se inventa
# ─────────────────────────────────────────────────────────────────────────────


def test_la_periodicidad_no_se_reparte_por_analogia() -> None:
    """`[REQ]` El plan declara revisiones «trimestrales, semestrales, anuales y
    quinquenales **según el tipo de equipo**» y no dice cuál le toca a cuál.
    Repartirlas sería inventarse el plan de mantenimiento del edificio.

    `[PDV]` El RIPCI (RD 513/2017) fija periodicidades por tipo y podría sembrar
    valores por omisión; no se hace porque exigiría transcribir una tabla
    reglamentaria que nadie de este proyecto ha validado.
    """
    a = PlanDeAutoproteccion().leer(_pdf(PLAN), Procedencia(doc_type="PLAN_AUTOPROTECCION"))
    # El puerto no tiene siquiera dónde ponerla: no se propone.
    assert not any(hasattr(e, "maintenance_months") for e in a.equipos)
    assert any("periodicidad de los equipos propuestos queda vacía" in v for v in a.avisos)


def test_se_avisa_de_cuantos_vienen_sin_cantidad() -> None:
    a = PlanDeAutoproteccion().leer(_pdf(PLAN), Procedencia(doc_type="PLAN_AUTOPROTECCION"))
    assert any("SIN cantidad" in v for v in a.avisos)


# ─────────────────────────────────────────────────────────────────────────────


def _pdf(texto: str) -> bytes:
    """Un PDF con ese texto. `[REQ]` Fabricado aquí, no hay ninguno de cliente."""
    from reportlab.lib.pagesizes import A4  # type: ignore[import-not-found]
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    cuerpo = getSampleStyleSheet()["BodyText"]
    doc.build([Paragraph(linea or "&nbsp;", cuerpo) for linea in texto.split("\n")])
    return buffer.getvalue()
