"""Datos de demostración: una cartera con tres activos y dos años de consumo.

Sirven para recorrer la aplicación con algo dentro y para desarrollar la
interfaz. **No** son datos reales de ningún cliente: los consumos se generan
con una estacionalidad sencilla —más electricidad en verano, más gas en
invierno— para que los gráficos digan algo.

Deja a propósito tres cosas imperfectas, porque son las que hay que ver
funcionando: un mes sin lectura (para que la cobertura no dé 100 %), una
lectura de gas en m³ sin poder calorífico (que se guarda y no suma) y una
factura de IA con poca confianza esperando revisión.
"""

from __future__ import annotations

import argparse
import math
import sys
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, text

from esg.indicadores.reparto import mes_siguiente


def _mes_a_mes(desde: date, meses: int) -> list[tuple[date, date]]:
    periodos = []
    actual = desde
    for _ in range(meses):
        siguiente = mes_siguiente(actual)
        periodos.append((actual, siguiente))
        actual = siguiente
    return periodos


def sembrar_demo(dsn: str, *, email_admin: str = "demo@ejemplo.example") -> None:
    motor = create_engine(dsn, future=True)
    with motor.begin() as conn:
        org = conn.execute(
            text(
                "INSERT INTO organizacion (nombre, slug) VALUES ('Consultora de Demostración', "
                "'demo') ON CONFLICT (slug) DO UPDATE SET nombre = EXCLUDED.nombre RETURNING id"
            )
        ).scalar_one()
        for correo, nombre, rol in (
            (email_admin, "Administradora de demostración", "ADMIN"),
            ("analista@ejemplo.example", "Analista de demostración", "ANALISTA"),
            ("cliente@ejemplo.example", "Gestora del fondo", "CLIENTE"),
        ):
            conn.execute(
                text(
                    "INSERT INTO usuario (organizacion_id, email, nombre, rol) "
                    "VALUES (:o, :e, :n, CAST(:r AS rol_usuario)) "
                    "ON CONFLICT (organizacion_id, lower(email)) DO NOTHING"
                ),
                {"o": org, "e": correo, "n": nombre, "r": rol},
            )

        carteras: dict[str, uuid.UUID] = {}
        for nombre, codigo in (("Cartera Ibérica", "IB"), ("Cartera Levante", "LV")):
            carteras[codigo] = conn.execute(
                text(
                    "INSERT INTO cartera (organizacion_id, nombre, codigo) "
                    "VALUES (:o, :n, :c) RETURNING id"
                ),
                {"o": org, "n": nombre, "c": codigo},
            ).scalar_one()

        # El cliente de demostración solo ve la cartera Ibérica: es lo que hace
        # visible, al entrar con su correo, que el ámbito funciona.
        conn.execute(
            text(
                "INSERT INTO ambito_de_visibilidad (organizacion_id, usuario_id, cartera_id) "
                "SELECT :o, id, :c FROM usuario WHERE email = 'cliente@ejemplo.example'"
            ),
            {"o": org, "c": carteras["IB"]},
        )

        activos: dict[str, uuid.UUID] = {}
        for codigo, nombre, cartera, tipologia, superficie, municipio in (
            ("A-001", "Torre Diagonal", "IB", "OFICINAS", 18500, "Barcelona"),
            ("A-002", "Parque Logístico Sur", "IB", "LOGISTICO", 42000, "Getafe"),
            ("A-003", "Centro Comercial Levante", "LV", "COMERCIAL", 26500, "Valencia"),
        ):
            activos[codigo] = conn.execute(
                text(
                    "INSERT INTO activo (organizacion_id, cartera_id, codigo, nombre, municipio, "
                    "tipologia, superficie_alquilable_m2, superficie_bruta_m2, incorporado_en) "
                    "VALUES (:o, :c, :cod, :n, :m, CAST(:t AS tipologia_activo), :s, :sb, "
                    "'2022-01-01') RETURNING id"
                ),
                {
                    "o": org,
                    "c": carteras[cartera],
                    "cod": codigo,
                    "n": nombre,
                    "m": municipio,
                    "t": tipologia,
                    "s": superficie,
                    "sb": superficie * 1.15,
                },
            ).scalar_one()

        suministros: list[tuple[uuid.UUID, str, str, str, float]] = []
        for codigo, base_luz, base_agua, base_gas, base_residuos in (
            ("A-001", 92000, 900, 41000, 5200),
            ("A-002", 61000, 380, 12000, 8600),
            ("A-003", 135000, 1600, 22000, 14500),
        ):
            activo = activos[codigo]
            for vector, sufijo, unidad, base in (
                ("ELECTRICIDAD", "LUZ", "kWh", base_luz),
                ("AGUA", "AGUA", "m3", base_agua),
                ("GAS", "GAS", "kWh", base_gas),
                ("RESIDUOS", "RSU", "kg", base_residuos),
            ):
                identificador = conn.execute(
                    text(
                        "INSERT INTO punto_de_suministro (organizacion_id, activo_id, vector, "
                        "codigo, unidad_de_factura, alta_en, fraccion) VALUES (:o, :a, "
                        "CAST(:v AS vector_esg), :c, :u, '2022-01-01', "
                        "CAST(:f AS fraccion_residuo)) RETURNING id"
                    ),
                    {
                        "o": org,
                        "a": activo,
                        "v": vector,
                        "c": f"{codigo}-{sufijo}",
                        "u": unidad,
                        "f": "RESTO" if vector == "RESIDUOS" else None,
                    },
                ).scalar_one()
                suministros.append((identificador, vector, unidad, codigo, base / 12))

        hoy = date.today()
        # Veinticuatro meses que **acaban en el mes pasado**, no dos años
        # naturales: con años fijos, la demostración envejece y el panel abre
        # con la ventana de doce meses vacía. Se vio en la primera captura.
        primero_de_este_mes = hoy.replace(day=1)
        arranque = date(primero_de_este_mes.year - 2, primero_de_este_mes.month, 1)
        for punto, vector, unidad, codigo, media in suministros:
            for indice, (inicio, fin) in enumerate(_mes_a_mes(arranque, 24)):
                if fin > primero_de_este_mes:
                    break  # el mes en curso todavía no ha facturado
                # Un hueco a propósito: sin él, la cobertura sale al 100 % y no
                # se ve para qué sirve el indicador.
                if codigo == "A-002" and vector == "AGUA" and indice == 7:
                    continue
                estacion = 1 + 0.28 * math.sin((indice % 12) / 12 * 2 * math.pi - 1.2)
                if vector == "GAS":
                    estacion = 1 + 0.55 * math.cos((indice % 12) / 12 * 2 * math.pi)
                # Una mejora sostenida del 6 % en el segundo año: es lo que la
                # comparativa interanual tiene que enseñar.
                tendencia = 1 - 0.06 * (indice // 12)
                cantidad = Decimal(str(round(media * estacion * tendencia, 2)))
                conn.execute(
                    text(
                        "INSERT INTO lectura (organizacion_id, punto_id, inicio, fin, cantidad, "
                        "unidad, cantidad_normalizada, unidad_normalizada, factor_de_conversion, "
                        "origen) VALUES (:o, :p, :i, :f, :c, :u, :c, :u, 1, 'MANUAL')"
                    ),
                    {"o": org, "p": punto, "i": inicio, "f": fin, "c": cantidad, "u": unidad},
                )

        # Ocupación: solo de la Torre. Los otros dos activos se quedan sin ella
        # a propósito, para que se vea que la intensidad por ocupante no se
        # inventa cuando falta el dato.
        for inicio, fin in _mes_a_mes(arranque, 24):
            if fin > primero_de_este_mes:
                break
            conn.execute(
                text(
                    "INSERT INTO ocupacion (organizacion_id, activo_id, mes, ocupantes_medios) "
                    "VALUES (:o, :a, :m, 640) ON CONFLICT (activo_id, mes) DO NOTHING"
                ),
                {"o": org, "a": activos["A-001"], "m": inicio},
            )

        # Y una factura de gas en m³ sin poder calorífico: se guarda y no suma.
        gas_torre = conn.execute(
            text("SELECT id FROM punto_de_suministro WHERE codigo = 'A-001-GAS'")
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO lectura (organizacion_id, punto_id, inicio, fin, cantidad, unidad, "
                "origen, nota) VALUES (:o, :p, :i, :f, 3120, 'm3', 'FICHERO', "
                "'Sin poder calorífico del periodo: no se agrega') "
                "ON CONFLICT DO NOTHING"
            ),
            # El mes en curso, que es el único hueco libre: los 24 anteriores
            # ya tienen lectura y el solape los rechazaría.
            {
                "o": org,
                "p": gas_torre,
                "i": primero_de_este_mes,
                "f": mes_siguiente(primero_de_este_mes),
            },
        )
    motor.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Siembra datos de demostración")
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--email", default="demo@ejemplo.example")
    a = parser.parse_args(argv)
    sembrar_demo(a.dsn, email_admin=a.email)
    print(f"Demostración sembrada. Entre como {a.email} (modo local) o dé de alta ese correo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
