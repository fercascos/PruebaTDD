/**
 * ¿Se puede importar el inventario desde una hoja de verdad? `[REQ]` §7
 *
 * Lo que se comprueba con el navegador delante:
 *
 * 1. **Que previsualizar no guarde nada.** Se cuenta el inventario antes y
 *    después de subir la hoja, contra la API. Es la promesa de la pantalla y no
 *    se puede verificar leyendo el código.
 * 2. **Que cada fila diga qué le va a pasar y por qué**, con el número de fila
 *    de Excel y el estado escrito, no solo en color.
 * 3. **Que nada se sobrescriba solo.** Se importa, se corrige un equipo a mano,
 *    se vuelve a importar la misma hoja y la corrección tiene que seguir ahí.
 *
 *     make run &
 *     npm run build && npx vite preview --port 4173 &
 *     node herramientas/comprobar-importacion.mjs
 */
import { chromium } from 'playwright'
import { writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const BASE = process.env.URL_BASE ?? 'http://localhost:4173'
const API = process.env.URL_API ?? 'http://localhost:8000/api/v1'
const CORREO = process.env.TDD_EMAIL ?? 'admin@ejemplo.example'
const CLAVE = process.env.TDD_PASSWORD ?? 'cubierta invertida 2026'

const fallos = []

async function api(metodo, ruta, cuerpo, token) {
  const r = await fetch(API + ruta, {
    method: metodo,
    headers: {
      ...(cuerpo ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
  })
  const texto = await r.text()
  if (!r.ok) throw new Error(`${metodo} ${ruta} -> ${r.status}: ${texto.slice(0, 300)}`)
  return texto ? JSON.parse(texto) : null
}

const sufijo = Math.random().toString(16).slice(2, 8)
const { access_token: tk } = await api('POST', '/auth/login', { email: CORREO, password: CLAVE })
const cli = await api('POST', '/clients', { name: 'Inversora Ficticia S.L.' }, tk)
const proyecto = await api(
  'POST',
  '/projects',
  { client_id: cli.id, internal_code: `2026-${sufijo}`, name: 'Encargo con importación' },
  tk,
)
const tipologias = await api('GET', '/catalogs/asset-typologies', null, tk)
const activo = await api(
  'POST',
  `/projects/${proyecto.id}/assets`,
  { name: 'Nave Logística Norte', typology_id: tipologias[0].id },
  tk,
)

// Un XLSX mínimo escrito a mano. Se construye aquí en vez de guardar un binario
// en el repositorio: un fichero de ejemplo con datos dentro es justo lo que el
// cliente pidió no meter, y así además se ve qué contiene la hoja sin abrirla.
const { deflateRawSync } = await import('node:zlib')

function hoja(filas) {
  const esc = (s) =>
    String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const cuerpo = filas
    .map(
      (fila, f) =>
        `<row r="${f + 1}">` +
        fila
          .map(
            (celda, c) =>
              `<c r="${String.fromCharCode(65 + c)}${f + 1}" t="inlineStr">` +
              `<is><t xml:space="preserve">${esc(celda)}</t></is></c>`,
          )
          .join('') +
        '</row>',
    )
    .join('')
  return `<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${cuerpo}</sheetData></worksheet>`
}

function zip(entradas) {
  const trozos = []
  const central = []
  let offset = 0
  const crc = (buf) => {
    let c = ~0
    for (const b of buf) {
      c ^= b
      for (let i = 0; i < 8; i++) c = (c >>> 1) ^ (0xedb88320 & -(c & 1))
    }
    return ~c >>> 0
  }
  for (const [nombre, contenido] of entradas) {
    const datos = Buffer.from(contenido, 'utf-8')
    const comprimido = deflateRawSync(datos)
    const n = Buffer.from(nombre, 'utf-8')
    const cabecera = Buffer.alloc(30)
    cabecera.writeUInt32LE(0x04034b50, 0)
    cabecera.writeUInt16LE(20, 4)
    cabecera.writeUInt16LE(8, 8)
    cabecera.writeUInt32LE(crc(datos), 14)
    cabecera.writeUInt32LE(comprimido.length, 18)
    cabecera.writeUInt32LE(datos.length, 22)
    cabecera.writeUInt16LE(n.length, 26)
    trozos.push(cabecera, n, comprimido)

    const dir = Buffer.alloc(46)
    dir.writeUInt32LE(0x02014b50, 0)
    dir.writeUInt16LE(20, 4)
    dir.writeUInt16LE(20, 6)
    dir.writeUInt16LE(8, 10)
    dir.writeUInt32LE(crc(datos), 16)
    dir.writeUInt32LE(comprimido.length, 20)
    dir.writeUInt32LE(datos.length, 24)
    dir.writeUInt16LE(n.length, 28)
    dir.writeUInt32LE(offset, 42)
    central.push(dir, n)
    offset += cabecera.length + n.length + comprimido.length
  }
  const centralBuf = Buffer.concat(central)
  const fin = Buffer.alloc(22)
  fin.writeUInt32LE(0x06054b50, 0)
  fin.writeUInt16LE(entradas.length, 8)
  fin.writeUInt16LE(entradas.length, 10)
  fin.writeUInt32LE(centralBuf.length, 12)
  fin.writeUInt32LE(offset, 16)
  return Buffer.concat([...trozos, centralBuf, fin])
}

function libro(filas) {
  return zip([
    [
      '[Content_Types].xml',
      '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
    ],
    [
      '_rels/.rels',
      '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
    ],
    [
      'xl/workbook.xml',
      '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Inventario" sheetId="1" r:id="rId1"/></sheets></workbook>',
    ],
    [
      'xl/_rels/workbook.xml.rels',
      '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
    ],
    ['xl/worksheets/sheet1.xml', hoja(filas)],
  ])
}

const CABECERA = [
  'Activo',
  'Etiqueta',
  'Tipo de equipo',
  'Sistema técnico',
  'Fabricante',
  'Año de instalación',
  'Vida útil esperada',
  'Presupuesto 2027',
]
const FILAS = [
  CABECERA,
  ['Nave Logística Norte', 'CL-01', 'Enfriadora', 'Climatización', 'De la hoja', '1995', '20', '12'],
  ['Edificio Fantasma', 'CL-02', 'Bomba', '', '', '', '', ''],
  ['Nave Logística Norte', 'CL-01', 'Enfriadora repetida', '', '', '', '', ''],
]
const ruta = join(tmpdir(), `inventario-${sufijo}.xlsx`)
writeFileSync(ruta, libro(FILAS))
console.log(`· Hoja de prueba con 3 filas: una buena, un activo inexistente y una repetida`)

const antes = (await api('GET', `/projects/${proyecto.id}/equipment`, null, tk)).length

// ── La pantalla ──────────────────────────────────────────────────────────────
const navegador = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
)
const contexto = await navegador.newContext({ viewport: { width: 1500, height: 1100 } })
const pagina = await contexto.newPage()
pagina.on('pageerror', (e) => fallos.push(`Error en la página: ${e.message}`))

await pagina.goto(BASE)
await pagina.fill('input[type="email"]', CORREO)
await pagina.fill('input[type="password"]', CLAVE)
await pagina.click('button[type="submit"]')
await pagina.waitForURL('**/proyectos', { timeout: 10000 })

await pagina.goto(`${BASE}/proyectos/${proyecto.id}/equipo`)
await pagina.click('button:has-text("Importar desde Excel")')
await pagina.waitForSelector('.importar')
await pagina.setInputFiles('.importar input[type="file"]', ruta)
await pagina.waitForSelector('.tabla.previa-importacion', { timeout: 10000 })
console.log('· Previsualización abierta')

// 1 · Previsualizar no guarda nada. Se comprueba contra la API, no en pantalla.
const durante = (await api('GET', `/projects/${proyecto.id}/equipment`, null, tk)).length
if (durante !== antes) {
  fallos.push(`Previsualizar ha escrito: había ${antes} equipos y ahora hay ${durante}`)
}
console.log(`  inventario tras previsualizar: ${durante} (antes ${antes})`)

// 2 · Cada fila con su número de Excel y su estado escrito.
const filas = await pagina.locator('.tabla.previa-importacion tbody tr').allInnerTexts()
console.log('  filas:', filas.map((f) => f.replace(/\s+/g, ' ').trim().slice(0, 90)))
if (filas.length !== 3) fallos.push(`Se esperaban 3 filas en la previa, hay ${filas.length}`)
if (!filas[0]?.includes('Se creará')) fallos.push('La fila buena no dice que se va a crear')
if (!filas[1]?.includes('Error') || !filas[1]?.includes('no es un activo')) {
  fallos.push(`La fila del activo inexistente no explica el motivo: ${filas[1]}`)
}
if (!filas[2]?.includes('Repetida en la hoja')) {
  fallos.push(`La fila repetida no sale marcada: ${filas[2]}`)
}
// El número de fila es el de Excel: 2, 3 y 4 (la 1 es la cabecera).
const numeros = await pagina
  .locator('.tabla.previa-importacion tbody tr td:first-child')
  .allInnerTexts()
if (numeros.map((n) => n.trim()).join(',') !== '2,3,4') {
  fallos.push(`Los números de fila no son los de Excel: ${numeros}`)
}

// 3 · Una columna que no se reconoce se enumera en vez de perderse.
const cuerpo = await pagina.locator('.importar').innerText()
if (!cuerpo.includes('Presupuesto 2027')) {
  fallos.push('La columna que no se reconoce no se avisa: el dato se perdería en silencio')
}

// 4 · Aplicar.
await pagina.click('.importar button:has-text("Importar")')
await pagina.waitForSelector('.importar .mensaje.ok', { timeout: 10000 })
const resultado = await pagina.locator('.importar .mensaje.ok').innerText()
console.log('  resultado:', resultado.trim())
if (!resultado.includes('1 equipos creados')) {
  fallos.push(`No se ha creado exactamente 1 equipo: ${resultado}`)
}
const despues = await api('GET', `/projects/${proyecto.id}/equipment`, null, tk)
if (despues.length !== antes + 1) {
  fallos.push(`Se esperaba 1 equipo nuevo, hay ${despues.length - antes}`)
}
const enfriadora = despues.find((e) => e.tag === 'CL-01')
if (enfriadora?.technical_system_name !== 'Climatización') {
  fallos.push('El sistema técnico de la hoja no ha llegado al equipo')
}
if (enfriadora?.end_of_life_year !== 2015) {
  fallos.push(`La vida útil no se ha calculado al importar: ${enfriadora?.end_of_life_year}`)
}

// 5 · Nada se sobrescribe solo: se corrige a mano y se reimporta la misma hoja.
await api(
  'PATCH',
  `/equipment/${enfriadora.id}`,
  { manufacturer: 'Corregido tras la visita' },
  tk,
)
await pagina.click('.importar button:has-text("Volver al inventario")')
await pagina.waitForSelector('.tabla.inventario')
await pagina.click('button:has-text("Importar desde Excel")')
await pagina.setInputFiles('.importar input[type="file"]', ruta)
await pagina.waitForSelector('.tabla.previa-importacion')
const reimportada = await pagina.locator('.tabla.previa-importacion tbody tr').first().innerText()
console.log('  al reimportar:', reimportada.replace(/\s+/g, ' ').trim().slice(0, 110))
if (!reimportada.includes('Ya existe')) {
  fallos.push(`Reimportar no marca el equipo como ya existente: ${reimportada}`)
}
const casilla = pagina.locator('.importar label.casilla input[type="checkbox"]')
if ((await casilla.count()) === 0) {
  fallos.push('No hay casilla para actualizar los existentes: la decisión debe ser explícita')
} else if (await casilla.isChecked()) {
  fallos.push('La casilla de actualizar viene marcada: sobrescribiría sin que nadie lo pida')
}

const final = await api('GET', `/projects/${proyecto.id}/equipment`, null, tk)
if (final.find((e) => e.tag === 'CL-01')?.manufacturer !== 'Corregido tras la visita') {
  fallos.push('La corrección hecha a mano se ha perdido al volver a abrir la importación')
}

await navegador.close()

console.log()
if (fallos.length) {
  console.log(`${fallos.length} problema(s):`)
  for (const f of fallos) console.log(' -', f)
  process.exit(1)
}
console.log('Previsualizar no escribe, cada fila dice qué le pasa y nada se sobrescribe solo.')
