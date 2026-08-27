/** De dónde sale el navegador de las comprobaciones.
 *
 *  Estaba repetido en las catorce: `chromium.launch(...)` a pelo. El problema
 *  no era la repetición, era lo que implicaba: **todo se comprobaba en
 *  Chromium**, y la vista que más se usa de esta aplicación es la de campo, en
 *  un iPhone. Ahí manda WebKit.
 *
 *      TDD_NAVEGADOR=webkit node herramientas/comprobar-sin-red.mjs
 *      TDD_DISPOSITIVO="iPhone 14" node herramientas/comprobar-safari.mjs
 *
 *  `[LIM]` **WebKit de Playwright no es Safari de iOS.** Comparte motor, así
 *  que caza las diferencias de CSS y de API de JavaScript, que son la mayoría.
 *  Lo que NO reproduce: la cámara real, HEIC de verdad, el desalojo de
 *  IndexedDB a los siete días sin usar la aplicación, la presión de memoria que
 *  recarga la pestaña, y el comportamiento de «Añadir a pantalla de inicio».
 *  Eso solo se comprueba en un teléfono, y hasta que se haga no se puede
 *  afirmar que la vista de campo funcione en un iPhone.
 */
import { chromium, devices, webkit } from 'playwright'

const MOTORES = { chromium, webkit }

/** Qué motor toca. Por omisión Chromium, que es el que hay instalado en local. */
export function motor() {
  const nombre = process.env.TDD_NAVEGADOR ?? 'chromium'
  const elegido = MOTORES[nombre]
  if (!elegido) {
    throw new Error(`TDD_NAVEGADOR="${nombre}" no es ninguno de: ${Object.keys(MOTORES).join(', ')}`)
  }
  return { nombre, motor: elegido }
}

/** Abre el navegador y un contexto, ya emulando el dispositivo si se pidió. */
export async function abrir(opciones = {}) {
  const { nombre, motor: elegido } = motor()
  // `executablePath` solo para Chromium: es el que está preinstalado en una
  // ruta fija. WebKit lo instala Playwright donde le corresponde.
  const lanzamiento = nombre === 'chromium' && process.env.CHROMIUM_PATH
    ? { executablePath: process.env.CHROMIUM_PATH }
    : {}
  const navegador = await elegido.launch(lanzamiento)

  const dispositivo = process.env.TDD_DISPOSITIVO
  if (dispositivo && !devices[dispositivo]) {
    throw new Error(`TDD_DISPOSITIVO="${dispositivo}" no lo conoce Playwright`)
  }
  const contexto = await navegador.newContext({
    ...(dispositivo ? devices[dispositivo] : { viewport: { width: 1280, height: 900 } }),
    ...opciones,
  })
  return { navegador, contexto, motorUsado: nombre, dispositivo: dispositivo ?? 'escritorio' }
}
