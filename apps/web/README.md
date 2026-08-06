# Frontend · PWA de due diligence técnica

React 18 + TypeScript sobre Vite. **Es la interfaz del MVP, no la aplicación
completa**: lo que hay funciona contra la API real; lo que falta está listado
abajo sin adornos.

## Arrancar en local

```bash
npm install
npm run dev        # http://localhost:5173, con proxy a la API en :8000
npm test           # 34 pruebas: cola de subida, cola persistida y estado de red
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
- **Editor de anotaciones** sobre la fotografía. El backend guarda la capa
  vectorial; no hay lienzo para dibujarla.
- **Mapa de fotografías por GPS**, matriz de riesgos y comparador de precios.
- **Recuperación de contraseña.** El alta de una persona fija una contraseña
  inicial que hay que comunicar por otro canal: la invitación por correo exige
  SMTP y no está montado. Se dice en pantalla; no se disimula.
- **Edición del activo asignado a un hallazgo.** Se cambian el texto, el riesgo
  y las líneas; mover una actuación a otro activo sigue siendo un `PATCH`.
- **Pruebas de componente.** Solo la lógica pura está probada; las pantallas se
  han verificado a mano contra la API real.
