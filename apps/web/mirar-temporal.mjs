import { chromium } from 'playwright'
const nav = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH })
const ctx = await nav.newContext({ viewport: { width: 1440, height: 1200 } })
const pg = await ctx.newPage()
const F = 'file:///home/user/PruebaTDD/apps/web/prototipo/dist/prototipo-en.html'
const P = process.env.TDD_PROYECTO
const A = process.env.TDD_ACTIVOS.split(',')
const rutas = ['#/proyectos', '#/plantillas', '#/sugerencias', '#/personas',
  `#/proyectos/${P}`, `#/proyectos/${P}/activos`, `#/proyectos/${P}/dashboard`,
  `#/proyectos/${P}/riesgos`, `#/proyectos/${P}/informes`]
for (const a of A) for (const s of ['', '/documentacion', '/visita', '/inventario', '/capex'])
  rutas.push(`#/proyectos/${P}/activos/${a}${s}`)

// Palabras funcionales que no existen en ingles.
const ES = /(?:^|[\s(«"'])(?:de|del|la|el|los|las|con|que|para|por|una|un|se|sin|los|sus|está|más|así|qué|cuánto|cómo|desde|hay|no se|todavía|ningun\w*)(?:[\s)»,.:;"']|$)/i
const sospechosas = new Map()
for (const r of rutas) {
  await pg.goto(F + r)
  await pg.waitForTimeout(1300)
  // Abrir los <details> para ver lo que esconden.
  await pg.evaluate(() => document.querySelectorAll('details').forEach(d => (d.open = true)))
  await pg.waitForTimeout(300)
  const textos = await pg.evaluate(() => {
    const salida = []
    const paseo = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
    let n
    while ((n = paseo.nextNode())) {
      const t = n.textContent.replace(/\s+/g, ' ').trim()
      if (t.length > 6) salida.push(t)
    }
    return salida
  })
  for (const t of textos) if (ES.test(t)) {
    if (!sospechosas.has(t)) sospechosas.set(t, r)
  }
}
console.log(`${sospechosas.size} textos que parecen castellano:`)
for (const [t, r] of [...sospechosas].sort()) console.log(`  ${t.slice(0, 120)}`)
await nav.close()
