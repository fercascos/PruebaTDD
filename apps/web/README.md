# Frontend · PWA de due diligence técnica

React 18 + TypeScript sobre Vite. **Es la interfaz del MVP, no la aplicación
completa**: lo que hay funciona contra la API real; lo que falta está listado
abajo sin adornos.

## Arrancar en local

```bash
npm install
npm run dev        # http://localhost:5173, con proxy a la API en :8000
npm test           # 47 pruebas: cola, cola persistida, formas y estado de red
npm run build      # tipos (aplicación y service worker) + empaquetado

# ¿Abre sin red? Necesita el empaquetado servido y un Chromium:
npm run build && npx vite preview --port 4173 &
npm run test:sin-red
```

El proxy de `vite.config.ts` manda `/api` al backend, así que en desarrollo no
hay CORS y en producción la aplicación se sirve de un solo origen.

## Lo que hay

| Pantalla | Qué hace |
|---|---|
| **Inicio de sesión** | Emite el par de tokens y recupera la sesión al recargar |
| **Proyectos** | Listado de encargos de la organización |
| **Fases** | Estado de cada fase **con su motivo**; las derivadas se marcan como calculadas |
| **Activos** | Ficha resumida por activo |
| **Nuevo encargo** | Alta con cliente —nuevo o existente— y **elección de fases a la carta** |
| **Ficha de activo** | Alta y edición; los campos de nave se conservan al reclasificar |
| **Fotografías** | **Los tres orígenes**, cola de subida, selección y renombrado en lote |
| **Ficha de fotografía** | Clasificar por activo y zona, pie, orden en el informe, procedencia |
| **Mapa** | Las fotografías situadas sobre el terreno, con el recuento de las que no lo están |
| **Riesgos** | Distribución por grado, matriz riesgo × horizonte y desglose por capítulo |
| **Anotador** | Flechas, recuadros, elipses, líneas y texto sobre la foto; el original no se toca |
| **Nuevo hallazgo** | Con sus líneas de CAPEX, una por plazo; también **desde una foto** |
| **Hallazgos y CAPEX** | La tabla del informe: una fila por actuación, una columna por plazo, y **exportar a XLSX** |
| **Ficha de hallazgo** | Editar la actuación y sus líneas, con la **cascada de CAPEX a la vista** y las transiciones con su motivo |
| **Personas** | Alta, rol y baja del equipo. Sin esto la aplicación la usaba una sola persona |
| **Informes** | Avisos previos, generación, descarga PPTX/XLSX y ciclo hasta emitir |
| **Plantillas** | Subida, análisis y mapeo de marcadores |
| **Sugerencias** | Proponer cambios; la bandeja solo la ve quien atiende el buzón |

## Los tres orígenes de fotografía

En el servidor es **el mismo endpoint**. Aquí la diferencia está en el `input`
que lo abre, y esa diferencia es todo lo que hace falta:

| Origen | `input` | Qué abre en el móvil |
|---|---|---|
| Ordenador | `multiple` | El explorador de archivos |
| Carrete | `accept="image/*" multiple` | La galería de fotos |
| Cámara | `accept="image/*" capture="environment"` | **La cámara trasera, directamente** |

`capture` es el atributo que hace que el móvil abra la cámara en vez de la
galería. Sin él, «hacer una foto» exigiría salir de la aplicación, disparar y
volver a entrar a buscarla, que es exactamente lo que nadie hace en una visita
con casco puesto.

## Tres decisiones que se notan al leer el código

**El token de acceso vive en memoria, no en `localStorage`.** Un token en
`localStorage` lo lee cualquier script que llegue a ejecutarse en la página; en
memoria desaparece al cerrar la pestaña. El de refresco sí se guarda —si no,
habría que iniciar sesión en cada recarga— y es el compromiso consciente del
diseño.

**El refresco se hace una sola vez aunque caduquen diez peticiones a la vez.**
Comparten la misma promesa. Sin eso, dos peticiones rotarían el token, la
segunda presentaría uno ya rotado y el servidor revocaría la familia entera
dando el token por robado: el usuario se vería expulsado sin motivo aparente.

**La fórmula del CAPEX está a la vista, no escondida** (`CalculadoraDeCapex.tsx`).
`[REQ]` P-16 pedía no ocultar las fórmulas. El endpoint que calcula la cascada
existía y estaba probado desde el principio, pero ninguna pantalla lo llamaba:
el requisito estaba construido y era invisible. Cada peldaño sale con **su base
y su porcentaje**, no solo con el resultado, para poder comprobar delante del
cliente que GG y BI van sobre el PEM y los honorarios sobre el PEC. Aplicar el
resultado a un importe es un clic aparte: `[REQ]` P-05b, la cascada nunca pisa
sola un número que alguien tecleó mirando un presupuesto real.

**Las imágenes se traen con `fetch`, no con `src`** (`src/fotos/Imagen.tsx`).
Un `<img src="/api/v1/photos/…/download">` no funciona aquí: el token vive en
memoria y el navegador no le pone ninguna cabecera a la petición que dispara un
`src`. El resultado era un `401` por cada foto y una rejilla de recuadros rotos.
Se descarga con la credencial puesta y se pinta desde un `blob:`, revocándolo al
desmontar. La rejilla pide `MINIATURA_320` y la ficha `VISTA_1600`: una visita
de 400 fotos no puede traerse 400 originales de 4 MB para pintar recuadros.

**La cola de subida es lógica pura, sin React ni red** (`src/fotos/cola.ts`).
Por eso sus 20 pruebas comprueban de verdad lo que importa —que la
concurrencia no se dispara, que un fallo de red se reintenta y un duplicado no,
que nada se pierde en silencio— sin montar un servidor ni un navegador.

## Anotar una fotografía

`[REQ]` §15.2. Señalar la fisura con una flecha es lo que hace útil una foto
técnica. El backend guardaba la capa desde el principio —versionada, auditada,
reversible, con el original intacto— pero **no había dónde dibujarla y el
informe tampoco la pintaba**: anotar producía un JSON que no llegaba a ninguna
parte.

Las coordenadas se guardan en **fracción del lado (0..1)**, no en píxeles. El
lienzo mide lo que quepa en la pantalla del móvil, la foto tiene 4000 px y el
PPTX se mide en pulgadas: con píxeles, la flecha apuntaría a un sitio distinto
en cada uno de los tres. Es el fallo clásico de las anotaciones y aquí es
imposible por construcción — el servidor rechaza cualquier coordenada fuera de
rango en vez de recortarla, porque una flecha recortada en silencio señala un
sitio que nadie eligió.

El lienzo (`src/fotos/Anotador.tsx`) y el rasterizado del servidor
(`tdd/evidence/anotaciones.py`) pintan por separado —no hay forma de compartir
código entre Canvas y Pillow—, pero **comparten el formato**, y eso es lo que
garantiza que dibujen en el mismo sitio. Se comprueba arrastrando el ratón de
verdad: `npm run test:anotador`.

## La matriz de riesgos

`[REQ]` §12. **Riesgo × horizonte temporal**, no la clásica probabilidad ×
consecuencia: la especificación define el riesgo como un grado único de cuatro
niveles ya interpretado, no como dos ejes. Cruzarlo con el plazo responde la
pregunta que se hace el inversor: *«¿cuánto de lo grave hay que pagar en los dos
primeros años?»*.

**El grado nunca se identifica solo por color.** Cada fila lleva su código
(`01`…`04`) y su nombre escritos, y las barras su cifra al lado. Uno de cada
doce hombres es daltónico, y esta pantalla se imprime en blanco y negro para
reuniones. El color acompaña; no informa por sí solo. `npm run test:riesgos` lo
comprueba leyendo el texto de la tabla.

Tres cosas que parecen detalles y no lo son, y por eso tienen prueba propia:

* **Una actuación recurrente (P-44) cuenta como un hallazgo** aunque tenga
  líneas en tres plazos. Contar líneas inflaría el recuento justo en las
  actuaciones más caras, que son las que se miran.
* **Un hallazgo sin importe sigue contando.** En campo se anota lo que se ve
  antes de saber cuánto cuesta.
* **Los hallazgos sin grado salen en su propia fila.** Esconderlos haría que el
  total de la matriz no cuadrara con el CAPEX y nadie sabría por qué faltan cien
  mil euros.

Ese cuadre es lo que sostiene la pantalla, y se comprueba de las dos maneras:
en la suite, contra el resumen de CAPEX del propio proyecto; y en el navegador,
leyendo la fila de totales.

## El mapa y las teselas

`[REQ]` §15.9. Sirve para lo que un listado no puede: ver de un vistazo si la
visita cubrió todo el activo o se quedó en la fachada, y detectar la foto que se
coló de otro edificio.

**La biblioteca es libre; las teselas no.** Leaflet es BSD-2, sin condiciones.
El servidor al que todo el mundo apunta por costumbre, `tile.openstreetmap.org`,
**no es un CDN de uso libre**: su [Tile Usage Policy][osm] lo limita a uso
ligero y no comercial y pide expresamente que el uso intensivo se autoaloje o
vaya a un proveedor de pago. Una consultora usándolo a diario estaría fuera de
esas condiciones.

Por eso **no hay ninguna URL escrita en el código**. Sin `VITE_MAP_TILE_URL` la
aplicación no contacta con nadie y el mapa funciona igual: las posiciones y las
distancias son correctas y hay escala, solo falta la cartografía de fondo.
Poner un proveedor es una decisión de quien despliega, que es quien puede
aceptar sus términos. Ver `.env.example`.

`[LIM]` **El mapa nunca es la visita completa.** Muchas fotografías llegan sin
coordenadas —en un sótano no hay señal, y muchos móviles van con la
localización apagada—, así que el recuento de las que faltan está siempre a la
vista. Sin ese número, cuatro chinchetas se leen como «se hicieron cuatro
fotos». No se infiere ninguna posición: si no vino en el EXIF, no está.

Leaflet pesa ~150 KB, así que la pestaña se carga aparte y solo al abrirla: en
obra, con datos móviles, no se puede hacer más lenta la entrada de todo el mundo
por una pantalla que muchos no van a abrir. El trozo se precachea igual, así que
el mapa también funciona sin red.

Se comprueba abriéndolo: `npm run test:mapa` cuenta las chinchetas, verifica que
el encuadre las deja todas dentro y que no sale ni una petición fuera.

[osm]: https://operations.osmfoundation.org/policies/tiles/

## Sin red

`[REQ]` §15.8. Dos piezas independientes, y conviene no confundirlas:

**La cola se guarda en IndexedDB** (`src/fotos/almacen.ts`). Antes vivía en
memoria: cerrar la pestaña, quedarse sin batería o que el móvil descartara la
página al abrir la cámara —cosa que hace— perdía todo lo pendiente. En una
visita sin cobertura eso significa volver a subir al edificio. Se guarda el
binario entero como `ArrayBuffer`, no el `File`: guardar el `File` depende de
que el navegador sepa serializarlo, y ahí Safari ha tenido fallos con blobs en
IndexedDB durante años. En la aplicación que más va a usarse desde un iPhone,
esa apuesta no compensa. Al volver, lo que quedó `SUBIENDO` vuelve a
`PENDIENTE`: esa foto no llegó al servidor, y dejarla en «subiendo» para
siempre la mete en un limbo del que nadie la saca.

**El armazón se precachea con un service worker** (`src/sw.ts`), para que la
aplicación abra en el sótano donde no hay señal. La API **nunca** se cachea: un
CAPEX servido desde caché es un número viejo presentado como actual, y eso en
un informe que se entrega es peor que un error visible.

`[LIM]` Es persistencia, **no sincronización en segundo plano**. La Background
Sync API no está usada: las fotos se suben cuando alguien abre la aplicación, y
ni siquiera solas —se avisa de cuántas quedaron y el usuario decide, que puede
estar en itinerancia—. Tampoco se piden `persist()` ni se vigila la cuota:
IndexedDB es *best-effort* y el navegador puede vaciarlo si falta espacio.

Comprobarlo exige un navegador de verdad (`npm run test:sin-red`), y no es
teatro: **encontró un fallo que ninguna otra comprobación veía.** El servidor
responde con `Vary: Origin`; las entradas del armazón se guardan sin esa
cabecera y el `<script crossorigin>` que genera Vite sí la manda, así que la
búsqueda en la caché no encontraba nunca el JavaScript. Con red no se nota —se
descarga y ya—; sin red la aplicación abría **en blanco**. Se arregló con
`ignoreVary`.

## Lo que NO está construido

- **Sincronización en segundo plano.** Lo pendiente se guarda y la aplicación
  abre sin red, pero nada se sube con el móvil en el bolsillo: hace falta
  abrirla. Ver «Sin red» más arriba.
- **Iconos del manifiesto.** Sin ellos el navegador no ofrece «instalar» en
  todas las plataformas.
- **Comparador de precios.**
- **Recuperación de contraseña.** El alta de una persona fija una contraseña
  inicial que hay que comunicar por otro canal: la invitación por correo exige
  SMTP y no está montado. Se dice en pantalla; no se disimula.
- **Edición del activo asignado a un hallazgo.** Se cambian el texto, el riesgo
  y las líneas; mover una actuación a otro activo sigue siendo un `PATCH`.
- **Pruebas de componente.** Solo la lógica pura está probada; las pantallas se
  han verificado a mano contra la API real.
