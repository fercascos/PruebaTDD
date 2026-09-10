import { chromium } from 'playwright'
import { writeFileSync } from 'node:fs'
const BASE = 'http://localhost:4173', API = 'http://localhost:8000/api/v1'
const D = '/tmp/claude-0/-home-user-PruebaTDD/d734f2bf-571f-536e-bdff-9397bc24c17b/scratchpad/pasos'
const PID = process.argv[2]

async function api(m, r, b, t) {
  const res = await fetch(API + r, { method: m, headers: { ...(b?{'Content-Type':'application/json'}:{}), ...(t?{Authorization:`Bearer ${t}`}:{}) }, body: b?JSON.stringify(b):undefined })
  const x = await res.text(); if (!res.ok) throw new Error(x); return x?JSON.parse(x):null
}
const { access_token: tk } = await api('POST','/auth/login',{email:'admin@ejemplo.example',password:'cubierta invertida 2026'})
const activos = await api('GET', `/projects/${PID}/assets`, null, tk)
const nave = activos.find(a => a.name.includes('Nave A'))

const nav = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' })
const ctx = await nav.newContext({ viewport: { width: 1360, height: 900 }, deviceScaleFactor: 1 })
const pg = await ctx.newPage()
const errores = []
pg.on('pageerror', e => errores.push(e.message))

async function foto(nombre, opciones = {}) {
  await pg.waitForTimeout(opciones.espera ?? 900)
  await pg.screenshot({ path: `${D}/${nombre}.jpg`, type: 'jpeg', quality: 82, fullPage: opciones.completa !== false })
  const alto = await pg.evaluate(() => document.documentElement.scrollHeight)
  console.log(`  ${nombre}  ${alto}px`)
}

// 01 · Entrar
await pg.goto(BASE)
await foto('01-entrar', { completa: false })
await pg.fill('input[type="email"]','admin@ejemplo.example')
await pg.fill('input[type="password"]','cubierta invertida 2026')
await pg.click('button[type="submit"]')
await pg.waitForURL('**/proyectos')

// 02 · Los encargos
await foto('02-proyectos')

// 03..11 · Las pestañas del proyecto
const PESTANAS = [
  ['03-fases', ''],
  ['04-documentacion', '/documentacion'],
  ['05-fotos', '/fotos'],
  ['06-mapa', '/mapa'],
  ['07-inventario-proyecto', '/equipo'],
  ['08-capex', '/capex'],
  ['09-dashboard', '/dashboard'],
  ['10-riesgos', '/riesgos'],
  ['11-informes', '/informes'],
]
for (const [nombre, ruta] of PESTANAS) {
  await pg.goto(`${BASE}/proyectos/${PID}${ruta}`)
  await foto(nombre, { espera: ruta === '/mapa' ? 2600 : 1200 })
}

// 12 · La lista de activos
await pg.goto(`${BASE}/proyectos/${PID}/activos`)
await foto('12-activos')

// 13..17 · El activo abierto, sección por sección
await pg.locator('tr', { hasText: 'Nave A' }).getByRole('button', { name: 'Editar' }).click()
await pg.waitForSelector('.arbol-capex', { timeout: 20000 })
await pg.waitForTimeout(2000)


for (const [nombre, sel] of [
  ['14-activo-ficha', 'form'],
  ['15-activo-ubicaciones', '.arbol-ubicaciones'],
  ['16-activo-visita', '.visita-activo'],
  ['17-activo-inventario', '.inventario-activo'],
  ['18-activo-capex', '.arbol-capex'],
]) {
  const loc = pg.locator(sel).first()
  if (await loc.count()) {
    await loc.screenshot({ path: `${D}/${nombre}.jpg`, type: 'jpeg', quality: 82 })
    console.log(`  ${nombre} (recorte)`)
  } else console.log(`  ${nombre} NO ENCONTRADO (${sel})`)
}

console.log(errores.length ? `ERRORES: ${errores.join(' | ')}` : 'sin errores de página')
await nav.close()
