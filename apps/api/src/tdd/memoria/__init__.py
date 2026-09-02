"""La memoria técnica del activo `[REQ]`.

Es el documento que entrega la propiedad con todos los datos del edificio y el
listado de categorías del CAPEX con sus objetos. Sirve para dos cosas:

1. **Completar la ficha del activo** sin volver a teclearla.
2. **Generar el esqueleto del CAPEX**: una fila por categoría presente y una
   subfila por objeto, que el gestor técnico va completando y ampliando.

`[REQ]` Entre extraer y aplicar hay un **botón**. La propuesta vive en
`memoria_tecnica.propuesta` y no toca el activo hasta que alguien la acepta.
Un clic, no un tecleo — pero un clic de alguien. Es la regla que puso el
cliente cuando se le planteó la tensión entre «que no haya duplicidad de
trabajo» y «que ningún dato sin revisar llegue al informe».

`[LIM]` La **extracción automática no está construida**. Faltan dos cosas y
ninguna es código: el proveedor de IA, que sigue sin elegir, y un ejemplo real
de memoria técnica contra el que escribirla. Lo que hay aquí es dónde vive la
propuesta, cómo se acepta y qué genera. Rellenar la memoria a mano funciona
hoy; extraerla de un PDF, no.
"""
