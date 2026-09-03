"""Extraer datos de la documentación que se sube `[REQ]`.

La idea, con las palabras del cliente: **según se va subiendo documentación, el
cuadro de CAPEX se va completando solo, y el gestor de la due diligence valida
después**. Eso obliga a dos cosas que no son evidentes hasta que hay más de un
documento:

1. **Un extractor por tipo de documento**, elegido por `doc_type`. La memoria
   técnica da superficies y objetos; un plan de autoprotección da equipos de
   PCI y limitaciones; un contrato de mantenimiento da periodicidades. Meterlos
   en la misma función acabaría en un `if` gigante que nadie se atreve a tocar.

2. **Cada propuesta con su procedencia.** Si dos documentos dicen que la
   superficie construida son 8.134 y 8.200, el gestor tiene que ver **las dos,
   con su documento y su párrafo**, y elegir. Una propuesta sin procedencia es
   un número huérfano, y ante un número huérfano lo único razonable es no
   fiarse: se pierde justo el trabajo que la extracción ahorraba.

`[REQ]` Nada de lo que sale de aquí escribe en el activo ni en el CAPEX. Todo
es propuesta, y entre la propuesta y el dato hay una persona pulsando un botón.
"""
