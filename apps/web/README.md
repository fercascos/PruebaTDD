# Frontend · PWA de due diligence técnica

React 18 + TypeScript sobre Vite. **Es la interfaz del MVP, no la aplicación
completa**: lo que hay funciona contra la API real; lo que falta está listado
abajo sin adornos.

## Arrancar en local

```bash
npm install
npm run dev        # http://localhost:5173, con proxy a la API en :8000
npm test           # 20 pruebas de la cola de subida
npm run build      # comprobación de tipos + empaquetado
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

## Lo que NO está construido

- **Modo offline real.** No hay IndexedDB ni service worker: la cola de subida
  vive en memoria y se pierde al recargar. El manifiesto está, pero la
  aplicación **no funciona sin red**, y §15.8 lo pide para la fase offline.
- **Editor de anotaciones** sobre la fotografía. El backend guarda la capa
  vectorial; no hay lienzo para dibujarla.
- **Mapa de fotografías por GPS**, matriz de riesgos, comparador de precios y
  administración de usuarios. El alta de personas existe en la API; no hay
  pantalla.
- **Edición de hallazgos y de líneas de CAPEX ya creadas.** Se crean desde la
  interfaz; corregir un importe sigue siendo un `PATCH` por API.
- **Pruebas de componente.** Solo la lógica pura está probada; las pantallas se
  han verificado a mano contra la API real.
