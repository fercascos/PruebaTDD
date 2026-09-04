"""Siembra el catálogo de factores de conversión fijos.

Los factores fijos **son definiciones** (1 MWh = 1.000 kWh, 1 t = 1.000 kg) y
viven en `indicadores/unidades.py`, que es lo que usa el motor: no se va a la
base de datos a preguntar cuántos kilos tiene una tonelada.

Entonces, ¿por qué están también en una tabla? Porque un informe ESG hay que
poder defenderlo, y quien lo audita pregunta «¿con qué factor convertisteis
esto?» y espera una respuesta que se pueda consultar sin leer el código. La
tabla es **el reflejo** del catálogo del código, no una segunda verdad: la
siembra la genera desde `FACTORES_FIJOS`, y hay una prueba que falla si divergen.

Lo que sí es dato de verdad en esa tabla, y no reflejo de nada, es el poder
calorífico del gas: cambia por comercializadora y por periodo, y se da de alta
por organización.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import create_engine, text

from esg.indicadores.unidades import FACTORES_FIJOS

FUENTE = "Definición del sistema de unidades (reflejo de esg.indicadores.unidades)"


def sembrar(dsn: str) -> int:
    motor = create_engine(dsn, future=True)
    sembrados = 0
    with motor.begin() as conn:
        for (origen, destino), factor in FACTORES_FIJOS.items():
            existe = conn.execute(
                text(
                    "SELECT count(*) FROM factor_de_conversion "
                    "WHERE organizacion_id IS NULL AND unidad_origen = :o AND unidad_destino = :d"
                ),
                {"o": origen, "d": destino},
            ).scalar_one()
            if existe:
                continue
            conn.execute(
                text(
                    "INSERT INTO factor_de_conversion (organizacion_id, unidad_origen, "
                    "unidad_destino, factor, fuente) VALUES (NULL, :o, :d, :f, :fuente)"
                ),
                {"o": origen, "d": destino, "f": factor, "fuente": FUENTE},
            )
            sembrados += 1
    motor.dispose()
    return sembrados


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Siembra los factores de conversión fijos")
    parser.add_argument("--dsn", required=True)
    argumentos = parser.parse_args(argv)
    print(f"Factores sembrados: {sembrar(argumentos.dsn)} (la siembra es idempotente).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
