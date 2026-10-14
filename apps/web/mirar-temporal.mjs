import { chromium } from 'playwright'
const nav = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH })
const ctx = await nav.newContext({ viewport: { width: 1440, height: 950 }, locale: 'en-GB' })
await ctx.addInitScript(() => { try { localStorage.setItem('tdd.idioma','en') } catch {} })
const pg = await ctx.newPage()
pg.on('console', m => { if (m.type()==='error') console.log('CONSOLA:', m.text().slice(0,200)) })
pg.on('pageerror', e => console.log('PAGEERROR:', e.message.slice(0,300)))
await pg.goto('http://localhost:5173/entrar')
await pg.waitForTimeout(800)
await pg.fill('input[type="email"]', 'admin@ejemplo.example')
await pg.fill('input[type="password"]', 'cubierta invertida 2026')
await pg.click('button[type="submit"]')
await pg.waitForURL('**/proyectos', { timeout: 15000 })
await pg.waitForTimeout(1500)
const P = process.env.TDD_PROYECTO
for (const r of ['', '/capex', '/documentacion']) {
  await pg.goto(`http://localhost:5173/proyectos/${P}${r}`)
  await pg.waitForTimeout(1800)
  const txt = (await pg.locator('body').innerText()).slice(0, 320).replace(/\n+/g, ' | ')
  console.log(`\n== ${r || '(resumen)'}\n   ${txt}`)
}
await pg.screenshot({ path: '/tmp/claude-0/-home-user-PruebaTDD/d734f2bf-571f-536e-bdff-9397bc24c17b/scratchpad/capex.png', fullPage: true })
await nav.close()
