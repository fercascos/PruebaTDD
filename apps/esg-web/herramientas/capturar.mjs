/**
 * Abre la aplicación en un navegador de verdad, entra, y guarda una captura de
 * cada pantalla. No es decoración: recorrer la aplicación levantada es lo que
 * destapa lo que la suite no ve —una pantalla en blanco, un filtro que no pide
 * nada, un gráfico que sale vacío con datos dentro—.
 *
 *   node herramientas/capturar.mjs [carpeta]
 */
import { chromium } from 'playwright'

const WEB = process.env.ESG_WEB ?? 'http://127.0.0.1:5174'
const CORREO = process.env.ESG_CORREO ?? 'demo@ejemplo.example'
const CARPETA = process.argv[2] ?? '/tmp/esg-capturas'

// `executablePath` cuando está puesto: el Chromium preinstalado del entorno
// puede ser de otra revisión que la que espera esta versión de Playwright, y
// entonces `launch()` a secas manda a descargar un navegador que no hace falta.
const navegador = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
)
const pagina = await navegador.newPage({ viewport: { width: 1400, height: 1000 } })
const problemas = []
pagina.on('console', (m) => m.type() === 'error' && problemas.push(m.text()))
pagina.on('pageerror', (e) => problemas.push(String(e)))

await pagina.goto(WEB, { waitUntil: 'networkidle' })
await pagina.getByLabel(/Correo/).fill(CORREO)
await pagina.getByRole('button', { name: 'Entrar' }).click()
await pagina.getByRole('button', { name: 'Panel' }).waitFor()
await pagina.waitForSelector('.tarjetas .tarjeta')
await pagina.screenshot({ path: `${CARPETA}/panel.png`, fullPage: true })

await pagina.getByRole('button', { name: 'Cargar fichero' }).click()

// Se sube un fichero de verdad y se simula: es la pantalla con más piezas
// —lectura, mapeo, validación, solape— y la única forma de saber que encajan
// es hacerlo con el navegador, no llamando a la API con curl.
const CSV = [
  'CUPS;Fecha inicio;Fecha fin;Consumo;Unidad;Tipo',
  'A-001-LUZ;01/01/2023;31/01/2023;8.240,50;kWh;Electricidad',
  'A-001-LUZ;01/02/2023;28/02/2023;siete mil;kWh;Electricidad',
  'NO-EXISTE;01/03/2023;31/03/2023;900;kWh;Electricidad',
].join('\n')
await pagina.setInputFiles('input[type=file]', {
  name: 'consumos-de-prueba.csv',
  mimeType: 'text/csv',
  buffer: Buffer.from(CSV, 'latin1'),
})
await pagina.getByRole('button', { name: 'Simular' }).click()
await pagina.getByText('Simulación').waitFor()
await pagina.screenshot({ path: `${CARPETA}/cargar.png`, fullPage: true })

const aceptadas = await pagina.locator('.recuento li').first().innerText()
if (!aceptadas.startsWith('1 ')) {
  problemas.push(`La simulación debía aceptar 1 fila y dijo: ${aceptadas}`)
}

await pagina.getByRole('button', { name: 'Facturas IA' }).click()
await pagina.waitForTimeout(300)
await pagina.screenshot({ path: `${CARPETA}/revision.png`, fullPage: true })

await navegador.close()
if (problemas.length) {
  console.error('La consola del navegador se quejó:')
  problemas.forEach((p) => console.error(' ·', p))
  process.exit(1)
}
console.log(`Capturas en ${CARPETA}`)
