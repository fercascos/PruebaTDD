"""`[LIM]` **MOCK.** Revisor simulado: no lee nada y no juzga nada.

Existe por una razón concreta: el proveedor de IA está sin elegir, y sin algo
que ocupe su sitio no se podrían construir ni probar el flujo, la pantalla ni
la confirmación humana, que son el 90 % del módulo y no dependen del proveedor.

**Qué hace y qué no.** Produce observaciones con la forma correcta, derivadas
del `sha256` del documento para que la misma entrada dé siempre lo mismo y las
pruebas sean estables. **No abre el fichero.** No hay ninguna relación entre lo
que dice y lo que el documento contiene.

Tres decisiones lo mantienen honesto:

* Cada resumen empieza por `SIMULADO —`. Quien lo lea en pantalla lo sabe sin
  tener que consultar nada.
* `confianza` se queda vacía **siempre**. Un número de confianza inventado
  sería lo más engañoso que podría hacer este módulo: se leería como una
  medida de algo.
* La evidencia dice explícitamente que no procede del documento, en vez de
  citar un texto plausible que nadie escribió.

Cuando se elija proveedor, este fichero **no se adapta: se sustituye**. Vive
aquí al lado del puerto para que reemplazarlo sea evidente.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from tdd.revision_documental.puerto import (
    Comprobacion,
    Dictamen,
    Documento,
    Observacion,
    Veredicto,
)

#: El nombre que se guarda en `doc_review.provider`. Se comprueba en las
#: pruebas: si alguien enchufa el simulado creyendo que es el real, la fila lo
#: delata.
NOMBRE = "SIMULADO"

#: Prefijo obligatorio de todo resumen. `test_revision_documental` comprueba
#: que ninguna observación simulada sale sin él.
MARCA = "SIMULADO —"

#: La rueda de veredictos. Cubre los cuatro para que la pantalla y el flujo de
#: aceptar/rechazar se puedan ejercitar enteros, incluido el caso incómodo de
#: `NO_CONFORME`, que es el que dispara trabajo de verdad.
RUEDA: tuple[Veredicto, ...] = (
    Veredicto.CONFORME,
    Veredicto.NO_CONFORME,
    Veredicto.DUDOSO,
    Veredicto.FALTA,
)


class RevisorSimulado:
    """Implementa `Revisor` sin llamar a ningún proveedor."""

    @property
    def nombre(self) -> str:
        return NOMBRE

    def revisar(
        self,
        documento: Documento,
        comprobaciones: Sequence[Comprobacion],
        *,
        fecha_encargo: date | None = None,
    ) -> Dictamen:
        """Una observación por criterio, determinista según el `sha256`.

        `fecha_encargo` se ignora: no hay nada que fechar cuando no se lee el
        documento. Se acepta porque el puerto lo declara y el adaptador real sí
        lo necesitará.
        """
        semilla = int(documento.sha256[:8], 16) if documento.sha256 else 0

        observaciones = tuple(
            Observacion(
                comprobacion=c.codigo,
                veredicto=RUEDA[(semilla + i) % len(RUEDA)],
                resumen=(
                    f"{MARCA} no se ha analizado «{documento.nombre}». "
                    f"Esta línea ocupa el sitio de lo que dirá el proveedor de "
                    f"IA sobre «{c.nombre}» cuando se elija uno."
                ),
                evidencia=("Sin evidencia: ningún proveedor ha leído el documento todavía."),
                pagina=None,
                confianza=None,
            )
            for i, c in enumerate(comprobaciones)
        )

        return Dictamen(
            observaciones=observaciones,
            proveedor=NOMBRE,
            modelo=None,
            simulado=True,
        )
