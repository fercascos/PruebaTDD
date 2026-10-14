/**
 * La compilación del prototipo navegable.
 *
 * Aparte de la de la aplicación y no un modo suyo, porque lo que cambia no es
 * una bandera: es otra entrada (`prototipo/main.tsx`), sin service worker
 * —precachear un fichero suelto no significa nada— y **todo en un solo
 * fichero**, que es lo que permite abrirlo con doble clic o subirlo como
 * artefacto.
 *
 *     npm run prototipo              # deja prototipo/dist/prototipo.html
 *     TDD_IDIOMA=en npm run prototipo  # ...prototipo-en.html, en ingles
 *
 * `[REQ]` El idioma no es una bandera cosmética: elige **qué grabación se
 * incrusta**. La mitad del texto de las pantallas —zonas, capítulos de CAPEX,
 * conceptos, y el propio encargo de demostración— viene de la API, así que un
 * prototipo en inglés necesita una grabación hecha en inglés. Compilar con
 * `TDD_IDIOMA=en` y la grabación castellana daría botones en inglés y datos en
 * castellano, que es peor que no traducirlo.
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { type Plugin, defineConfig } from 'vite'

const aqui = fileURLToPath(new URL('.', import.meta.url))
const SALIDA = resolve(aqui, 'prototipo/dist')

const IDIOMA = process.env.TDD_IDIOMA ?? 'es'
if (IDIOMA !== 'es' && IDIOMA !== 'en') {
  throw new Error(`TDD_IDIOMA tiene que ser «es» o «en», no «${IDIOMA}».`)
}

/** La grabación que se incrusta, y el nombre del fichero que sale. */
const GRABACION = IDIOMA === 'es' ? 'grabacion.json' : `grabacion-${IDIOMA}.json`
const FICHERO = IDIOMA === 'es' ? 'prototipo.html' : `prototipo-${IDIOMA}.html`

/**
 * Mete el JavaScript y el CSS **dentro** del HTML.
 *
 * Se hace a mano en vez de con un plugin: son veinte líneas, y una dependencia
 * más en un proyecto que se despliega en un contenedor pequeño se paga en cada
 * `npm ci`. El bundle no pide nada a otro servidor, así que el resultado abre
 * sin red y vale como artefacto, donde cualquier fichero suelto se bloquea.
 */
function unSoloFichero(): Plugin {
  return {
    name: 'tdd-un-solo-fichero',
    apply: 'build',
    closeBundle() {
      const html = resolve(SALIDA, 'index.html')
      let texto = readFileSync(html, 'utf-8')

      texto = texto.replace(
        /<script type="module"[^>]*src="([^"]+)"[^>]*><\/script>/g,
        (_todo, src: string) => {
          const js = readFileSync(resolve(SALIDA, src.replace(/^\.?\//, '')), 'utf-8')
          // `</script>` dentro de una cadena del bundle cerraría la etiqueta
          // antes de tiempo y dejaría medio programa como texto en la página.
          return `<script type="module">${js.replace(/<\/script>/g, '<\\/script>')}</script>`
        },
      )
      texto = texto.replace(
        /<link rel="stylesheet"[^>]*href="([^"]+)"[^>]*>/g,
        (_todo, href: string) =>
          `<style>${readFileSync(resolve(SALIDA, href.replace(/^\.?\//, '')), 'utf-8')}</style>`,
      )

      const destino = resolve(SALIDA, FICHERO)
      writeFileSync(destino, texto)
      const mb = (Buffer.byteLength(texto) / 1024 / 1024).toFixed(2)
      // eslint-disable-next-line no-console
      console.log(`\nUn solo fichero: ${destino} · ${mb} MB · idioma ${IDIOMA}`)
    },
  }
}

export default defineConfig({
  root: resolve(aqui, 'prototipo'),
  // Rutas relativas: el fichero se abre desde `file://` y desde cualquier ruta
  // de un servidor ajeno, y con rutas absolutas no encontraría nada.
  base: './',
  plugins: [react(), unSoloFichero()],
  // `grabacion` es un especificador desnudo a propósito: un `import
  // './grabacion.json'` lo resuelve el disco antes de llegar al alias, y
  // entonces no habría forma de elegir el idioma sin renombrar ficheros.
  resolve: { alias: { grabacion: resolve(aqui, 'prototipo', GRABACION) } },
  define: { __TDD_IDIOMA__: JSON.stringify(IDIOMA) },
  build: {
    outDir: SALIDA,
    emptyOutDir: true,
    // Un solo trozo: con varios habría que incrustarlos todos y el orden
    // importa. Aquí no hay nada que ganar partiéndolo.
    rollupOptions: { output: { inlineDynamicImports: true } },
    assetsInlineLimit: 10_000_000,
    chunkSizeWarningLimit: 8000,
  },
})
