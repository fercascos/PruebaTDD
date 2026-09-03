"""`[REQ]` Lo que un documento dice sobre su propia fiabilidad.

`[REQ]` No hay ningún plan de autoprotección de cliente en el repositorio, ni lo
habrá: el documento contra el que se escribió esto es confidencial. Aquí se
fabrican textos con la misma forma.

Lo que se fija no es que el extractor «funcione», sino las cuatro cosas de las
que depende que una limitación puesta en un informe firmado sea defendible:

* que **el plazo del RD 393/2007** se calcule y no se adivine;
* que **una fecha que no se lee no se invente**, y que eso sea la limitación;
* que **el índice no se confunda con la sección** —el fallo que produjo 112
  limitaciones de un documento que tenía doce—;
* y que un motivo inventado **no se pueda guardar**.
"""

from __future__ import annotations

import datetime as dt

import pytest

from tdd.extraccion.plan_autoproteccion import (
    TOPE_DECLARADAS,
    PlanDeAutoproteccion,
    _fecha,
    _reservas_declaradas,
)
from tdd.extraccion.puerto import LimitacionPropuesta, Procedencia

# ─────────────────────────────────────────────────────────────────────────────
#  El motivo no se inventa
# ─────────────────────────────────────────────────────────────────────────────


def test_un_motivo_que_no_esta_en_la_lista_no_se_puede_construir() -> None:
    """`[REQ]` Un motivo nuevo quedaría fuera de los recuentos del informe sin
    que nadie se entere. Se rechaza al construirlo, no al guardarlo."""
    with pytest.raises(ValueError, match="no es un motivo"):
        LimitacionPropuesta(texto="algo", motivo="GRAVE")


def test_los_motivos_de_la_lista_si() -> None:
    for motivo in ("CADUCADO", "INCOMPLETO", "NO_VIGENTE", "DECLARADA", "INCONSISTENTE"):
        assert LimitacionPropuesta(texto="algo", motivo=motivo).motivo == motivo


# ─────────────────────────────────────────────────────────────────────────────
#  La fecha, y el plazo de la norma
# ─────────────────────────────────────────────────────────────────────────────


def test_la_fecha_se_lee_en_sus_tres_formas() -> None:
    assert _fecha("Plan de Autoprotección\nFecha: 14/03/2019\n") == dt.date(2019, 3, 14)
    assert _fecha("Fecha del documento: 2-9-2021") == dt.date(2021, 9, 2)
    assert _fecha("Madrid, a 7 de octubre de 2020") == dt.date(2020, 10, 7)


def test_una_fecha_imposible_no_se_fuerza() -> None:
    """El 31 de febrero no es una fecha. Devolver algo parecido sería peor que
    no devolver nada: sobre ello se calcularía una caducidad."""
    assert _fecha("Fecha: 31/02/2020") is None
    assert _fecha("Fecha: 12 de brumario de 2020") is None


def test_solo_se_mira_la_portada() -> None:
    """`[REQ]` Un plan cita fechas por todas partes: la de un certificado de
    mantenimiento, la de una licencia, la de la norma. Tomar la primera del
    documento entero daría una fecha con aspecto de portada que no lo es, y la
    caducidad se calcularía sobre ella."""
    texto = "Plan de Autoprotección\n" + ("relleno " * 400) + "\nFecha: 01/01/1999\n"
    assert _fecha(texto) is None


def test_un_plan_de_hace_mas_de_tres_anos_esta_fuera_de_plazo() -> None:
    """`[REQ]` RD 393/2007: el plan se revisa al menos cada tres años."""
    viejo = dt.date.today().replace(year=dt.date.today().year - 5)
    a = PlanDeAutoproteccion().leer(
        _pdf_falso(f"Plan de Autoprotección\nFecha: {viejo:%d/%m/%Y}\n"),
        Procedencia(doc_type="PLAN_AUTOPROTECCION"),
    )
    caducado = [lim for lim in a.limitaciones if lim.motivo == "CADUCADO"]
    assert len(caducado) == 1
    assert "RD 393/2007" in caducado[0].texto
    procedencia = caducado[0].procedencia
    assert procedencia is not None
    assert f"{viejo:%d/%m/%Y}" in (procedencia.evidencia or "")


def test_un_plan_reciente_no_se_marca_caducado() -> None:
    hace_un_ano = dt.date.today().replace(year=dt.date.today().year - 1)
    a = PlanDeAutoproteccion().leer(
        _pdf_falso(f"Plan de Autoprotección\nFecha: {hace_un_ano:%d/%m/%Y}\n"),
        Procedencia(doc_type="PLAN_AUTOPROTECCION"),
    )
    assert [lim for lim in a.limitaciones if lim.motivo == "CADUCADO"] == []


def test_sin_fecha_la_limitacion_es_que_no_se_puede_comprobar() -> None:
    """`[REQ]` «No consta» no es «está vigente». Y no se inventa una fecha para
    poder calcular: se dice que no se ha podido leer."""
    a = PlanDeAutoproteccion().leer(
        _pdf_falso("Plan de Autoprotección del complejo\nSin fecha en la portada.\n"),
        Procedencia(doc_type="PLAN_AUTOPROTECCION"),
    )
    incompletas = [lim for lim in a.limitaciones if lim.motivo == "INCOMPLETO"]
    assert any("no puede comprobarse" in lim.texto for lim in incompletas)
    assert [lim for lim in a.limitaciones if lim.motivo == "CADUCADO"] == []


# ─────────────────────────────────────────────────────────────────────────────
#  El documento que se declara no vigente
# ─────────────────────────────────────────────────────────────────────────────


def test_un_documento_que_dice_no_sustituir_al_plan_se_marca() -> None:
    a = PlanDeAutoproteccion().leer(
        _pdf_falso(
            "Resumen del Plan de Autoprotección\nFecha: 01/06/2025\n"
            "Advertencia: este documento no sustituye al Plan de Autoprotección completo, "
            "a sus planos ni a sus anexos.\n"
        ),
        Procedencia(doc_type="PLAN_AUTOPROTECCION"),
    )
    no_vigentes = [lim for lim in a.limitaciones if lim.motivo == "NO_VIGENTE"]
    assert len(no_vigentes) == 1
    assert "no es el plan de autoprotección vigente" in no_vigentes[0].texto


def test_dos_formas_de_decir_lo_mismo_no_son_dos_limitaciones() -> None:
    """En el informe saldrían como dos párrafos que dicen lo mismo."""
    a = PlanDeAutoproteccion().leer(
        _pdf_falso(
            "Plan de Autoprotección\nFecha: 01/06/2025\n"
            "Es un resumen de trabajo. No sustituye al Plan completo. Documento borrador.\n"
        ),
        Procedencia(doc_type="PLAN_AUTOPROTECCION"),
    )
    assert len([lim for lim in a.limitaciones if lim.motivo == "NO_VIGENTE"]) == 1


# ─────────────────────────────────────────────────────────────────────────────
#  Las reservas que el propio documento redacta
# ─────────────────────────────────────────────────────────────────────────────

#: Con la forma observada en un documento real: un índice al principio y la
#: sección de verdad después.
CON_INDICE = """\
Plan de Autoprotección
Fecha: 01/06/2025

Índice estructural

1. Resumen ejecutivo

2. Capítulo 1: identificación del titular

3. Alertas, vacíos e inconsistencias

1. Resumen ejecutivo

El complejo está formado por seis naves industriales con oficinas anejas y viales
perimetrales para vehículos pesados de reparto y distribución.

2. Capítulo 1: identificación del titular

Recoge el nombre y la dirección del establecimiento, los usos, las licencias y el
titular de la actividad, junto con sus responsables designados.

3. Alertas, vacíos e inconsistencias

Los siguientes puntos surgen del propio documento:

• El plan se redactó con las naves vacías. No refleja necesariamente actividades,
  mercancías, estanterías, cargas de fuego ni distribuciones actuales.

• Los recorridos de evacuación se definieron suponiendo espacios diáfanos.
  Cualquier implantación interior puede alterar longitudes, salidas y capacidades.
"""


def test_el_indice_no_se_confunde_con_la_seccion() -> None:
    """`[REQ]` **El fallo que más caro salía.** El epígrafe aparece dos veces: en
    el sumario y como encabezado real. Enganchando el del sumario, el cuerpo
    abarcaba el documento entero: medido contra un documento de verdad, **112
    limitaciones de uno que tenía doce**."""
    reservas, se_ha_pasado = _reservas_declaradas(CON_INDICE)

    assert not se_ha_pasado
    assert len(reservas) == 2, [r[0][:60] for r in reservas]
    assert all(epigrafe == "Alertas, vacíos e inconsistencias" for _, epigrafe in reservas)
    # Y no se ha colado nada del capítulo 1 ni del resumen ejecutivo.
    assert not any("seis naves" in texto for texto, _ in reservas)
    assert not any("licencias" in texto for texto, _ in reservas)


def test_la_frase_que_introduce_la_lista_no_es_una_limitacion() -> None:
    """«Los siguientes puntos surgen del propio documento:» anuncia la lista, no
    la compone."""
    reservas, _ = _reservas_declaradas(CON_INDICE)
    assert not any(texto.endswith(":") for texto, _ in reservas)


def test_las_reservas_se_recogen_literales() -> None:
    """`[REQ]` No se reescriben. Están redactadas por quien conoce el edificio y
    el informe las va a citar: parafrasearlas cambiaría el alcance de una
    salvedad técnica por el de un resumen automático."""
    reservas, _ = _reservas_declaradas(CON_INDICE)
    assert any(
        texto.startswith("El plan se redactó con las naves vacías.") for texto, _ in reservas
    )


def test_un_documento_sin_seccion_de_reservas_no_inventa_ninguna() -> None:
    """`[LIM]` Un plan de autoprotección **no suele traerla**: la Norma Básica
    fija capítulos 1 a 9 y anexos, y ninguno es «limitaciones»."""
    reservas, _ = _reservas_declaradas(
        "Plan de Autoprotección\n\n1. Capítulo 1\n\n" + ("texto normal " * 60)
    )
    assert reservas == []


def test_pasarse_del_tope_se_dice_en_vez_de_recortar_en_silencio() -> None:
    """`[REQ]` Cincuenta limitaciones no son cincuenta limitaciones: significa
    que el corte por epígrafes ha fallado. Truncar sin avisar dejaría creer que
    el documento tenía exactamente las que se ven."""
    frase = "Una salvedad técnica del documento con longitud suficiente para contar.\n\n"
    texto = "1. Limitaciones del documento\n\n" + frase * (TOPE_DECLARADAS + 8)
    reservas, se_ha_pasado = _reservas_declaradas(texto)

    assert len(reservas) == TOPE_DECLARADAS
    assert se_ha_pasado

    a = PlanDeAutoproteccion().leer(_pdf_falso(texto), Procedencia(doc_type="PLAN_AUTOPROTECCION"))
    assert any("solo se han recogido" in aviso for aviso in a.avisos)


# ─────────────────────────────────────────────────────────────────────────────
#  Degradar sin mentir
# ─────────────────────────────────────────────────────────────────────────────


def test_un_pdf_ilegible_no_tumba_la_lectura_y_lo_dice() -> None:
    a = PlanDeAutoproteccion().leer(
        b"esto no es un PDF", Procedencia(doc_type="PLAN_AUTOPROTECCION")
    )
    assert a.limitaciones == []
    assert any("no se ha podido leer" in aviso.lower() for aviso in a.avisos)


def test_un_escaneado_se_reconoce_como_tal() -> None:
    """Un PDF sin texto da cuatro caracteres sueltos. Decirlo es la diferencia
    entre «no había limitaciones» y «no sé leer este fichero»."""
    a = PlanDeAutoproteccion().leer(
        _pdf_falso("Plan\n", corto=True), Procedencia(doc_type="PLAN_AUTOPROTECCION")
    )
    assert any("escaneado" in aviso for aviso in a.avisos)
    assert a.limitaciones == []


def test_siempre_avisa_de_que_el_inventario_de_pci_no_se_lee() -> None:
    """`[LIM]` El capítulo 4 del plan es el inventario de medios contra
    incendios y aquí no se lee. Sin este aviso, un plan leído sin errores
    dejaría creer que ya se ha aprovechado todo lo que traía."""
    a = PlanDeAutoproteccion().leer(
        _pdf_falso("Plan de Autoprotección\nFecha: 01/06/2025\n" + ("relleno " * 60)),
        Procedencia(doc_type="PLAN_AUTOPROTECCION"),
    )
    assert any("protección contra incendios" in aviso for aviso in a.avisos)


def test_el_extractor_declara_que_no_es_simulado() -> None:
    """`[REQ]` Lee el documento de verdad. Que sea determinista no lo convierte
    en un simulacro, y al revés: un simulacro no puede pasar por lectura."""
    assert PlanDeAutoproteccion().es_simulada is False
    assert PlanDeAutoproteccion().soporta == ("PLAN_AUTOPROTECCION",)


# ─────────────────────────────────────────────────────────────────────────────


#: Prosa neutra con la que llegar al mínimo de texto. No contiene ninguna de las
#: fórmulas que las reglas buscan: si lo hiciera, los casos negativos pasarían
#: por la razón equivocada.
_RELLENO = (
    "El presente documento describe la organización de los medios humanos y "
    "materiales disponibles en el establecimiento. Se estructura conforme a la "
    "Norma Basica de Autoproteccion y recoge la descripcion del edificio, sus "
    "instalaciones y los procedimientos previstos.\n"
)


def _pdf_falso(texto: str, *, corto: bool = False) -> bytes:
    """Un PDF de una página con ese texto.

    `[REQ]` Fabricado aquí. No hay ningún plan de cliente en el repositorio.

    Se **rellena hasta pasar de doscientos caracteres** salvo que se pida
    `corto`. Por debajo de ese umbral el extractor lo toma por un escaneado y se
    para antes de aplicar ninguna regla —que es lo correcto, y lo que hacía
    fallar a estas pruebas cuando los textos eran de dos líneas—.
    """
    import io

    from reportlab.lib.pagesizes import A4  # type: ignore[import-not-found]
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    if not corto:
        texto = texto + _RELLENO

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    cuerpo = getSampleStyleSheet()["BodyText"]
    # Un párrafo por línea: `reportlab` colapsa los saltos dentro de uno solo, y
    # el corte por epígrafes se apoya en que las líneas sigan siendo líneas.
    doc.build([Paragraph(linea or "&nbsp;", cuerpo) for linea in texto.split("\n")])
    return buffer.getvalue()
