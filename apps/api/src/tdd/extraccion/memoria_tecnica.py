"""El extractor de memorias técnicas, detrás del puerto.

La lectura del PDF no cambia: sigue en `tdd.memoria.extraccion`, escrita contra
una memoria real y con sus pruebas. Lo que hace este módulo es **adaptarla al
contrato**: convertir lo que aquélla devuelve en `CampoPropuesto`, cada uno con
la procedencia que permite comprobarlo.

`[LIM]` Sigue escrito contra **una** memoria. Que lea ésa está medido; que
generalice, no. Con una segunda podrá decirse.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from tdd.extraccion.puerto import (
    Aportacion,
    CampoPropuesto,
    PlantaPropuesta,
    Procedencia,
    registrar,
)
from tdd.memoria import extraccion as lector

#: El `doc_type` que este extractor atiende.
TIPO = "MEMORIA_TECNICA"


@dataclass(frozen=True, slots=True)
class MemoriaTecnica:
    """Lee una memoria técnica en PDF. Determinista, sin IA y sin red."""

    nombre: str = "memoria-tecnica-v1"
    soporta: tuple[str, ...] = (TIPO,)
    #: `[REQ]` **No es simulado**: lee el documento de verdad y lo que propone
    #: sale de él. Que sea determinista no lo convierte en un simulacro.
    es_simulada: bool = field(default=False)

    def leer(self, contenido: bytes, procedencia: Procedencia) -> Aportacion:
        leido = lector.leer(contenido)

        aportacion = Aportacion(
            doc_type=procedencia.doc_type,
            extractor=self.nombre,
            es_simulada=self.es_simulada,
            desconocidos=dict(leido.desconocidos),
            avisos=list(leido.avisos),
        )

        # La sección de la que sale cada superficie es la tabla de la memoria.
        # Se nombra igual para todas porque es una sola tabla: fingir un
        # epígrafe distinto por fila sería inventarse una precisión que no hay.
        de_la_tabla = replace(procedencia, seccion="Tabla de superficies y portada")
        for campo, valor in sorted(leido.propuesta.items()):
            aportacion.campos.append(
                CampoPropuesto(
                    campo=campo,
                    valor=str(valor),
                    # La celda **tal y como está escrita**. Si no la hay, se deja
                    # vacía en vez de reconstruirla: una evidencia inventada es
                    # peor que ninguna, porque parece comprobable y no lo es.
                    procedencia=replace(de_la_tabla, evidencia=leido.evidencias.get(campo)),
                )
            )

        for planta in leido.plantas:
            aportacion.plantas.append(
                PlantaPropuesta(
                    label=planta.label,
                    level=planta.level,
                    usable_area_sqm=planta.usable_area_sqm,
                    procedencia=replace(
                        de_la_tabla,
                        evidencia=leido.evidencias.get(f"planta:{planta.label}"),
                    ),
                )
            )

        # `[LIM]` Los objetos del CAPEX **no salen de aquí**. La memoria los
        # enumera en prosa dentro de sus secciones constructivas, y repartirlos
        # entre capítulos es clasificación semántica: vive en
        # `tdd.memoria.clasificacion` y necesita un proveedor sin elegir. Lo que
        # este extractor sí deja es el texto de las secciones, que es su
        # materia prima, en los avisos de abajo. Cuando haya clasificador, lo que
        # devuelva entra en `aportacion.objetos` sin tocar nada más de aquí.
        if leido.secciones:
            constructivas = [s for s in leido.secciones if s.codigo.startswith(("MC", "MD.2"))]
            aportacion.avisos.append(
                f"Se han reconocido {len(leido.secciones)} epígrafes, {len(constructivas)} de "
                "ellos constructivos. Los objetos del CAPEX que describen NO se han "
                "propuesto: hace falta clasificarlos, y eso todavía no está construido."
            )
        return aportacion


registrar(MemoriaTecnica())
