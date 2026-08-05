"""Reglas del bloque de fotografías `[REQ]` §15.5, §15.9 y §15.10."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from tdd.evidence.service import (
    DIAS_DE_PAPELERA,
    Aviso,
    ContextoDeFoto,
    EstadoDeFoto,
    FotoConocida,
    FotoParaInforme,
    PurgaNoPermitida,
    Severidad,
    TipoDeDuplicado,
    TransicionDeFotoNoPermitida,
    agrupar_duplicados,
    avisos_previos_al_informe,
    buscar_duplicado,
    comprobar_purga,
    comprobar_transicion,
    dias_restantes_en_papelera,
    distancia_en_metros,
    planificar_renombrado,
)

AHORA = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


def id_() -> uuid.UUID:
    return uuid.uuid4()


# ─────────────────────────────────────────────────────────────────────────────
#  Máquina de estados §15.9
# ─────────────────────────────────────────────────────────────────────────────


def test_el_camino_normal_de_una_foto() -> None:
    comprobar_transicion(EstadoDeFoto.SUBIENDO, EstadoDeFoto.PROCESANDO)
    comprobar_transicion(EstadoDeFoto.PROCESANDO, EstadoDeFoto.LISTA)
    comprobar_transicion(EstadoDeFoto.LISTA, EstadoDeFoto.PAPELERA)
    comprobar_transicion(EstadoDeFoto.PAPELERA, EstadoDeFoto.LISTA)


def test_una_foto_purgada_no_vuelve() -> None:
    """La purga es física e irreversible: no hay estado de destino."""
    with pytest.raises(TransicionDeFotoNoPermitida):
        comprobar_transicion(EstadoDeFoto.PURGADA, EstadoDeFoto.LISTA)


def test_una_foto_en_cuarentena_no_pasa_a_lista_sin_mas() -> None:
    """Lo que dio positivo en el antivirus no se «rehabilita» con un cambio de
    estado: se purga con autorización, y el objeto se conserva para análisis."""
    with pytest.raises(TransicionDeFotoNoPermitida, match="CUARENTENA"):
        comprobar_transicion(EstadoDeFoto.CUARENTENA, EstadoDeFoto.LISTA)


def test_el_error_dice_a_donde_si_se_puede_ir() -> None:
    with pytest.raises(TransicionDeFotoNoPermitida, match="PAPELERA"):
        comprobar_transicion(EstadoDeFoto.LISTA, EstadoDeFoto.PROCESANDO)


# ─────────────────────────────────────────────────────────────────────────────
#  Duplicados §15.5
# ─────────────────────────────────────────────────────────────────────────────


def test_el_duplicado_exacto_se_detecta_por_sha256() -> None:
    ya = FotoConocida(id_(), sha256="a" * 64, phash="0000000000000000")
    encontrado = buscar_duplicado("a" * 64, "ffffffffffffffff", [ya])
    assert encontrado is not None
    assert encontrado.tipo is TipoDeDuplicado.EXACTO
    assert encontrado.photo_id == ya.id


def test_el_casi_duplicado_se_detecta_por_hash_perceptual() -> None:
    """Dos disparos de la misma escena: distinto fichero, misma foto."""
    ya = FotoConocida(id_(), sha256="a" * 64, phash="ffffffffffffff00")
    encontrado = buscar_duplicado("b" * 64, "ffffffffffffff01", [ya])
    assert encontrado is not None
    assert encontrado.tipo is TipoDeDuplicado.CASI
    assert 0 < encontrado.distancia <= 5


def test_dos_fotos_distintas_no_se_marcan_como_duplicadas() -> None:
    ya = FotoConocida(id_(), sha256="a" * 64, phash="0000000000000000")
    assert buscar_duplicado("b" * 64, "ffffffffffffffff", [ya]) is None


def test_entre_varios_casi_duplicados_gana_el_mas_parecido() -> None:
    lejano = FotoConocida(id_(), sha256="c" * 64, phash="ffffffffffffff0f")
    cercano = FotoConocida(id_(), sha256="d" * 64, phash="ffffffffffffff01")
    encontrado = buscar_duplicado("b" * 64, "ffffffffffffff00", [lejano, cercano])
    assert encontrado is not None
    assert encontrado.photo_id == cercano.id


def test_el_exacto_tiene_prioridad_sobre_el_perceptual() -> None:
    """Es la única coincidencia de la que se puede estar seguro."""
    casi = FotoConocida(id_(), sha256="c" * 64, phash="ffffffffffffff01")
    exacto = FotoConocida(id_(), sha256="a" * 64, phash="0000000000000000")
    encontrado = buscar_duplicado("a" * 64, "ffffffffffffff00", [casi, exacto])
    assert encontrado is not None
    assert encontrado.tipo is TipoDeDuplicado.EXACTO


def test_sin_hash_perceptual_solo_se_compara_el_exacto() -> None:
    """Una foto todavía en proceso no tiene `phash`: no puede arrastrar a nadie
    a un falso positivo."""
    ya = FotoConocida(id_(), sha256="a" * 64, phash=None)
    assert buscar_duplicado("b" * 64, "ffffffffffffff00", [ya]) is None


def test_el_mensaje_del_casi_duplicado_no_invita_a_borrar() -> None:
    """`[REQ]` Nunca se borra un duplicado automáticamente: una foto
    aparentemente redundante puede ser la única que documenta un detalle."""
    ya = FotoConocida(id_(), sha256="a" * 64, phash="ffffffffffffff00")
    encontrado = buscar_duplicado("b" * 64, "ffffffffffffff01", [ya])
    assert encontrado is not None
    assert "revíselo" in encontrado.mensaje


def test_se_agrupan_los_duplicados_para_revisarlos_juntos() -> None:
    a = FotoConocida(id_(), sha256="a" * 64, phash="ffffffffffffff00")
    b = FotoConocida(id_(), sha256="a" * 64, phash="ffffffffffffff00")
    c = FotoConocida(id_(), sha256="c" * 64, phash="0000000000000000")
    grupos = agrupar_duplicados([a, b, c])
    assert grupos == [[a.id, b.id]]


def test_sin_repetidos_no_hay_grupos() -> None:
    fotos = [
        FotoConocida(id_(), sha256="a" * 64, phash="0000000000000000"),
        FotoConocida(id_(), sha256="b" * 64, phash="ffffffffffffffff"),
    ]
    assert agrupar_duplicados(fotos) == []


# ─────────────────────────────────────────────────────────────────────────────
#  GPS §15.6
# ─────────────────────────────────────────────────────────────────────────────


def test_la_distancia_entre_dos_puntos_conocidos() -> None:
    """Puerta del Sol y Atocha: unos 1,5 km en línea recta."""
    metros = distancia_en_metros(40.416775, -3.703790, 40.406690, -3.690490)
    assert 1_400 < metros < 1_700


def test_la_distancia_de_un_punto_a_si_mismo_es_cero() -> None:
    assert distancia_en_metros(40.4, -3.7, 40.4, -3.7) == pytest.approx(0.0)


# ─────────────────────────────────────────────────────────────────────────────
#  Avisos previos al informe §15.10
# ─────────────────────────────────────────────────────────────────────────────


def _seleccionada(**kwargs: object) -> FotoParaInforme:
    base = {
        "id": id_(),
        "estado": EstadoDeFoto.LISTA,
        "include_in_report": True,
        "asset_id": id_(),
        "caption": "Fisuras en la solera",
    }
    return FotoParaInforme(**{**base, **kwargs})  # type: ignore[arg-type]


def _codigos(avisos: list[Aviso]) -> set[str]:
    return {a.codigo for a in avisos}


def test_una_foto_correcta_no_genera_avisos() -> None:
    assert avisos_previos_al_informe([_seleccionada()]) == []


def test_una_foto_en_cuarentena_seleccionada_es_bloqueante() -> None:
    """El único aviso que impide generar el informe: insertar una foto que no
    ha superado las verificaciones."""
    avisos = avisos_previos_al_informe([_seleccionada(estado=EstadoDeFoto.CUARENTENA)])
    assert avisos[0].severidad is Severidad.BLOQUEANTE
    assert avisos[0].codigo == "PHOTO_NOT_USABLE"


def test_una_foto_sin_activo_avisa_pero_no_bloquea() -> None:
    """`[REQ]` Se acepta con aviso, no con error: en campo se fotografía antes
    de saber a qué activo corresponde."""
    avisos = avisos_previos_al_informe([_seleccionada(asset_id=None)])
    assert "PHOTO_WITHOUT_ASSET" in _codigos(avisos)
    assert all(a.severidad is not Severidad.BLOQUEANTE for a in avisos)


def test_una_foto_sin_pie_es_solo_un_aviso_de_calidad() -> None:
    avisos = avisos_previos_al_informe([_seleccionada(caption="   ")])
    assert [a.severidad for a in avisos] == [Severidad.BAJA]


def test_las_fotos_no_seleccionadas_no_generan_avisos() -> None:
    """Un proyecto con 1.400 fotos sin pie no debe producir 1.400 avisos: solo
    importa lo que va a salir en el informe."""
    fotos = [_seleccionada(include_in_report=False, caption=None, asset_id=None)] * 50
    assert avisos_previos_al_informe(fotos) == []


def test_una_foto_lejos_del_activo_avisa_sin_bloquear() -> None:
    """Aviso, nunca bloqueo: hay sótanos sin GPS fiable y hay instalaciones
    exteriores legítimamente alejadas."""
    avisos = avisos_previos_al_informe(
        [_seleccionada(gps=(40.416775, -3.703790), gps_del_activo=(40.406690, -3.690490))]
    )
    assert "PHOTO_GPS_FAR_FROM_ASSET" in _codigos(avisos)
    assert avisos[0].severidad is Severidad.MEDIA


def test_una_foto_cerca_del_activo_no_avisa() -> None:
    avisos = avisos_previos_al_informe(
        [_seleccionada(gps=(40.416775, -3.703790), gps_del_activo=(40.417000, -3.704000))]
    )
    assert avisos == []


def test_un_activo_sin_fotos_seleccionadas_se_avisa() -> None:
    huerfano = id_()
    avisos = avisos_previos_al_informe([_seleccionada()], activos_esperados=[huerfano])
    assert "ASSET_WITHOUT_PHOTOS" in _codigos(avisos)


# ─────────────────────────────────────────────────────────────────────────────
#  Renombrado en lote §15.4
# ─────────────────────────────────────────────────────────────────────────────


def _contexto(nombre: str, **valores: str | None) -> ContextoDeFoto:
    base = {"proyecto": "2026-014", "activo": "Nave A", "sistema": "CLIMA", "zona": "Cubierta"}
    return ContextoDeFoto(
        photo_id=id_(), nombre_actual=nombre, extension="jpg", valores={**base, **valores}
    )


def test_la_previsualizacion_devuelve_la_tabla_antes_y_despues() -> None:
    plan = planificar_renombrado([_contexto("IMG_4821")], numerar_desde=1)
    assert plan.cambios[0].antes == "IMG_4821"
    assert plan.cambios[0].despues == "2026-014_NaveA_CLIMA_Cubierta_001"
    assert plan.total_cambian == 1


def test_el_correlativo_avanza_dentro_del_lote() -> None:
    plan = planificar_renombrado([_contexto("a"), _contexto("b"), _contexto("c")], numerar_desde=1)
    assert [c.despues[-3:] for c in plan.cambios] == ["001", "002", "003"]


def test_sin_numerar_los_nombres_repetidos_reciben_sufijo() -> None:
    """Sin correlativo, tres fotos de la misma zona producirían el mismo
    nombre. El sufijo alfabético las separa sin tocar el número."""
    plan = planificar_renombrado([_contexto("a"), _contexto("b")])
    assert plan.cambios[0].despues != plan.cambios[1].despues
    assert plan.cambios[1].despues.endswith("_b")
    assert len(plan.colisiones_resueltas) == 1


def test_un_nombre_que_no_cambia_se_marca_como_tal() -> None:
    """38 de 40 es mejor que 0 de 40, y para eso hay que saber cuáles cambian."""
    ya_bueno = ContextoDeFoto(
        photo_id=id_(),
        nombre_actual="2026-014_NaveA_CLIMA_Cubierta_001",
        extension="jpg",
        valores={
            "proyecto": "2026-014",
            "activo": "Nave A",
            "sistema": "CLIMA",
            "zona": "Cubierta",
            "numero": "001",
        },
    )
    plan = planificar_renombrado([ya_bueno])
    assert plan.cambios[0].cambia is False
    assert plan.total_cambian == 0


def test_los_tokens_sin_valor_se_informan_para_que_el_usuario_lo_vea() -> None:
    plan = planificar_renombrado([_contexto("a", zona=None)], numerar_desde=1)
    assert plan.cambios[0].omitidos == ("[Zona]",)


def test_un_lote_vacio_no_falla() -> None:
    plan = planificar_renombrado([])
    assert plan.cambios == ()


# ─────────────────────────────────────────────────────────────────────────────
#  Papelera y purga §15.9
# ─────────────────────────────────────────────────────────────────────────────


def test_quedan_dias_de_retencion_recien_borrada() -> None:
    assert dias_restantes_en_papelera(AHORA, AHORA) == DIAS_DE_PAPELERA


def test_la_retencion_se_agota_a_los_treinta_dias() -> None:
    assert dias_restantes_en_papelera(AHORA - timedelta(days=30), AHORA) == 0


def test_no_se_purga_antes_de_cumplir_la_retencion() -> None:
    with pytest.raises(PurgaNoPermitida) as exc:
        comprobar_purga(
            estado=EstadoDeFoto.PAPELERA,
            borrada_el=AHORA - timedelta(days=3),
            ahora=AHORA,
            referenciada_por_informe_emitido=False,
        )
    assert exc.value.codigo == "RETENTION_NOT_ELAPSED"


def test_no_se_purga_lo_que_no_esta_en_la_papelera() -> None:
    with pytest.raises(PurgaNoPermitida) as exc:
        comprobar_purga(
            estado=EstadoDeFoto.LISTA,
            borrada_el=None,
            ahora=AHORA,
            referenciada_por_informe_emitido=False,
        )
    assert exc.value.codigo == "NOT_IN_TRASH"


def test_una_foto_de_un_informe_emitido_no_se_purga_nunca() -> None:
    """`[REC]` Un informe emitido debe seguir siendo reproducible. Esta guarda
    va la primera a propósito: se aplica aunque la retención esté cumplida."""
    with pytest.raises(PurgaNoPermitida) as exc:
        comprobar_purga(
            estado=EstadoDeFoto.PAPELERA,
            borrada_el=AHORA - timedelta(days=400),
            ahora=AHORA,
            referenciada_por_informe_emitido=True,
        )
    assert exc.value.codigo == "REFERENCED_BY_ISSUED_REPORT"


def test_la_retencion_del_proyecto_manda_sobre_la_de_la_papelera() -> None:
    with pytest.raises(PurgaNoPermitida) as exc:
        comprobar_purga(
            estado=EstadoDeFoto.PAPELERA,
            borrada_el=AHORA - timedelta(days=60),
            ahora=AHORA,
            referenciada_por_informe_emitido=False,
            retencion_del_proyecto_hasta=date(2033, 1, 1),
        )
    assert exc.value.codigo == "PROJECT_RETENTION_ACTIVE"


def test_cumplida_la_retencion_la_purga_se_permite() -> None:
    comprobar_purga(
        estado=EstadoDeFoto.PAPELERA,
        borrada_el=AHORA - timedelta(days=31),
        ahora=AHORA,
        referenciada_por_informe_emitido=False,
    )


def test_la_cuarentena_se_purga_con_autorizacion_sin_esperar_retencion() -> None:
    """Un positivo del antivirus no tiene por qué quedarse 30 días guardado."""
    comprobar_purga(
        estado=EstadoDeFoto.CUARENTENA,
        borrada_el=None,
        ahora=AHORA,
        referenciada_por_informe_emitido=False,
    )
