import { chromium } from 'playwright'
import { writeFileSync } from 'node:fs'
const nav = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH })
const pg = await (await nav.newContext({ viewport: { width: 1440, height: 1200 } })).newPage()
const F = 'file://' + process.env.PROTO
const P = process.env.TDD_PROYECTO
const A = process.env.TDD_ACTIVOS.split(',')
const rutas = ['#/proyectos', '#/plantillas', '#/sugerencias', '#/personas',
  `#/proyectos/${P}`, `#/proyectos/${P}/activos`, `#/proyectos/${P}/dashboard`,
  `#/proyectos/${P}/riesgos`, `#/proyectos/${P}/informes`]
for (const a of A) for (const s of ['', '/documentacion', '/visita', '/inventario', '/capex'])
  rutas.push(`#/proyectos/${P}/activos/${a}${s}`)
const salida = {}
for (const r of rutas) {
  await pg.goto(F + r); await pg.waitForTimeout(1300)
  await pg.evaluate(() => document.querySelectorAll('details').forEach(d => (d.open = true)))
  await pg.waitForTimeout(250)
  salida[r] = (await pg.locator('body').innerText()).replace(/\s+/g, ' ').trim()
}
writeFileSync(process.env.VOLCADO, JSON.stringify(salida, null, 1))
console.log(`${rutas.length} rutas · ${Object.values(salida).join('').length} caracteres`)
await nav.close()
