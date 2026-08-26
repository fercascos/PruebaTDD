import { readFileSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { transformSync } from 'esbuild'
import { type Plugin, defineConfig } from 'vite'

const aqui = fileURLToPath(new URL('.', import.meta.url))

/**
 * Compila `src/sw.ts` y le inyecta la lista real de ficheros del armazón.
 *
 * Se hace a mano en vez de con un plugin de PWA porque lo que hace falta cabe
 * en veinte líneas y así **no hay magia**: se ve exactamente qué se precachea.
 * La lista sale del propio bundle, con los hashes puestos. Escribirla a mano
 * habría dejado la caché sirviendo el JavaScript de la versión anterior en
 * cuanto alguien tocara un fichero, que es el fallo clásico de una PWA.
 */
function serviceWorker(): Plugin {
  return {
    name: 'tdd-service-worker',
    apply: 'build',
    generateBundle(_opciones, bundle) {
      const armazon = [
        '/',
        '/index.html',
        '/manifest.webmanifest',
        ...Object.keys(bundle)
          .filter((f) => f.endsWith('.js') || f.endsWith('.css'))
          .map((f) => `/${f}`),
        // Los iconos viven en `public/` y Vite los copia tal cual, así que no
        // aparecen en `bundle`: hay que leerlos del disco. Se precachean porque
        // el navegador los pide al instalar la aplicación, y una PWA que se
        // instala sin cobertura y sale sin icono en la pantalla de inicio
        // parece rota.
        ...readdirSync(resolve(aqui, 'public/iconos')).map((f) => `/iconos/${f}`),
      ]
      const fuente = readFileSync(resolve(aqui, 'src/sw.ts'), 'utf-8')
      const { code } = transformSync(fuente, {
        loader: 'ts',
        format: 'iife',
        target: 'es2020',
        define: { __ARMAZON__: JSON.stringify(armazon) },
      })
      this.emitFile({ type: 'asset', fileName: 'sw.js', source: code })
    },
  }
}

export default defineConfig({
  plugins: [react(), serviceWorker()],
  server: {
    // El backend vive en otro puerto en desarrollo. El proxy evita CORS y, de
    // paso, hace que en producción la aplicación sirva de un solo origen.
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } },
  },
  // `preview` NO hereda el proxy de `server`, y es el servidor contra el que
  // corren todas las comprobaciones de navegador de `herramientas/`. Sin esto
  // la aplicación construida pide `/api` al propio 4173 y recibe el index.html,
  // que falla como un error de JSON y no como un problema de configuración.
  preview: {
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } },
  },
  test: { environment: 'jsdom', globals: true },
})
