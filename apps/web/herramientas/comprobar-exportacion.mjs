/** Comprueba que el botón de exportar CAPEX descarga la plantilla del cliente,
 *  y que el selector de idioma cambia de plantilla de verdad.
 *
 *  Las pruebas de la API ya cubren el fichero. Lo que solo se ve aquí es que el
 *  botón llame a la ruta con el idioma elegido: un `select` que no llega al
 *  `fetch` deja al usuario descargando siempre en español sin enterarse. */
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

// Las peticiones que salen al pulsar, con el idioma que toque.
const pedidas = []
pg.on('request', (r) => { if (r.url().includes('export.xlsx')) pedidas.push(r.url()) })

await pg.click('button:has-text("Exportar a XLSX")')
await pg.waitForTimeout(1500)
comprobar(pedidas.some((u) => u.includes('idioma=es')), 'en español pide idioma=es')

await pg.selectOption('.idioma select', 'en')
await pg.click('button:has-text("Exportar a XLSX")')
await pg.waitForTimeout(1500)
comprobar(pedidas.some((u) => u.includes('idioma=en')), 'al elegir inglés pide idioma=en')

comprobar(errores.length === 0, `sin errores de página (${errores.slice(0, 2).join(' · ')})`)
await nav.close()

if (fallos.length) { console.error(`\n${fallos.length} comprobaciones fallan`); process.exit(1) }
console.log('\nTodo correcto.')
