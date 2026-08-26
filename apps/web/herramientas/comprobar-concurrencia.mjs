/** Dos personas editando el mismo hallazgo, en dos navegadores de verdad.
 *
 *  Las pruebas de la API ya cubren el `412` y el `428`. Lo que **solo** se ve
 *  aquí es lo que le pasa a la persona:
 *
 *   1. Que el aviso no se pinta como un error rojo. Un choque de versión no es
 *      un fallo del usuario: si se le enseña como error, vuelve a pulsar
 *      Guardar, que es justo lo que no hay que hacer.
 *   2. Que hay un botón para recargar. Sin él, la única salida es recargar la
 *      página entera y perder el sitio.
 *   3. Que al recargar aparece **el texto de la otra persona**, no el propio.
 *      Es la comprobación que de verdad importa: que no se perdió nada.
 *
 *  Se usan dos contextos de navegador aislados, no dos pestañas: la sesión vive
 *  en memoria y dos pestañas del mismo contexto la compartirían.
 */
import { chromium } from 'playwright'

const BASE = process.env.TDD_WEB ?? 'http://localhost:4173'
const CORREO = process.env.TDD_EMAIL ?? 'admin@ejemplo.example'
const CLAVE = process.env.TDD_PASSWORD ?? 'cubierta invertida 2026'
const PID = process.env.TDD_PROYECTO

if (!PID) {
  console.error('Falta TDD_PROYECTO')
  process.exit(1)
}

const fallos = []
const comprobar = (ok, que) => {
  if (!ok) fallos.push(que)
  console.log(`${ok ? '  ok' : '  FALLA'}  ${que}`)
}

const nav = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH })

/** Una sesión iniciada, en su propio contexto. */
async function persona() {
  const ctx = await nav.newContext()
  const pg = await ctx.newPage()
  await pg.goto(`${BASE}/entrar`)
  await pg.fill('input[type="email"]', CORREO)
  await pg.fill('input[type="password"]', CLAVE)
  await pg.click('button[type="submit"]')
  await pg.waitForURL('**/proyectos', { timeout: 15000 })
  return pg
}

const marta = await persona()
const luis = await persona()
const errores = []
marta.on('pageerror', (e) => errores.push(e.message))
luis.on('pageerror', (e) => errores.push(e.message))

// ── Un hallazgo para pelearse por él ────────────────────────────────────────
// Tiene que existir antes: crearlo aquí por API exigiría el token, que vive en
// memoria del módulo y no es accesible desde `evaluate`. El encargo de pruebas
// lleva al menos uno.
for (const pg of [marta, luis]) {
  await pg.goto(`${BASE}/proyectos/${PID}/capex`)
  // Se espera a que la tabla pinte: contar antes daba siempre cero y hacía
  // parecer que el encargo no tenía hallazgos.
  await pg.waitForSelector('.tabla.capex tbody tr, .vacio', { timeout: 20000 })
  const hay = await pg.locator('.tabla.capex tbody tr').count()
  if (hay === 0) {
    console.error('El encargo de pruebas no tiene ningún hallazgo. Cree uno antes.')
    process.exit(1)
  }
  await pg.locator('.tabla.capex tbody tr button.enlace').first().click()
  await pg.waitForSelector('.ficha-hallazgo', { timeout: 15000 })
}
comprobar(true, 'las dos personas tienen el mismo hallazgo abierto')

// ── Marta guarda primero ────────────────────────────────────────────────────
const textoDeMarta = `Junta abierta 4 cm en fachada norte · ${Date.now()}`
await marta.fill('.ficha-hallazgo textarea', textoDeMarta)
await marta.locator('button:has-text("Guardar")').first().click()
await marta.waitForTimeout(1500)
comprobar(
  (await marta.locator('.mensaje.error').count()) === 0,
  'la primera en guardar no ve ningún error',
)

// ── Luis guarda después, con la versión que leyó ────────────────────────────
// Guarda desde el FINAL de la ficha, que es lo que pasa de verdad: se baja a
// tocar las líneas de CAPEX y se guarda desde ahí. El aviso se pinta arriba, y
// si no se sube solo, quien guarda no lo ve nunca.
await luis.fill('.ficha-hallazgo textarea', 'Junta abierta, revisar')
await luis.locator('button:has-text("Añadir línea")').scrollIntoViewIfNeeded()
await luis.locator('button:has-text("Guardar cambios")').first().click()
await luis.waitForSelector('.mensaje', { timeout: 15000 })
await luis.waitForTimeout(1200)

comprobar(
  (await luis.locator('.mensaje.aviso').count()) === 1,
  'el segundo ve un AVISO, no un error rojo',
)
const aviso = await luis.locator('.mensaje').first().innerText()
comprobar(/modificado/i.test(aviso), `el aviso dice que alguien lo modificó`)
comprobar(
  /no se han guardado/i.test(aviso),
  'el aviso dice en claro que sus cambios no se guardaron',
)

const recargar = luis.locator('button:has-text("Recargar con los cambios")')
comprobar((await recargar.count()) === 1, 'se le ofrece recargar, no reintentar')

// Presente en el DOM no es lo mismo que visible: el aviso está arriba y se
// guarda desde abajo. Se comprueba que de verdad quede dentro de la ventana.
const dentro = await luis.locator('.mensaje.aviso').first().evaluate((n) => {
  const c = n.getBoundingClientRect()
  return c.top >= 0 && c.bottom <= window.innerHeight
})
comprobar(dentro, 'el aviso queda a la vista, no solo presente en el DOM')

// ── Y al recargar, aparece el texto de Marta ────────────────────────────────
await recargar.click()
await luis.waitForTimeout(1500)
const enPantalla = await luis.locator('.ficha-hallazgo textarea').first().inputValue()
comprobar(
  enPantalla === textoDeMarta,
  'al recargar se ve el texto de la otra persona: no se perdió nada',
)
comprobar(
  (await luis.locator('.mensaje.aviso').count()) === 0,
  'el aviso desaparece al recargar',
)

comprobar(errores.length === 0, `sin errores de página (${errores.slice(0, 2).join(' · ')})`)
await nav.close()

if (fallos.length) {
  console.error(`\n${fallos.length} comprobaciones fallan`)
  process.exit(1)
}
console.log('\nTodo correcto.')
