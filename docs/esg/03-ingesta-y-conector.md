# ESG · 3. Cómo entran los datos

Dos caminos, un solo destino: la tabla `lectura`, con las mismas restricciones y
la misma procedencia. Lo único que los distingue es el `origen` y, en el de IA,
la **confianza**.

---

## 3.1. Carga manual de CSV y XLSX

```
fichero → leer → proponer mapeo → confirmar → SIMULAR → incidencias → APLICAR
```

### Lo que se ha aprendido de los ficheros reales

| Manía del fichero | Qué se hace |
|---|---|
| Punto y coma como separador, y BOM delante | Se prueban `;`, `,`, tabulador y `\|`; se decodifica en UTF-8 y, si no, en Windows-1252 |
| `10.240,50` y `10,240.50` en el mismo proyecto | Manda **el último separador**: el que está más a la derecha es el decimal |
| `31/03/2025`, `2025-03-31`, `31-03-2025` | Cuatro formatos admitidos; lo que no encaje es una incidencia con su valor |
| «del 1 al 31 de marzo» | El fin del fichero es **inclusivo**; se guarda `01/04`. Sin esto, marzo y abril se solapan un día cada mes y la carga entera del segundo mes se rechaza |
| Un XLSX renombrado a `.csv` | Se detecta por la firma ZIP y se dice en una frase, en vez de producir cien incidencias sin sentido |
| Filas en blanco en medio | No son un error: son un Excel |
| Un importe ilegible | **No invalida la fila**: el consumo es el dato, el importe es acompañamiento. Se avisa y se sigue |
| Un consumo negativo | Se rechaza: una regularización no se carga como consumo, o nadie sabrá cuál era cuál |

### Simular escribe de verdad

La simulación hace la carga entera **dentro de un punto de guardado** y lo
deshace al final. No es una comprobación aproximada del fichero: los solapes y
los duplicados los detecta la base de datos intentándolo.

Una simulación que solo mirase el fichero diría «1.200 filas correctas» y la
carga real fallaría en la 37, que es exactamente la situación que hace que nadie
vuelva a usar el botón de simular.

Las incidencias se guardan **después** del deshacer, así que el informe de una
simulación se puede volver a abrir (`GET /api/v1/cargas/{id}/incidencias`).

### Lo que la carga NO hace

**No da de alta activos ni suministros.** Un CUPS que no existe produce una
incidencia que dice qué hacer. Si se diera de alta solo, un CUPS mal tecleado se
convertiría en un activo fantasma con consumo real dentro, y esa clase de basura
no se detecta hasta que alguien suma dos veces el mismo edificio.

---

## 3.2. Conector con el lector de facturas de Azure

El lector ya existe y no se construye aquí: se consume. Lo que sí se construye
es la **frontera**, y por eso es un puerto (`conector/puerto.py`) con dos
implementaciones: la HTTP contra Azure y un doble en memoria.

```
LectorDeFacturas (puerto)
   ├── LectorAzure     — GET /facturas?desde&hasta&cursor, clave en cabecera
   ├── LectorEnMemoria — el de la suite: mismas facturas, sin red
   └── LectorNoConfigurado — el de una instalación sin conector: 503 con motivo
```

`[LIM]` El contrato de `LectorAzure` está escrito contra el formato **supuesto**
de la pregunta P-1 y no se ha ejercitado contra el servicio real. Todo lo que
hay detrás de la frontera sí está probado, con el doble. Cuando llegue el
contrato de verdad, lo que cambia es un fichero.

### La confianza no es un adorno

La IA acierta mucho. «Mucho» no es «siempre», y una factura mal leída **no se
distingue de una buena** una vez está dentro de la suma. Por eso:

- La confianza global de una factura es **la del peor campo**, no la media: una
  media alta esconde que la fecha del periodo venía al 40 %, y una fecha mal
  leída mueve el consumo de mes.
- Por debajo del umbral (`LECTOR_FACTURAS_CONFIANZA_MINIMA`, 0,85 por defecto)
  la lectura entra como `PENDIENTE_REVISION`: **no suma en ningún panel** hasta
  que una persona la confirma.
- La confianza campo a campo se guarda en la nota, porque lo primero que
  necesita saber quien revisa es qué campo venía dudoso.
- El PDF original **no se copia**: se guarda el enlace. Ya vive en el sistema
  que lo leyó, y duplicar un documento contable obliga a mantener dos copias
  sincronizadas para siempre.

### Idempotencia

`referencia_externa` —el identificador de la factura en origen— lleva índice
único. Importar dos veces la misma ventana no duplica nada: las repetidas salen
como rechazadas con su motivo. Y si la misma factura se cargó antes desde un
fichero, la que la para es la restricción de solape, con un mensaje que lo dice.
