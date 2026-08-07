/**
 * ¿Se puede pedir el acceso de vuelta? `[REQ]` §10.2
 *
 * **Alcance de esta comprobación.** El flujo entero —usar el enlace, entrar con
 * la contraseña nueva, que el enlace no sirva dos veces— está cubierto punta a
 * punta en `tests/integration/test_recuperacion_de_clave.py`, que sí puede leer
 * el correo capturado. Aquí no se lee: hacerlo exigiría un endpoint que
 * volcara los correos enviados, y añadir esa superficie **solo para una
 * prueba** no compensa, aunque se acote a `APP_ENV=local`.
 *
 * Lo que sí necesita un navegador delante, y por eso está aquí:
 *
 * 1. **Que el enlace esté a la vista en la pantalla de entrada.** Es la salida
 *    de quien no puede entrar: si hay que buscarla, no existe.
 * 2. **Que la respuesta sea idéntica exista o no la cuenta.** Se comparan las
 *    dos pantallas carácter a carácter. Es la protección que más fácil se
 *    deshace desde la interfaz por querer ser amable.
 * 3. **Que un enlace sin token no deje una pantalla rota**, que es lo que pasa
 *    cuando alguien copia la URL a mano desde el correo.
 *
 *     make run &
 *     npm run build && npx vite preview --port 4173 &
 *     node herramientas/comprobar-recuperacion.mjs
 */
import { chromium } from 'playwright'

const BASE = process.env.URL_BASE ?? 'http://localhost:4173'
const CORREO = process.env.TDD_EMAIL ?? 'admin@ejemplo.example'

const fallos = []
const sufijo = Math.random().toString(16).slice(2, 8)

const navegador = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
)
const contexto = await navegador.newContext({ viewport: { width: 1200, height: 900 } })
const pagina = await contexto.newPage()
pagina.on('pageerror', (e) => fallos.push(`Error en la página: ${e.message}`))

// ── 1 · La salida está a la vista ────────────────────────────────────────────
await pagina.goto(`${BASE}/entrar`)
const enlace = pagina.locator('a:has-text("He olvidado mi contraseña")')
if ((await enlace.count()) === 0) {
  fallos.push('No hay enlace de recuperación en la pantalla de entrada')
} else {
  await enlace.click()
  await pagina.waitForURL('**/recuperar', { timeout: 10000 })
  console.log('· Se llega a recuperar desde la pantalla de entrada')
}

// ── 2 · La misma respuesta exista o no la cuenta ─────────────────────────────
async function pedirEnlace(direccion) {
  await pagina.goto(`${BASE}/recuperar`)
  await pagina.fill('input[type="email"]', direccion)
  await pagina.click('button[type="submit"]')
  await pagina.waitForSelector('.mensaje', { timeout: 10000 })
  return (await pagina.locator('.mensaje').innerText()).replace(/\s+/g, ' ').trim()
}

// La cuenta del administrador existe; la otra, no. Se pide el enlace de la que
// existe pero NO se usa: pedirlo no cambia nada mientras nadie lo abra.
const conCuenta = await pedirEnlace(CORREO)
const sinCuenta = await pedirEnlace(`nadie-${sufijo}@ejemplo.example`)
console.log('  con cuenta :', conCuenta)
console.log('  sin cuenta :', sinCuenta)

if (conCuenta !== sinCuenta) {
  fallos.push(`La respuesta delata si la cuenta existe:\n     «${conCuenta}»\n     «${sinCuenta}»`)
}
if (!/^si esa direcci/i.test(conCuenta)) {
  fallos.push(`La respuesta no está redactada en condicional: «${conCuenta}»`)
}
// Y ninguna de las dos pantallas afirma que se ha enviado algo.
for (const texto of [conCuenta, sinCuenta]) {
  if (/hemos enviado un correo a|correo enviado a/i.test(texto)) {
    fallos.push(`La pantalla afirma haber enviado el correo: «${texto}»`)
  }
}

// ── 3 · Un enlace sin token no deja una pantalla rota ────────────────────────
await pagina.goto(`${BASE}/restablecer`)
await pagina.waitForSelector('.mensaje', { timeout: 10000 })
const sinToken = (await pagina.locator('.mensaje').innerText()).replace(/\s+/g, ' ').trim()
console.log('  sin token  :', sinToken)
if ((await pagina.locator('input[type="password"]').count()) !== 0) {
  fallos.push('Se pide contraseña nueva sin tener token: no habría dónde aplicarla')
}
if (!/pida uno nuevo|enlace nuevo/i.test(sinToken)) {
  fallos.push(`La pantalla sin token no dice qué hacer: «${sinToken}»`)
}

// Y con un token inventado se llega al formulario, pero el servidor lo rechaza
// con su motivo: la validación no está en el cliente.
await pagina.goto(`${BASE}/restablecer#me-lo-invento`)
await pagina.waitForSelector('input[type="password"]', { timeout: 10000 })
const claves = pagina.locator('input[type="password"]')
await claves.nth(0).fill('lucernario nuevo del ano 2027')
await claves.nth(1).fill('lucernario nuevo del ano 2027')
await pagina.click('button[type="submit"]')
await pagina.waitForSelector('.mensaje.error', { timeout: 10000 })
const inventado = (await pagina.locator('.mensaje.error').innerText()).replace(/\s+/g, ' ').trim()
console.log('  token falso:', inventado)
if (!/no es válido/i.test(inventado)) {
  fallos.push(`Un token inventado no se rechaza con su motivo: «${inventado}»`)
}

await navegador.close()

console.log()
if (fallos.length) {
  console.log(`${fallos.length} problema(s):`)
  for (const f of fallos) console.log(' -', f)
  process.exit(1)
}
console.log('La respuesta no delata cuentas y un enlace incompleto dice qué hacer.')
