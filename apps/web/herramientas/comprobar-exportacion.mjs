/** Comprueba que el botón de exportar CAPEX descarga la plantilla del cliente,
 *  que el selector de idioma cambia de plantilla de verdad, y que en un encargo
 *  de cartera la descarga sale **separada por activo**.
 *
 *  Las pruebas de la API ya cubren el fichero. Lo que solo se ve aquí es que el
 *  `select` llegue al `fetch`: uno que no llega deja al usuario descargando
 *  siempre en español, o siempre el libro conjunto, sin enterarse. */
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
const comprobar = (ok, que) => { if (!ok) fallos.push(que); console.log(`${ok ? '  ok' : '  FALLA'}  ${que}`) }

const nav = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH })
const pg = await nav.newPage()
const errores = []
pg.on('pageerror', (e) => errores.push(e.message))

await pg.goto(`${BASE}/entrar`)
await pg.fill('input[type="email"]', CORREO)
await pg.fill('input[type="password"]', CLAVE)
await pg.click('button[type="submit"]')
await pg.waitForURL('**/proyectos', { timeout: 15000 })

await pg.goto(`${BASE}/proyectos/${PID}/capex`)
await pg.waitForSelector('.tabla.capex')

comprobar(await pg.locator('.idioma select').count() === 1, 'hay un selector de idioma junto al botón')
comprobar(await pg.locator('.idioma select').inputValue() === 'es', 'por defecto viene en español')

// Las peticiones que salen al pulsar, con el idioma y el alcance que toquen.
const pedidas = []
pg.on('request', (r) => { if (r.url().includes('/capex/export.')) pedidas.push(r.url()) })

// ── Cartera: un libro por activo ────────────────────────────────────────────
// El selector de alcance solo existe con más de un activo. Cuando está, se
// comprueba primero, porque su valor por omisión cambia el botón de sitio.
const esCartera = await pg.locator('.alcance select').count() === 1
if (esCartera) {
  comprobar(
    await pg.locator('.alcance select').inputValue() === 'por-activo',
    'en una cartera, por omisión se descarga un libro por activo',
  )
  comprobar(
    await pg.locator('.grupo-activo .cabecera-grupo').count() >= 2,
    'la rejilla viene agrupada por activo, con su subtotal',
  )

  await pg.click('button:has-text("Exportar por activo")')
  await pg.waitForTimeout(1500)
  comprobar(pedidas.some((u) => u.includes('export.zip')), 'por activo pide export.zip')

  // Y el botón de cada sección, que baja SOLO ese activo.
  await pg.locator('.cabecera-grupo button:has-text("Exportar este activo")').first().click()
  await pg.waitForTimeout(1500)
  comprobar(
    pedidas.some((u) => u.includes('export.xlsx') && u.includes('asset_id=')),
    'el botón de una sección pide el libro de ese activo',
  )

  // Se vuelve al libro conjunto para las comprobaciones de idioma de abajo,
  // que son las de siempre y hablan de `export.xlsx`.
  await pg.selectOption('.alcance select', 'conjunto')
} else {
  comprobar(
    await pg.locator('.cabecera-grupo').count() === 0,
    'con un solo activo no se agrupa: la sección sobraría',
  )
}

await pg.click('button:has-text("Exportar a XLSX")')
await pg.waitForTimeout(1500)
comprobar(
  pedidas.some((u) => u.includes('export.xlsx') && u.includes('idioma=es')),
  'en español pide idioma=es',
)

await pg.selectOption('.idioma select', 'en')
await pg.click('button:has-text("Exportar a XLSX")')
await pg.waitForTimeout(1500)
comprobar(
  pedidas.some((u) => u.includes('export.xlsx') && u.includes('idioma=en')),
  'al elegir inglés pide idioma=en',
)

comprobar(errores.length === 0, `sin errores de página (${errores.slice(0, 2).join(' · ')})`)
await nav.close()

if (fallos.length) { console.error(`\n${fallos.length} comprobaciones fallan`); process.exit(1) }
console.log('\nTodo correcto.')
